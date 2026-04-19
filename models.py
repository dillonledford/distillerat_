from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    github_id = db.Column(db.String, unique=True)
    username = db.Column(db.String)
    avatar_url = db.Column(db.String)
    sources = db.relationship('UserSource', backref='user', lazy=True)

class UserSource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    source_type = db.Column(db.String)  # 'github' or 'google drive'
    identifier = db.Column(db.String)   # repo name or google drive file ID
    label = db.Column(db.String)        # optional friendly name

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    report_type = db.Column(db.String)
    time_range = db.Column(db.String)
    content = db.Column(db.Text)
    sources_used = db.Column(db.String)  # ← add this, comma separated labels
    created_at = db.Column(db.DateTime, default=db.func.now())
    user = db.relationship('User', backref='reports')
    