from flask import render_template, request, redirect, url_for
from flask_login import login_required, logout_user, current_user
from google import genai
from dotenv import load_dotenv
from system_prompts import PROMPTS
from models import db, User, UserSource
from fetchers import fetch_feed, fetch_drive_folder
import markdown
import os

load_dotenv()

MODE_MODELS = {
    "short_version": "gemini-2.0-flash-lite",
    "whats_changed": "gemini-2.5-flash-lite",
    "big_picture": "gemini-2.5-flash",
    "needs_attention": "gemini-2.5-flash"
}

def get_gemini_response(contents, system_instruction, mode="whats_changed"):
    api_key = os.getenv('GEMINI_API_KEY')
    model = MODE_MODELS.get(mode, "gemini-2.5-flash-lite")
    try:
        c = genai.Client(api_key=api_key)
        response = c.models.generate_content(
            model=model,
            contents=contents,
            config={"system_instruction": system_instruction}
        )
        return response.text
    except Exception as e:
        return f"Error generating report: {str(e)}"

def register_routes(app):

    @app.route('/')
    def index():
        if current_user.is_authenticated:
            from flask_dance.contrib.google import google
            sources = UserSource.query.filter_by(user_id=current_user.id).all()
            google_connected = google.token is not None
            return render_template('dashboard.html', sources=sources, google_connected=google_connected)
        return render_template('dashboard.html')

    @app.route('/dashboard')
    @login_required
    def dashboard():
        sources = UserSource.query.filter_by(user_id=current_user.id).all()
        from flask_dance.contrib.google import google
        google_connected = google.token is not None
        return render_template('dashboard.html', sources=sources, google_connected=google_connected)

    @app.route('/add_source', methods=["POST"])
    @login_required
    def add_source():
        identifier = request.form.get("identifier")
        source_type = request.form.get("source_type")
        label = request.form.get("label", identifier)
        if identifier and len(identifier) < 200:
            source = UserSource(
                user_id=current_user.id,
                source_type=source_type,
                identifier=identifier,
                label=label
            )
            db.session.add(source)
            db.session.commit()
        return redirect(url_for('dashboard'))

    @app.route('/remove_source/<int:source_id>')
    @login_required
    def remove_source(source_id):
        source = UserSource.query.get(source_id)
        if source and source.user_id == current_user.id:
            db.session.delete(source)
            db.session.commit()
        return redirect(url_for('dashboard'))

    @app.route('/visitor_report', methods=["POST"])
    def visitor_report():
        repo = request.form.get("repo")
        timeframe = int(request.form.get("timeframe", 7))
        output = None
        if repo:
            url = f"https://github.com/{repo}/releases.atom"
            items = fetch_feed(url, days=timeframe)
            if items:
                combined = "\n\n".join(items)
                output = markdown.markdown(get_gemini_response(combined, PROMPTS["whats_changed"], "whats_changed"))
            else:
                output = "No releases found for that repo in the selected timeframe."
        return render_template('report.html', output=output)

    @app.route('/report', methods=["POST"])
    @login_required
    def report():
        timeframe = int(request.form.get("timeframe", 7))
        mode = request.form.get("mode", "whats_changed")
        sources = UserSource.query.filter_by(user_id=current_user.id).all()
        all_content = []

        for source in sources:
            if source.source_type == 'github':
                url = f"https://github.com/{source.identifier}/releases.atom"
                items = fetch_feed(url, days=timeframe)
                if items:
                    all_content.append(f"## GitHub: {source.identifier}\n" + "\n\n".join(items))
            elif source.source_type == 'google_drive':
                from flask_dance.contrib.google import google
                token = google.token.get("access_token") if google.token else None
                if token:
                    content = fetch_drive_folder(source.identifier, token, days=timeframe)
                    all_content.append(f"## Google Drive: {source.label}\n{content}")

        if all_content:
            combined = "\n\n".join(all_content)
            output = markdown.markdown(get_gemini_response(combined, PROMPTS[mode], mode))
        else:
            output = "No content found for the selected timeframe."
        return render_template('report.html', output=output)

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('index'))
