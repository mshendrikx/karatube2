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
    roomid = db.Column(db.String(100))
    roomadm = db.Column(db.String(1))
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

class Song(db.Model):
    youtubeid = db.Column(db.String(100), primary_key=True)
    name = db.Column(db.String(100))
    artist = db.Column(db.String(100))
    downloaded = db.Column(db.Integer)


class Room(db.Model):
    roomid = db.Column(db.String(100), primary_key=True)
    password = db.Column(db.String(1000))
    barcode = db.Column(db.Integer)
    songint = db.Column(db.Integer)


class Queue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roomid = db.Column(db.String(100))
    userid = db.Column(db.String(100))
    youtubeid = db.Column(db.String(100))
    status = db.Column(db.String(1))
    order = db.Column(db.Integer)


class Roomadm(db.Model):
    roomid = db.Column(db.String(100), primary_key=True)
    userid = db.Column(db.String(100), primary_key=True)


class Config(db.Model):
    id = db.Column(db.String(6), primary_key=True)
    library = db.Column(db.String(1))
    lastfm = db.Column(db.String(100))
    updateratio = db.Column(db.Integer)


class Controls(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roomid = db.Column(db.String(100))
    command = db.Column(db.String(10))
    commvalue = db.Column(db.String(10))
