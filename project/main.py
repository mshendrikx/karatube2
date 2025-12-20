import random
import os

from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_babel import gettext as _
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
from .models import User, MobVer
from . import db

from . import scheduler

main = Blueprint("main", __name__)

WHATSAPP_BASE_URL = os.environ.get("WHATSAPP_BASE_URL")
WHATSAPP_API_KEY = os.environ.get("WHATSAPP_API_KEY")
WHATSAPP_SESSION = os.environ.get("WHATSAPP_SESSION")


@main.route("/")
def index():
    return render_template("index.html")


@main.route("/profile")
@login_required
def profile():
    return render_template("profile.html", name=current_user.name)


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
