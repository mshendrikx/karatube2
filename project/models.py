from flask_login import UserMixin
from . import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mobile = db.Column(db.String(30), unique=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(1000))
    language = db.Column(db.String(2))
    theme = db.Column(db.String(5))
    admin = db.Column(db.Integer)
    whatsapp_id = db.Column(db.String(30))
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )


class MobVer(db.Model):
    userid = db.Column(db.Integer, primary_key=True)
    mobile = db.Column(db.String(30))
    whatsapp_id = db.Column(db.String(30))
    code = db.Column(db.String(6))
    created_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )
