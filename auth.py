from flask_dance.contrib.github import make_github_blueprint
from flask_dance.consumer.storage.session import SessionStorage
from flask_dance.consumer import oauth_authorized
from flask_dance.contrib.google import make_google_blueprint
from flask_login import login_user
from models import db, User

import os

github_bp = make_github_blueprint(
    client_id=os.getenv('GITHUB_CLIENT_ID'),
    client_secret=os.getenv('GITHUB_CLIENT_SECRET'),
    redirect_to="dashboard",
    storage=SessionStorage()
)

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
            username=github_info['login'],
            avatar_url=github_info.get('avatar_url', '')
        )
        db.session.add(user)
        db.session.commit()
    login_user(user)
    return False

google_bp = make_google_blueprint(
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    scope=[
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/documents.readonly"
    ],
    redirect_to="index",
    storage=SessionStorage()
)
