import random
import os
import qrcode
import io
import base64
import time

from flask_login import login_required, current_user
from urllib.request import urlretrieve
from werkzeug.security import generate_password_hash, check_password_hash
from flask_babel import gettext as _
from pathlib import Path
from flask import (
    Blueprint,
    render_template,
    request,
    flash,
    redirect,
    url_for,
    jsonify,
    session,
)
from .whatsapp_api import (
    whatsapp_get_numberid,
    whatsapp_send_message,
    whatsapp_restart_session,
)
from .models import User, MobVer, Room, Song, Queue, Roomadm, Config, Controls
from . import db

from . import scheduler

from .karatube import (
    lastfm_search,
    youtube_search,
    video_delete,
    queue_add,
    queue_get,
    check_video,
    musicbrainz_search,
    singer_warning,
    youtube_download,
    youtube_download_api,
)

class PlayerData:
    singer = ""
    song = ""
    next_singer = ""
    next_song = ""
    video_url = ""
    artist = ""
    queueid = ""


LOCK_QUEUE = {}
SESSION_MUSICS = {}

main = Blueprint("main", __name__)

WHATSAPP_BASE_URL = os.environ.get("WHATSAPP_BASE_URL")
WHATSAPP_API_KEY = os.environ.get("WHATSAPP_API_KEY")
WHATSAPP_SESSION = os.environ.get("WHATSAPP_SESSION")


@main.route("/")
def index():

    return render_template("index.html", user=current_user)



@main.route("/profile")
@login_required
def profile():

    rooms = []
    rooms.append(current_user.roomid)
    if current_user.admin == "X":
        room_sel = Room.query
    else:
        room_sel = Roomadm.query.filter_by(userid=current_user.id)
    for room in room_sel:
        if room.roomid != current_user.roomid:
            rooms.append(room.roomid)

    return render_template("profile.html", current_user=current_user, rooms=rooms)


@main.route("/profile", methods=["POST"])
@login_required
def profile_post():

    password = request.form.get("password")
    repass = request.form.get("repass")
    name = request.form.get("name")
    email = request.form.get("email")
    mobile = request.form.get("mobile")
    language = request.form.get("lang_selection")
    theme = request.form.get("theme_selection")
    roomid = request.form.get("room_selection")
    warning = request.form.get("warn_selection")

    if password != repass:
        flash(_("Password do not match"))
        flash("alert-danger")
        return redirect(url_for("main.profile"))

    if "@" not in email:
        flash(_("Enter valid E-mail"))
        flash("alert-danger")
        return redirect(url_for("main.profile"))

    if password != "":
        current_user.password = generate_password_hash(password, method="pbkdf2:sha256")

    if name != "":
        current_user.name = name

    current_user.email = email
    current_user.language = language
    current_user.theme = theme
    current_user.roomid = roomid
    current_user.warning = warning

    db.session.add(current_user)
    db.session.commit()

    if mobile != current_user.mobile:
        whatsapp_id = whatsapp_get_numberid(
            base_url=WHATSAPP_BASE_URL,
            api_key=WHATSAPP_API_KEY,
            session=WHATSAPP_SESSION,
            contact=mobile,
        )
        if whatsapp_id is None:
            flash(_("WhatsApp number is not registered"))
            flash("alert-danger")
            return redirect(url_for("main.profile"))
        else:
            current_user.whatsapp_id = whatsapp_id
            db.session.add(current_user)
            db.session.commit()

        mobver = MobVer.query.filter_by(userid=current_user.id).first()
        if mobver:
            mobver.code = str(random.randint(100000, 999999))
        else:
            mobver = MobVer(
                userid=current_user.id,
                mobile=mobile,
                whatsapp_id=whatsapp_id,
                code=str(random.randint(100000, 999999)),
            )
        db.session.add(mobver)
        db.session.commit()

        contacts = [whatsapp_id]
        content = _("Your verification code is: {code}").format(code=mobver.code)
        whatsapp_send_message(
            base_url=WHATSAPP_BASE_URL,
            api_key=WHATSAPP_API_KEY,
            session=WHATSAPP_SESSION,
            contacts=contacts,
            content=content,
            content_type="string",
        )

        return redirect(url_for("main.mobilechange"))

    return redirect(url_for("main.profile"))


@main.route("/mobilechange")
@login_required
def mobilechange():

    return render_template("mobilechange.html")


@main.route("/mobilechange", methods=["POST"])
@login_required
def mobilechange_post():

    mobver = MobVer.query.filter_by(userid=current_user.id).first()
    if not mobver:
        flash(_("No mobile verification request found"))
        flash("alert-danger")
        return redirect(url_for("main.profile"))

    verify = request.form.get("verify")

    if mobver.code == verify:
        current_user.mobile = mobver.mobile
        current_user.whatsapp_id = mobver.whatsapp_id
        db.session.add(current_user)
        db.session.delete(mobver)
        db.session.commit()
        flash(_("Mobile number updated successfully"))
        flash("alert-success")
        return redirect(url_for("main.profile"))
    else:
        flash(_("Verification code does not match"))
        flash("alert-danger")
        return redirect(url_for("main.mobilechange"))

@main.route("/musics")
@login_required
def musics():

    try:
        del SESSION_MUSICS[session["session_id"]]
    except:
        1 == 1

    song_list = Song.query.order_by("artist", "name")
    songs_check = song_list.filter_by(downloaded=0)
    for song_check in songs_check:
        if check_video(youtubeid=song_check.youtubeid):
            song_check.downloaded = 1
            queue = Queue.query.filter_by(youtubeid=song_check.youtubeid)
            for queue_item in queue:
                queue_item.status = ""
            db.session.commit()

    user_sel = []
    user_sel.append(current_user)
    user_list = User.query.filter_by(roomid=current_user.roomid)
    for user in user_list:
        if user.id != current_user.id:
            user_sel.append(user)

    return render_template(
        "musics.html", songs=song_list, user_sel=user_sel, current_user=current_user
    )


@main.route("/musics", methods=["POST"])
@login_required
def musics_post():

    global SESSION_MUSICS

    search_string = request.form.get("search_string")
    singer_user = request.form.get("user_selection")
    config = Config.query.first()
    if config.library == "1":
        musics = lastfm_search(search_string, lastfm_pass=config.lastfm)
    else:
        musics = musicbrainz_search(search_string)

    if musics == None:
        flash(_("No music found in database"))
        flash("alert-warning")
        return redirect(url_for("main.musics"))
    else:
        try:
            SESSION_MUSICS[session["session_id"]] = musics
            return render_template(
                "musicdb.html", musics=musics, singer_user=singer_user
            )
        except Exception as e:
            flash(_("Session expired, please login again"))
            flash("alert-warning")
            return redirect(url_for("auth.logout"))


@main.route("/youtube/<song>/<singer>")
@login_required
def youtube(song, singer):

    song_id = int(song)
    try:
        search_arg = (
            SESSION_MUSICS[session["session_id"]][song_id].artist
            + " "
            + SESSION_MUSICS[session["session_id"]][song_id].song
        )
    except Exception as e:
        flash(_("Error getting song"))
        flash("alert-danger")
        return redirect(url_for("main.musics"))

    youtube_videos = youtube_search(search_arg)
    videos = [video.get_display_data() for video in youtube_videos]

    return render_template(
        "youtube.html",
        videos=videos,
        singer=singer,
        song_id=song_id,
    )


@main.route("/youtubedl/<song>/<id>/<image>/<singer>")
@login_required
def youtubedl(song, id, image, singer):

    result = False

    song_id = int(song)

    song_exists = Song.query.filter_by(youtubeid=id).first()

    if song_exists:
        flash(_("Youtube video alredy downloaded"))
        flash("alert-warning")
    else:
        try:
            downloaded = 0
            #if youtube_download_api(youtubeid=id):
            #    downloaded = 1
            new_song = Song(
                youtubeid=id,
                name=SESSION_MUSICS[session["session_id"]][song_id].song,
                artist=SESSION_MUSICS[session["session_id"]][song_id].artist,
                downloaded=downloaded,
            )
            db.session.add(new_song)
            db.session.commit()
            result = True
            
        except:
            result = False

        if result == True:

            image_url = "https://i.ytimg.com/vi/" + str(id) + "/" + image
            file_name = (
                str(Path(__file__).parent.absolute())
                + "/static/thumbs/"
                + str(id)
                + ".jpg"
            )
            urlretrieve(image_url, file_name)

    return redirect(url_for("main.addqueue", youtubeid=id, userid=singer))


@main.route("/addqueue/<youtubeid>/<userid>")
@login_required
def addqueue(youtubeid, userid):

    global LOCK_QUEUE

    while current_user.roomid in LOCK_QUEUE:
        time.sleep(1)

    LOCK_QUEUE[current_user.roomid] = True

    try:
        queue_check = Queue.query.filter_by(
            userid=current_user.id, youtubeid=youtubeid, roomid=current_user.roomid, created_by=current_user.id
        ).first()
        if queue_check:
            flash(_("Song alredy in queue"))
            flash("alert-warning")
        else:
            if check_video(youtubeid=youtubeid):
                if queue_add(current_user.roomid, userid, youtubeid, "", current_user.id):
                    flash(_("Song added to queue"))
                    flash("alert-success")
                else:
                    flash(_("Fail to add song to queue"))
                    flash("alert-danger")
            else:
                add_song = Song.query.filter_by(youtubeid=youtubeid).first()
                if add_song:
                    if add_song.downloaded == 1:
                        add_song.delete()
                        db.session.commit()
                        flash(_("There is no video file, download again"))
                        flash("alert-danger")
                    else:
                        if queue_add(current_user.roomid, userid, youtubeid, "D", current_user.id):
                            flash(_("Downloading video, wait finish"))
                            flash("alert-warning")
                        else:
                            flash(_("Fail to add song to queue"))
                            flash("alert-danger")
    except:
        flash(_("Fail to add song to queue"))
        flash("alert-danger")

    try:
        del LOCK_QUEUE[current_user.roomid]
    except:
        1 == 1

    return redirect(url_for("main.musics"))


@main.route("/delsong/<youtubeid>")
@login_required
def delsong(youtubeid):

    if current_user.admin == "X":
        if video_delete(youtubeid):
            del_song = Song.query.filter_by(youtubeid=youtubeid).delete()
            db.session.commit()
            if del_song:
                Queue.query.filter_by(youtubeid=youtubeid).delete()
                db.session.commit()
                flash(_("Song deleted"))
                flash("alert-success")
        else:
            flash(_("Song delete fails"))
            flash("alert-danger")
    else:
        flash(_("Only admin can delete song"))
        flash("alert-danger")

    return redirect(url_for("main.musics"))


@main.route("/miniplayer/<youtubeid>")
@login_required
def miniplayer(youtubeid):
    video_url = "/static/songs/" + str(youtubeid) + ".mp4"

    return render_template("miniplayer.html", video_url=video_url)


@main.route("/queue")
@login_required
def queue():

    queue = queue_get(roomid=current_user.roomid)

    return render_template("queue.html", queue=queue, current_user=current_user)


@main.route("/delqueue/<queueid>")
@login_required
def delqueue(queueid):

    global LOCK_QUEUE

    while current_user.roomid in LOCK_QUEUE:
        time.sleep(1)

    LOCK_QUEUE[current_user.roomid] = True

    queue = Queue.query.filter_by(id=queueid).first()

    if queue:
        if current_user.roomadm == "X" or current_user.id == queue.userid:
            order = queue.order
            userid = queue.userid
            roomid = queue.roomid
            status = queue.status
            Queue.query.filter_by(id=queueid).delete()
            db.session.commit()
            if status != "P":
                user_queue = Queue.query.filter_by(
                    roomid=roomid, userid=userid
                ).order_by(Queue.order)
                for user_song in user_queue:
                    if user_song.order > order:
                        order_aux = user_song.order
                        user_song.order = order
                        order = order_aux
                db.session.commit()
            flash(_("Queue deleted"))
            flash("alert-success")
        else:
            flash(_("Only room admin can delete queue"))
            flash("alert-danger")
    else:
        flash(_("Fail to delete queue"))
        flash("alert-danger")

    try:
        del LOCK_QUEUE[current_user.roomid]
    except:
        1 == 1

    return redirect(url_for("main.queue"))


@main.route("/player")
@login_required
def player():

    if current_user.admin != "X":
        roomadm = Roomadm.query.filter_by(
            roomid=current_user.roomid, userid=current_user.id
        ).first()
        if not roomadm:
            flash(_("User is not room admin."))
            flash("alert-danger")
            return redirect(url_for("main.index"))

    room = Room.query.filter_by(roomid=current_user.roomid).first()
    if not room:
        flash(_("Room is not in database."))
        flash("alert-danger")
        return redirect(url_for("main.index"))

    roompass = os.environ.get("ROOM_PASS")
    if roompass == None:
        roompass = os.urandom(4).hex()
        qrcode_data = str(current_user.roomid) + "§" + str(roompass)
    room.password = roompass
    db.session.commit()

    # Create a QR code object with desired error correction level
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L)
    qr.add_data(qrcode_data)
    qr.make(fit=True)
    qrcodeimg = qr.make_image(fill_color="black", back_color="white")
    # Create an in-memory file-like object
    buffer = io.BytesIO()
    qrcodeimg.save(buffer)
    # Get image data as bytes
    image_bytes = buffer.getvalue()
    signup_img = base64.b64encode(image_bytes).decode("utf-8")
    # qrcode_data = str(os.environ.get("KARATUBE_URL")) + "/login"
    qrcode_data = str(os.environ.get("KARATUBE_URL"))
    # Create a QR code object with desired error correction level
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L)
    qr.add_data(qrcode_data)
    qr.make(fit=True)
    qrcodeimg = qr.make_image(fill_color="black", back_color="white")
    # Create an in-memory file-like object
    buffer = io.BytesIO()
    qrcodeimg.save(buffer)
    # Get image data as bytes
    image_bytes = buffer.getvalue()
    login_img = base64.b64encode(image_bytes).decode("utf-8")

    config = Config.query.filter_by(id="CONFIG").first()
    return render_template(
        "player.html",
        player_config=config,
        signup_img=signup_img,
        login_img=login_img,
        room=room,
    )


@main.route("/screenupdate")
@login_required
def screenupdate():

    try:
        first = True
        player_data = PlayerData()
        queue = queue_get(roomid=current_user.roomid)
        for queue_item in queue:

            if first:
                if queue_item.status != "D":
                    player_data.singer = queue_item.singer
                    player_data.song = queue_item.song
                    player_data.artist = queue_item.artist
                    player_data.video_url = (
                        "/static/songs/" + str(queue_item.youtubeid) + ".mp4"
                    )
                    player_data.queueid = str(queue_item.id)
                    if queue_item.status == "":
                        queue_update = Queue.query.filter_by(id=queue_item.id).first()
                        queue_update.status = "P"
                        db.session.commit()
                        singer_warning(queue_item.id)
                first = False
            else:
                player_data.next_singer = queue_item.singer
                player_data.next_song = queue_item.song
                break

    except:
        1 == 1

    control = Controls.query.filter_by(roomid=current_user.roomid).first()
    if control:
        command = control.command
        commvalue = control.commvalue
        Controls.query.filter_by(id=control.id).delete()
        db.session.commit()

    else:
        command = ""
        commvalue = ""

    config = Config.query.filter_by(id="CONFIG").first()
    if config:
        update_ratio = config.updateratio * 1000
    else:
        update_ratio = 1000

    room = Room.query.filter_by(roomid=current_user.roomid).first()
    if room:
        song_interval = room.songint * 1000
    else:
        song_interval = 10000

    return jsonify(
        {
            "video_url": player_data.video_url,
            "singer": player_data.singer,
            "next_singer": player_data.next_singer,
            "song": player_data.song,
            "next_song": player_data.next_song,
            "artist": player_data.artist,
            "queueid": player_data.queueid,
            "command": command,
            "commvalue": commvalue,
            "update_ratio": update_ratio,
            "song_interval": song_interval,
        }
    )


@main.route("/queueupdate")
@login_required
def queueupdate():

    queue_list = queue_get(roomid=current_user.roomid)

    Queue.query.filter_by(roomid=current_user.roomid, status="P").delete()
    db.session.commit()

    try:
        for queue in queue_list:
            if queue.status != "":
                continue
            queue_next = Queue.query.filter_by(id=queue.id).first()
            if queue_next:
                queue_next.status = "P"
                # db.session.add(queue_next)
                db.session.commit()
                singer_warning(queue_next.id)
                break
    except:
        1 == 1

    return jsonify({})


@main.route("/createroom", methods=["POST"])
@login_required
def createroom():

    if current_user.admin == "":
        flash(_("Must be administrator."))
        flash("alert-danger")
        return redirect(url_for("main.index"))

    # login code goes here
    userid = request.form.get("userid")
    roomid = request.form.get("roomid")
    roompass = os.urandom(12).hex()

    user = User.query.filter_by(id=userid).first()
    # check if the user actually exists
    # take the user-supplied password, hash it, and compare it to the hashed password in the database
    if not user:
        flash(_("No user in DB."))
        flash("alert-danger")
        return redirect(
            url_for("main.createroom")
        )  # if the user doesn't exist or password is wrong, reload the page

    room = Room.query.filter_by(roomid=roomid).first()
    # check if the room actually exists
    # take the room-supplied password, hash it, and compare it to the hashed password in the database
    if room:
        flash(_("Room alredy exists."))
        flash("alert-danger")
        return redirect(
            url_for("main.createroom")
        )  # if the room doesn't exist or password is wrong, reload the page

    try:
        new_room = Room(
            roomid=roomid,
            password=generate_password_hash(roompass, method="pbkdf2:sha256"),
            barcode=1,
            songint=10,
        )
        db.session.add(new_room)
        new_roomadm = Roomadm(roomid=roomid, userid=userid)
        db.session.add(new_roomadm)
        db.session.commit()
        flash(_("Room created."))
        flash("alert-success")
    except:
        flash(_("Fail to create Room."))
        flash("alert-danger")

    return redirect(url_for("main.configuration"))


@main.route("/configuration")
@login_required
def configuration():

    if current_user.admin == "":
        flash(_("Must be administrator."))
        flash("alert-danger")
        return redirect(url_for("main.index"))

    config = Config.query.filter_by(id="CONFIG").first()

    users = User.query.all()

    rooms = Room.query.all()

    return render_template(
        "configuration.html",
        current_user=current_user,
        config=config,
        users=users,
        rooms=rooms,
    )


@main.route("/configuration", methods=["POST"])
@login_required
def configuration_post():

    if current_user.admin == "":
        flash(_("Must be administrator."))
        flash("alert-danger")
        return redirect(url_for("main.index"))

    song_library = request.form.get("song_library")
    lastfm = request.form.get("lastfm")
    updateratio = request.form.get("updateratio")
    config = Config.query.filter_by(id="CONFIG").first()
    config.library = song_library
    config.lastfm = lastfm
    config.updateratio = int(updateratio)
    if config.updateratio == 0:
        config.updateratio = 1
    db.session.add(config)
    db.session.commit()

    flash(_("Configuration updated."))
    flash("alert-success")

    return render_template(
        "configuration.html", current_user=current_user, config=config
    )


@main.route("/setcommand/<command>", methods=["POST"])
@login_required
def setcommand(command):

    if current_user.roomadm == "X":
        if command == "qrcode":
            room = Room.query.filter_by(roomid=current_user.roomid).first()
            if room:
                if room.barcode == 1:
                    room.barcode = 0
                else:
                    room.barcode = 1
        elif command == "songint":
            songint = int(request.form.get("songint"))
            if songint == 0:
                songint = 10
            room = Room.query.filter_by(roomid=current_user.roomid).first()
            if room:
                room.songint = songint
        else:
            control = Controls(
                roomid=current_user.roomid, command=command, commvalue=""
            )
            db.session.add(control)
        db.session.commit()

    return redirect(url_for("main.roomcontrol"))


@main.route("/roomcontrol")
@login_required
def roomcontrol():

    if current_user.roomadm != "X":
        flash(_("User must be an administrator."))
        flash("alert-warning")
        return redirect(url_for("main.roomcontrol"))

    room = Room.query.filter_by(roomid=current_user.roomid).first()
    users_sel = User.query.all()

    users = []
    roomadms = []
    for user in users_sel:
        if user.id == current_user.id:
            continue
        roomadm = Roomadm.query.filter_by(
            roomid=current_user.roomid, userid=user.id
        ).first()
        if roomadm:
            user.roomadm = "X"
            roomadms.append(user)
        else:
            user.roomadm = ""
            users.append(user)

    return render_template(
        "room.html",
        current_user=current_user,
        room=room,
        roomadms=roomadms,
        users=users,
        users_sel=users_sel,
    )


@main.route("/volumechange", methods=["POST"])
@login_required
def handle_volume_change():

    volume = request.get_json().get("rangeValue")
    control = Controls(roomid=current_user.roomid, command="vol", commvalue=volume)
    db.session.add(control)
    db.session.commit()

    return "", 204


@main.route("/roomqrcode/<roomid>/<roomkey>")
def roomqrcode(roomid, roomkey):

    room = Room.query.filter_by(roomid=roomid).first()
    if not room:
        flash(_("Room not available."))
        flash("alert-danger")
        return redirect(url_for("main.index"))

    if not check_password_hash(room.password, roomkey):
        flash(_("Wrong key for room, scan room qrcode again."))
        flash("alert-danger")
        return redirect(url_for("main.index"))

    if current_user.is_authenticated:
        update_user = User.query.filter_by(id=current_user.id).first()
        if update_user:
            current_user.roomid = roomid
            update_user.roomid = roomid
            db.session.commit()
            return redirect(url_for("main.profile"))

    return render_template("signup.html", roomid=roomid, roomkey=roomkey)


@main.route("/addroom", methods=["POST"])
@login_required
def addroom():

    userid = request.form.get("userid")
    user = User.query.filter_by(id=userid).first()

    if not user:
        flash(_("User not exist in database."))
        flash("alert-danger")
        return redirect(url_for("main.roomcontrol"))

    user.roomid = current_user.roomid

    if request.form["action"] == "Admin":
        roomadm = Roomadm.query.filter_by(
            roomid=current_user.roomid, userid=user.id
        ).first()
        if roomadm:
            flash(_("User alredy in room."))
            flash("alert-warning")
        else:
            flash(_("User added to room."))
            flash("alert-success")
            new_admin = Roomadm(roomid=current_user.roomid, userid=user.id)
            db.session.add(new_admin)

    db.session.commit()

    return redirect(url_for("main.roomcontrol"))


@main.route("/delroomuser/<userid>")
@login_required
def delroomuser(userid):

    if userid == current_user.id:
        flash(_("Current user can not be removed from room."))
        flash("alert-warning")
    else:
        user = User.query.filter_by(id=userid).first()
        if user:
            Queue.query.filter_by(userid=user.id).delete()
            user.roomid = ""
            db.session.commit()
            flash(_("User removed from room."))
            flash("alert-success")

    return redirect(url_for("main.roomcontrol"))


@main.route("/delroomadm/<userid>")
@login_required
def delroomadm(userid):

    if userid == current_user.id:
        flash(_("Current user can not be removed from administrator."))
        flash("alert-warning")
    else:
        Roomadm.query.filter_by(roomid=current_user.roomid, userid=userid).delete()
        db.session.commit()
        flash(_("User remove from administrator."))
        flash("alert-success")

    return redirect(url_for("main.roomcontrol"))


@main.route("/delroom", methods=["POST"])
@login_required
def delroom():

    if current_user.admin == "":
        flash(_("Must be administrator."))
        flash("alert-danger")
        return redirect(url_for("main.index"))

    # login code goes here
    roomid = request.form.get("delroomid")

    room = Room.query.filter_by(roomid=roomid).delete()

    if not room:
        flash(_("Room not exists."))
        flash("alert-danger")
    else:
        flash(_("Room deleted."))
        flash("alert-success")
        Roomadm.query.filter_by(roomid=roomid).delete()
        Queue.query.filter_by(roomid=roomid).delete()
        users = User.query.filter_by(roomid=roomid)
        for user in users:
            user.roomid = ""

    db.session.commit()

    return redirect(url_for("main.configuration"))


@main.route("/updateuser", methods=["POST"])
@login_required
def updateuser():

    if current_user.admin == "":
        flash(_("Must be administrator."))
        flash("alert-danger")
        return redirect(url_for("main.index"))

    userid = request.form.get("updateuserid")

    user = User.query.filter_by(id=userid).first()

    if not user:
        flash(_("User not exist is database."))
        flash("alert-danger")
        return redirect(url_for("main.configuration"))

    if request.form["action"] == "Reset":
        user.password = generate_password_hash("K4r4tub3", method="pbkdf2:sha256")
        flash(_("Password set to: K4r4tub3"))
        flash("alert-success")
    elif request.form["action"] == "Delete":
        flash(_("User deleted from database."))
        flash("alert-success")
        User.query.filter_by(id=userid).delete()
        Roomadm.query.filter_by(userid=userid).delete()
        Queue.query.filter_by(userid=userid).delete()
    elif request.form["action"] == "Admin":
        if user.admin == "X":
            flash(_("Administrator role removed."))
            flash("alert-success")
            user.admin = ""
        else:
            flash(_("User is set as administrator."))
            flash("alert-success")
            user.admin = "X"

    db.session.commit()

    return redirect(url_for("main.configuration"))


@main.route("/changeroom", methods=["POST"])
@login_required
def changeroom_post():

    roomid = request.form.get("roomid")
    roompass = request.form.get("roompass")

    room = Room.query.filter_by(roomid=roomid).first()

    if roomid == current_user.roomid:
        flash(_("User alredy in room"))
        flash("alert-warning")
    elif not room or room.password != roompass:
        flash(_("Wrong room or room password"))
        flash("alert-danger")
    else:
        flash(_("User room changed"))
        flash("alert-success")
        current_user.roomid = roomid
        db.session.commit()

    return redirect(url_for("main.profile"))


@main.route("/barcode")
@login_required
def barcode():

    room = Room.query.filter_by(roomid=current_user.roomid).first()
    qrcode_data = str(room.roomid) + "§" + str(room.password)
    # Create a QR code object with desired error correction level
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L)
    qr.add_data(qrcode_data)
    qr.make(fit=True)
    qrcodeimg = qr.make_image(fill_color="black", back_color="white")
    # Create an in-memory file-like object
    buffer = io.BytesIO()
    qrcodeimg.save(buffer)
    # Get image data as bytes
    image_bytes = buffer.getvalue()
    signup_img = base64.b64encode(image_bytes).decode("utf-8")

    # qrcode_data = str(os.environ.get("KARATUBE_URL")) + "/login"
    qrcode_data = str(os.environ.get("KARATUBE_URL"))
    # Create a QR code object with desired error correction level
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L)
    qr.add_data(qrcode_data)
    qr.make(fit=True)
    qrcodeimg = qr.make_image(fill_color="black", back_color="white")
    # Create an in-memory file-like object
    buffer = io.BytesIO()
    qrcodeimg.save(buffer)
    # Get image data as bytes
    image_bytes = buffer.getvalue()
    login_img = base64.b64encode(image_bytes).decode("utf-8")

    queue = queue_get(roomid=current_user.roomid)
    counter = 0
    for queue_item in queue:
        if queue_item == "P":
            queue_item.order = 0
        else:
            counter += 1
            queue_item.order = counter

    return render_template(
        "barcode.html", signup_img=signup_img, login_img=login_img, queue=queue
    )