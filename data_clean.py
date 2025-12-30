import os
import dotenv

from flask_sqlalchemy import SQLAlchemy
from flask import Flask

dotenv.load_dotenv()

SONGS_DIR = "/data/media/karaoke/songs/"
THUMBS_DIR = "/data/media/karaoke/thumbs/"

db = SQLAlchemy()


class Song(db.Model):
    youtubeid = db.Column(db.String(100), primary_key=True)
    name = db.Column(db.String(100))
    artist = db.Column(db.String(100))
    downloaded = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

db_user = os.environ.get("DB_USERNAME")
db_pass = os.environ.get("DB_PASSWORD")
db_host = os.environ.get("DB_HOST")
db_port = os.environ.get("DB_PORT")
db_name = os.environ.get("DB_DATABASE")

db_url = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
db.init_app(app)

with app.app_context():

    songs = Song.query.all()

    for song in songs:
        check_song = os.path.join(SONGS_DIR, str(song.youtubeid) + ".mp4")
        if not os.path.exists(check_song):
            Song.query.filter_by(youtubeid=song.youtubeid).delete()
            db.session.commit()
            del_thumb = os.path.join(THUMBS_DIR, str(song.youtubeid) + ".jpg")
            os.remove(del_thumb)
            print("Song " + str(song.youtubeid) + " - " + song.name + " deleted")

    song_files = os.listdir(SONGS_DIR)
    for song_file in song_files:
        check_song = Song.query.filter_by(youtubeid=song_file[:-4]).first()
        if not check_song:
            del_song = os.path.join(SONGS_DIR, song_file)
            os.remove(del_song)
            print("Song " + song_file[:-4] + " deleted")

    thumb_files = os.listdir(THUMBS_DIR)
    for thumb_file in thumb_files:
        check_song = Song.query.filter_by(youtubeid=thumb_file[:-4]).first()
        if not check_song:
            del_thumb = os.path.join(THUMBS_DIR, thumb_file)
            os.remove(del_thumb)
            print("Thumb " + thumb_file[:-4] + " deleted")
