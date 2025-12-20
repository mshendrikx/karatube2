import musicbrainzngs
import subprocess
import requests
import os
import smtplib
import pika
import json

from flask_babel import gettext as _
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from youtubesearchpython import VideosSearch
from pathlib import Path
from .models import User, Song, Queue
from pytubefix import YouTube
from . import db

APP_PATH = str(Path(__file__).parent.absolute())
YT_BASE_URL = "https://www.youtube.com/watch?v="
SONGS_DIR = "/static/songs/"
THUMBS_DIR = "/static/thumbs/"
TOKEN_DIR = "/token/"

musicbrainzngs.set_useragent(
    "python-musicbrainzngs-example",
    "0.1",
    "https://github.com/alastair/python-musicbrainzngs/",
)


class PlayerData:
    singer = ""
    song = ""
    next_singer = ""
    next_song = ""
    video_url = ""


class SongQueue:
    id = 0
    roomid = ""
    userid = ""
    singer = ""
    youtubeid = ""
    artist = ""
    song = ""
    status = ""


class MusicData:
    id = 0
    artist = ""
    song = ""

    def get_display_data(self):
        return {"artist": self.artist, "song": self.song}


class YoutubeVideos:
    id = ""
    thumb = ""
    description = ""

    def get_display_data(self):
        image = self.thumb.split("/")[5]
        return {
            "id": self.id,
            "thumb": self.thumb,
            "description": self.description,
            "image": image,
        }


def video_delete(videoid):

    filename = APP_PATH + SONGS_DIR + str(videoid) + ".mp4"
    cmd = ["rm", filename]

    rc = subprocess.call(cmd)
    if rc != 0:
        rc = subprocess.call(cmd)  # retry once. Seems like this can be flaky

    filename = APP_PATH + THUMBS_DIR + str(videoid) + ".jpg"
    cmd = ["rm", filename]
    rc = subprocess.call(cmd)

    return True


def queue_add(roomid, userid, youtubeid, status):

    try:
        new_queue = Queue(
            roomid=roomid,
            userid=userid,
            youtubeid=youtubeid,
            status=status,
            order=999999,
        )
        db.session.add(new_queue)
        db.session.commit()
    except:
        return False

    reorder_array = []
    counter = {}

    queue = Queue.query.filter_by(roomid=roomid).order_by(Queue.order)

    for queue_item in queue:
        if queue_item.userid in counter:
            counter[queue_item.userid] += 1
        else:
            counter[queue_item.userid] = 1
        if queue_item.status == "P":
            status_int = 0
        else:
            status_int = 1

        reorder_array.append(
            [queue_item, status_int, counter[queue_item.userid], queue_item.order]
        )

    reorder_array.sort(key=lambda x: (x[1], x[2], x[3]))

    counter = 1
    for reorder_item in reorder_array:
        queue_item = reorder_item[0]
        queue_item.order = counter
        counter += 1

    db.session.commit()

    return True


def queue_get(roomid):

    reorder_array = []
    counter = {}

    queue = Queue.query.filter_by(roomid=roomid)

    for queue_item in queue:
        if queue_item.userid in counter:
            counter[queue_item.userid] += 1
        else:
            counter[queue_item.userid] = 1
        if queue_item.status == "P":
            status_int = 0
        elif queue_item.status == "D":
            if check_video(youtubeid=queue_item.youtubeid):
                queue_item.status = ""
                song = Song.query.filter_by(youtubeid=queue_item.youtubeid).first()
                song.downloaded = 1
                db.session.commit()
                status_int = 1
            else:
                status_int = 2
        else:
            status_int = 1

        reorder_array.append(
            [queue_item, status_int, counter[queue_item.userid], queue_item.order]
        )

    reorder_array.sort(key=lambda x: (x[1], x[2], x[3]))

    queue_array = []

    for queue_item in reorder_array:
        try:
            user = User.query.filter_by(id=queue_item[0].userid).first()
            song = Song.query.filter_by(youtubeid=queue_item[0].youtubeid).first()
            song_queue = SongQueue()
            song_queue.id = queue_item[0].id
            song_queue.roomid = queue_item[0].roomid
            song_queue.userid = queue_item[0].userid
            song_queue.status = queue_item[0].status
            song_queue.singer = user.name
            song_queue.youtubeid = queue_item[0].youtubeid
            song_queue.artist = song.artist
            song_queue.song = song.name
            queue_array.append(song_queue)
        except:
            continue

    return queue_array


def lastfm_search(search_arg, lastfm_pass):

    artists = {}
    tracks = []

    url = (
        "https://ws.audioscrobbler.com/2.0/?method=track.search&track="
        + search_arg
        + "&api_key="
        + lastfm_pass
        + "&limit=50&format=json"
    )
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return response.status_code
        data = response.json()

        for results in data["results"]["trackmatches"]["track"]:
            artist = results["artist"].title()
            if not artist in artists:
                artists[artist] = []
            title = results["name"].title()
            if not title in artists[artist]:
                artists[artist].append(title)

        count_id = 0
        for artist in artists:
            for song in artists[artist]:
                music_data = MusicData()
                music_data.id = count_id
                music_data.song = song
                music_data.artist = artist
                tracks.append(music_data)
                count_id += 1
    except:
        return None

    return tracks


def musicbrainz_search(search_arg):

    try:
        index = search_arg.index("-")
        artist_query = search_arg[:index]
        song_query = search_arg[index + 1 :]

    except:
        artist_query = None
        song_query = None

    tracks = []
    artists = {}

    try:
        if artist_query != None and song_query != None:
            result = musicbrainzngs.search_recordings(
                query=search_arg, artist=artist_query, recording=song_query, limit=100
            )
        else:
            result = musicbrainzngs.search_recordings(query=search_arg, limit=100)

        for record in result["recording-list"]:
            score = int(record["ext:score"])
            if score < 50:
                break
            artist = record["artist-credit-phrase"].title()
            if not artist in artists:
                artists[artist] = []
            title = record["title"].title()
            if not title in artists[artist]:
                artists[artist].append(title)

        count_id = 0
        for artist in artists:
            for song in artists[artist]:
                music_data = MusicData()
                music_data = count_id
                music_data.song = song
                music_data.artist = artist
                tracks.append(music_data)
                count_id += 1

    except:
        return None

    return tracks


def is_karaoke(title):

    return (
        "karaok" in title.lower()
        or "videok" in title.lower()
        or "backtracking" in title.lower()
        or "instrumental" in title.lower()
    )


def youtube_search(search_arg):

    replaces = ["&", "/", ".", ";", ",", ":", "?"]

    for replace in replaces:
        search_term = search_arg.replace(replace, " ")
    search_term = search_term + " karaoke"
    videos_search = VideosSearch(search_term, region="BR", language="pt")
    video_list = []

    count = 0
    while count < 5:
        for video in videos_search.resultComponents:
            try:
                if video["type"] != "video":
                    continue
                if not is_karaoke(video["title"]):
                    continue
                youtube_video = YoutubeVideos()
                youtube_video.id = video["id"]
                youtube_video.thumb = video["thumbnails"][0]["url"].split("?")[0]
                youtube_video.description = video["title"]
                video_list.append(youtube_video)
            except:
                continue
        videos_search.next()
        count += 1

    return video_list


def get_player_data(page_load, current_user, updatedb):

    count = 0
    player_data = PlayerData()
    queue = queue_get(roomid=current_user.roomid)

    if page_load:
        playing = Queue.query.filter_by(roomid=current_user.roomid, status="P").first()
        try:
            if playing.status == "P":
                user = User.query.filter_by(id=playing.userid).first()
                song = Song.query.filter_by(youtubeid=playing.youtubeid).first()
                player_data.singer = user.name
                player_data.song = song.name
                player_data.video_url = (
                    "/static/songs/" + str(playing.youtubeid) + ".mp4"
                )
                count += 1
        except:
            1 == 1
    else:
        if updatedb:
            Queue.query.filter_by(roomid=current_user.roomid, status="P").delete()
            db.session.commit()

    while count < 2:
        try:
            queue_item = queue[0]
            if count == 0:
                player_data.singer = queue_item.singer
                player_data.song = queue_item.song
                player_data.video_url = (
                    "/static/songs/" + str(queue_item.youtubeid) + ".mp4"
                )
                if updatedb:
                    queue_update = Queue.query.filter_by(id=queue_item.id).first()
                    queue_update.status = "P"
                    db.session.add(queue_update)
                    db.session.commit()
            else:
                player_data.next_singer = queue_item.singer
                player_data.next_song = queue_item.song
        except:
            break

        del queue[0]
        count += 1

    return player_data


def check_video(youtubeid):

    video_file = APP_PATH + SONGS_DIR + str(youtubeid) + ".mp4"
    if os.path.exists(video_file):
        return True
    else:
        return False


def create_message(
    sender_name, sender_email, recipient, subject, text_content, html_content=None
):
    message = MIMEMultipart("alternative")
    message["From"] = (
        sender_name + " <" + sender_email + ">"
    )  # Set sender name and email
    message["To"] = recipient
    message["Subject"] = subject

    # Add plain text part
    part1 = MIMEText(text_content, "plain")
    message.attach(part1)

    # Add HTML part (optional)
    if html_content:
        part2 = MIMEText(html_content, "html")
        message.attach(part2)

    return message


def send_email(
    sender_name,
    sender_email,
    recipient,
    subject,
    text_content,
    html_content=None,
    smtp_server="localhost",
    smtp_port=25,
    smtp_user=None,
    smtp_password=None,
):
    message = create_message(
        sender_name, sender_email, recipient, subject, text_content, html_content
    )

    try:
        # Connect to the SMTP server (modify server/port as needed)
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            # Start TLS encryption if required by Postfix configuration
            if server.has_extn("STARTTLS"):
                server.starttls()

            # Authenticate if required (check Postfix configuration)
            if smtp_user != "" and smtp_password != "":
                # Replace with your credentials
                server.login(smtp_user, smtp_password)

            server.sendmail(sender_email, recipient, message.as_string())

            return True

    except smtplib.SMTPException as e:
        print(f"Error sending email: {e}")
        return False


def recover_email(user, password):

    # Example usage with a custom sender name
    sender_name = "KaraTube"
    sender_email = os.environ["KARATUBE_EMAIL"]
    recipient_email = user.email
    subject = _("KaraTube Login")
    text_content = (
        _("User:") + " " + str(user.id) + "\n" + _("Password:") + " " + str(password)
    )

    return send_email(
        sender_name=sender_name,
        sender_email=sender_email,
        recipient=recipient_email,
        subject=subject,
        text_content=text_content,
        smtp_server=os.environ["SMTP_SERVER"],
        smtp_port=os.environ["SMTP_PORT"],
        smtp_user=os.environ["SMTP_USER"],
        smtp_password=os.environ["SMTP_PASS"],
    )


def youtube_download(youtubeid):

    video_file = str(youtubeid) + ".mp4"
    video_path = "/app/project/static/songs"
    download_url = YT_BASE_URL + str(youtubeid)

    try:
        YouTube(download_url).streams.first().download(
            output_path=video_path, filename=video_file
        )
        result = True
    except Exception as e:
        result = False

    return result


def youtube_download_async(youtubeid):

    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(os.environ.get("RABBITMQ_HOST"))
        )
        channel = connection.channel()

        channel.queue_declare(queue="youtube_download", durable=True)
        channel.basic_publish(
            exchange="", routing_key="youtube_download", body=youtubeid
        )

        connection.close()
        return True
    
    except Exception as e:
        return False

def youtube_download_api(youtubeid):

    url = 'http://' + os.environ.get("YOUTUBE_DOWNLOAD_HOST") + ':' + os.environ.get("YOUTUBE_DOWNLOAD_PORT") + '/youtube_download/' + youtubeid
    try:
        response = requests.get(url, timeout=10) # Added timeout for robustness
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        response_json = response.json()
        api_response_status = response_json.get("status")
        if api_response_status == "success":
            status = True
        else:
            status = False        
    except Exception as e:
        status = False
    
    return status
