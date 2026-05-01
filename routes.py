from flask import render_template, request, redirect, url_for, jsonify, Response, session
from flask_login import login_required, logout_user, current_user
from google import genai
from dotenv import load_dotenv
from system_prompts import PROMPTS
from models import db, User, UserSource, Report
from fetchers import fetch_feed, fetch_github_repo, fetch_drive_folder
from datetime import datetime, timedelta
import markdown
import os
from elevenlabs.client import ElevenLabs
import json
import uuid

load_dotenv()

MODE_MODELS = {
    "full_briefing": "gemini-2.5-flash",
    "quick_summary": "gemini-2.5-flash-lite"
}

def get_gemini_response(contents, system_instruction, mode="full_briefing"):
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
            report_count = Report.query.filter_by(user_id=current_user.id).count()
            google_connected = google.token is not None
            google_token = google.token.get("access_token") if google.token else None
            return render_template('dashboard.html', sources=sources, 
                                google_connected=google_connected,
                                google_token=google_token,
                                google_api_key=os.getenv('GOOGLE_API_KEY'),
                                report_count=report_count)
        # For visitors, just render the dashboard with visitor mode
        return render_template('dashboard.html')

    @app.route('/dashboard')
    @login_required
    def dashboard():
        sources = UserSource.query.filter_by(user_id=current_user.id).all()
        report_count = Report.query.filter_by(user_id=current_user.id).count()
        from flask_dance.contrib.google import google
        google_connected = google.token is not None
        google_token = google.token.get("access_token") if google.token else None
        return render_template('dashboard.html', sources=sources,
                            google_connected=google_connected,
                            google_token=google_token,
                            google_api_key=os.getenv('GOOGLE_API_KEY'),
                            report_count=report_count)

    @app.route('/add_source', methods=["POST"])
    @login_required
    def add_source():
        identifier = request.form.get("identifier") or request.form.get("drive_identifier")
        source_type = request.form.get("source_type")
        label = request.form.get("label", "").strip()
        if identifier and len(identifier) < 200 and label:
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

    @app.route('/visitor_report', methods=["POST", "GET"])
    def visitor_report():
        # Check if this is a request to load a saved report
        report_id = request.args.get('load')
        if report_id:
            # This is a GET request to load a saved report
            # The actual report data will be loaded from localStorage on the client side
            return render_template('visitor_report_view.html', report_id=report_id)
        
        # This is a POST request to generate a new report
        repo = request.form.get("repo")
        timeframe = int(request.form.get("timeframe", 7))
        output = None
        
        if repo:
            url = f"https://github.com/{repo}/releases.atom"
            items = fetch_feed(url, days=timeframe)
            if items:
                combined = "\n\n".join(items)
                raw = get_gemini_response(combined, PROMPTS["full_briefing"], "full_briefing")
                
                if raw.startswith("Error generating report:"):
                    return render_template('error.html')
                
                output = markdown.markdown(raw)
                
                # Create a visitor report object to pass to template (not saved to DB)
                visitor_report = {
                    'id': str(uuid.uuid4()),  # Generate unique ID for local storage
                    'content': raw,
                    'report_type': 'full_briefing',
                    'time_range': str(timeframe),
                    'created_at': datetime.utcnow(),
                    'repo': repo,
                    'is_visitor': True
                }
                
                return render_template('report.html', 
                                     output=output, 
                                     saved_report=visitor_report,
                                     is_visitor=True)
            else:
                output = "No releases found for that repo in the selected timeframe."
        
        return render_template('report.html', output=output, is_visitor=True)

    @app.route('/report', methods=["POST"])
    @login_required
    def report():
        timeframe = int(request.form.get("timeframe", 7))
        mode = request.form.get("mode", "full_briefing")
        sources = UserSource.query.filter_by(user_id=current_user.id).all()
        all_content = []
        for source in sources:
            
            if source.source_type == 'github':
                items = fetch_github_repo(source.identifier, days=timeframe)
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

            raw = get_gemini_response(combined, PROMPTS[mode], mode)
            if raw.startswith("Error generating report:"):
                return render_template('error.html')
            output = markdown.markdown(raw)
            source_labels = [s.label for s in sources]
            report = Report(
                user_id=current_user.id,
                report_type=mode,
                time_range=str(timeframe),
                content=raw,
                sources_used=", ".join(source_labels)
            )

            db.session.add(report)
            db.session.commit()
            
            report_count = Report.query.filter_by(user_id=current_user.id).count()
            
            # Pass the newly created report to the template
            return render_template('report.html', output=output, saved_report=report, report_count=report_count)
        else:
            output = "No content found for the selected timeframe."
            report_count = Report.query.filter_by(user_id=current_user.id).count()
            return render_template('report.html', output=output, report_count=report_count)

    @app.route('/reports')
    @login_required
    def saved_reports():
        reports = Report.query.filter_by(
            user_id=current_user.id
        ).order_by(Report.created_at.desc()).all()
        return render_template('reports_index.html', reports=reports, timedelta=timedelta)

    @app.route('/reports/<int:report_id>')
    @login_required
    def view_report(report_id):
        report = Report.query.get_or_404(report_id)
        if report.user_id != current_user.id:
            return redirect(url_for('dashboard'))
        output = markdown.markdown(report.content)
        report_count = Report.query.filter_by(user_id=current_user.id).count()
        return render_template('report.html', output=output, saved_report=report, report_count=report_count)

    # TTS endpoint - now supports both authenticated and visitor reports
    @app.route('/tts/<report_id>', methods=["POST"])
    def generate_tts(report_id):
        # Try to get authenticated report first
        if current_user.is_authenticated:
            try:
                report = Report.query.get_or_404(int(report_id))
                if report.user_id != current_user.id:
                    return jsonify({"error": "Unauthorized"}), 403
                text_content = report.content
            except:
                return jsonify({"error": "Report not found"}), 404
        else:
            # For visitors, get content from request body
            data = request.get_json() or {}
            text_content = data.get('content')
            if not text_content:
                return jsonify({"error": "No content provided"}), 400
        
        try:
            # Get voice_id from request, default to George
            data = request.get_json() or {}
            voice_id = data.get('voice_id', 'JBFqnCBsd6RMkjVDRZzb')
            
            client = ElevenLabs(api_key=os.getenv('ELEVENLABS_API_KEY'))
            
            # Convert report content (remove markdown formatting for better TTS)
            clean_text = text_content.replace('#', '').replace('*', '').replace('_', '')
            
            audio = client.text_to_speech.convert(
                text=clean_text,
                voice_id=voice_id,
                model_id="eleven_turbo_v2_5",
                output_format="mp3_44100_128"
            )
            
            # Stream the audio back to the client
            def generate():
                for chunk in audio:
                    yield chunk
            
            return Response(generate(), mimetype="audio/mpeg")
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/reports/delete/<int:report_id>', methods=["POST"])
    @login_required
    def delete_report(report_id):
        report = Report.query.get_or_404(report_id)
        if report.user_id == current_user.id:
            db.session.delete(report)
            db.session.commit()
        return redirect(url_for('saved_reports'))

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('index'))

    @app.route('/privacy')
    def privacy():
        return render_template('privacy.html')

    @app.route('/terms')
    def terms():
        return render_template('terms.html')

    @app.route('/sitemap.xml')
    def sitemap():
        from flask import Response
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://distillerat.com/</loc></url>
        <url><loc>https://distillerat.com/privacy</loc></url>
        <url><loc>https://distillerat.com/terms</loc></url>
    </urlset>'''
        return Response(xml, mimetype='application/xml')