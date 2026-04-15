import os

if os.getenv('FLASK_ENV') == 'development':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_dance.contrib.github import make_github_blueprint, github
from flask_dance.consumer.storage.session import SessionStorage
from flask_dance.consumer import oauth_authorized
from flask_sqlalchemy import SQLAlchemy
from google import genai
from dotenv import load_dotenv
from system_prompts import PROMPTS
import feedparser
from datetime import datetime, timedelta, timezone
import markdown
from flask import request as flask_request
import requests

load_dotenv()
print("CLIENT ID:", os.getenv('GITHUB_CLIENT_ID'))

# --- App setup ---
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_NAME'] = 'distillerat_session'

# --- Extensions ---
db = SQLAlchemy(app)
login_manager = LoginManager(app)

# --- OAuth ---
github_bp = make_github_blueprint(
    client_id=os.getenv('GITHUB_CLIENT_ID'),
    client_secret=os.getenv('GITHUB_CLIENT_SECRET'),
    redirect_to="dashboard",
    storage=SessionStorage()
)
app.register_blueprint(github_bp, url_prefix='/login')


@app.before_request
def log_request():
    print("REQUEST URL:", flask_request.url)


# --- Gemini ---
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

# --- User model ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    github_id = db.Column(db.String, unique=True)
    username = db.Column(db.String)

# --- Create tables after model is defined ---
with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- OAuth signal handler ---
@oauth_authorized.connect_via(github_bp)
def github_logged_in(blueprint, token):
    if not token:
        return False
    resp = blueprint.session.get('/user')
    if not resp.ok:
        return False
    github_info = resp.json()
    user = User.query.filter_by(github_id=str(github_info['id'])).first()
    if not user:
        user = User(
            github_id=str(github_info['id']),
            username=github_info['login']
        )
        db.session.add(user)
        db.session.commit()
    login_user(user)
    return False

def fetch_figma(file_id, token):
    headers = {"X-Figma-Token": token}
    
    # Get file info
    file_resp = requests.get(f"https://api.figma.com/v1/files/{file_id}", headers=headers)
    file_data = file_resp.json()
    
    # Get version history
    versions_resp = requests.get(f"https://api.figma.com/v1/files/{file_id}/versions", headers=headers)
    versions = versions_resp.json().get('versions', [])
    
    # Extract useful text from document
    def extract_text(node, texts=[]):
        if node.get('type') == 'TEXT':
            texts.append(node.get('characters', ''))
        for child in node.get('children', []):
            extract_text(child, texts)
        return texts
    
    texts = extract_text(file_data.get('document', {}))
    
    summary = f"File: {file_data.get('name')}\n"
    summary += f"Last Modified: {file_data.get('lastModified')}\n"
    summary += f"Versions: {len(versions)}\n\n"
    summary += "Version History:\n"
    for v in versions:
        summary += f"- {v['created_at']} by {v['user']['handle']}"
        if v.get('label'):
            summary += f" | Label: {v['label']}"
        if v.get('description'):
            summary += f" | {v['description']}"
        summary += "\n"
    summary += f"\nText content found in file:\n" + "\n".join(texts)
    
    return summary

@app.route('/figma', methods=["GET", "POST"])
@login_required
def figma():
    output = None
    if request.method == "POST":
        file_id = request.form.get("file_id")
        mode = request.form.get("mode", "summarize")
        token = os.getenv("FIGMA_ACCESS_TOKEN")
        content = fetch_figma(file_id, token)
        response = client.models.generate_content(
            # change model when usage is exceeded
            model="gemini-2.5-flash",
            contents=content,
            config={"system_instruction": PROMPTS[mode]}
        )
        output = markdown.markdown(response.text)
    return render_template("figma.html", output=output)

# --- Routes ---
@app.route('/', methods=["GET", "POST"])
def index():
    output = None
    if request.method == "POST":
        prompt = request.form.get("prompt")
        mode = request.form.get("mode", "synthesize")
        system_instruction = PROMPTS[mode]
        response = client.models.generate_content(
            # change model when usage is exceeded
            model="gemini-2.5-flash",
            contents=prompt,
            config={"system_instruction": system_instruction}
        )
        output = markdown.markdown(response.text)
    return render_template("index.html", output=output)

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

def fetch_feed(url, days=1):
    feed = feedparser.parse(url)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    items = []
    for entry in feed.entries:
        parsed = getattr(entry, 'published_parsed', None) or getattr(entry, 'updated_parsed', None)
        if not parsed:
            continue
        published = datetime(*parsed[:6], tzinfo=timezone.utc)
        if published >= cutoff:
            items.append(f"Title: {entry.title}\nSummary: {entry.get('summary', '')}")
    return items

@app.route('/fetch', methods=["GET", "POST"])
@login_required
def fetch():
    output = None
    if request.method == "POST":
        repo = request.form.get("repo")
        timeframe = int(request.form.get("timeframe", 7))
        mode = request.form.get("mode", "summarize")
        url = f"https://github.com/{repo}/releases.atom"
        items = fetch_feed(url, days=timeframe)
        if items:
            combined = "\n\n".join(items)
            response = client.models.generate_content(
                # change model when usage is exceeded
                model="gemini-2.5-flash",
                contents=combined,
                config={"system_instruction": PROMPTS[mode]}
            )
            output = markdown.markdown(response.text)
        else:
            output = "No releases found in that timeframe."
    return render_template("fetch.html", output=output)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- Entry ---
if __name__ == '__main__':
    app.run(debug=True, host='localhost')
