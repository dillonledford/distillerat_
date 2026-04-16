import os

if os.getenv('FLASK_ENV') == 'development':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask
from flask_login import LoginManager
from dotenv import load_dotenv
from models import db, User
from routes import register_routes
from auth import github_bp, google_bp

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_NAME'] = 'distillerat_session'
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') != 'development'

db.init_app(app)
login_manager = LoginManager(app)

app.register_blueprint(github_bp, url_prefix='/login')
app.register_blueprint(google_bp, url_prefix='/login/google')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

register_routes(app)

if __name__ == '__main__':
    app.run(debug=True, host='localhost')
