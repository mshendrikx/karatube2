import uuid
import os

from flask import Blueprint, current_app, render_template, redirect, url_for, request, flash, session
from flask_wtf import FlaskForm, RecaptchaField
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user
from flask_babel import gettext as _
from .models import User, Room, Roomadm
from .whatsapp_api import whatsapp_send_message, whatsapp_get_numberid
from . import db

WHATSAPP_BASE_URL = os.environ.get("WHATSAPP_BASE_URL")
WHATSAPP_API_KEY = os.environ.get("WHATSAPP_API_KEY")
WHATSAPP_SESSION = os.environ.get("WHATSAPP_SESSION")

auth = Blueprint('auth', __name__)

class RecoverLoginForm(FlaskForm):
    recaptcha = RecaptchaField()
    
@auth.route('/login')
def login():
    return render_template('login.html')

@auth.route('/login', methods=['POST'])
def login_post():
    # login code goes here
    mobile = request.form.get("mobile")
    password = request.form.get('password')
    remember = True if request.form.get('remember') else False

    user = User.query.filter_by(mobile=mobile).first()

    # check if the user actually exists
    # take the user-supplied password, hash it, and compare it to the hashed password in the database
    if not user or not check_password_hash(user.password, password):
        flash(_("Please check your login details and try again."))
        flash("alert-danger")
        return redirect(url_for('auth.login')) # if the user doesn't exist or password is wrong, reload the page

    if user.admin == "X":
        user.roomadm = "X"
    else:
        #roomadm = Roomadm.query.filter_by(roomid=room.roomid, userid=user.id).first()
        roomadm = Roomadm.query.filter_by(roomid=user.roomid, userid=user.id).first()
        try:
            if roomadm.roomid == user.roomid:
                user.roomadm = "X"
            else:
                user.roomadm = ""
        except:
            user.roomadm = ""
            
    # if the above check passes, then we know the user has the right credentials
    login_user(user, remember=remember)
    db.session.add(user)
    db.session.commit()
    
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        
    return redirect(url_for('main.profile'))

@auth.route('/signup')
def signup():
    return render_template('signup.html')

@auth.route("/signup", methods=["POST"])
def signup_post():
    # code to validate and add user to database goes here

    password = request.form.get("password")
    repass = request.form.get("repass")
    name = request.form.get("name")
    email = request.form.get("email")
    mobile = request.form.get("mobile")
    language = request.form.get("lang_selection")
    roomid = request.form.get("roomid")
    roompass = request.form.get("roompass")

    if password != repass:
        flash(_("Password dont match"))
        flash("alert-danger")
        return redirect(url_for("auth.signup"))

    if "@" not in email:
        flash(_("Enter valid E-mail"))
        flash("alert-danger")
        return redirect(url_for("auth.signup"))

    user = User.query.filter_by(
        mobile=mobile
    ).first()  # if this returns a user, then the email already exists in database

    if (
        user
    ):  # if a user is found, we want to redirect back to signup page so user can try again
        flash(_("Phone already registred"))
        flash("alert-danger")
        return redirect(url_for("auth.signup"))

    whatsapp_id = whatsapp_get_numberid(
        base_url=WHATSAPP_BASE_URL,
        api_key=WHATSAPP_API_KEY,
        session=WHATSAPP_SESSION,
        contact=mobile,
    )
    if whatsapp_id is None:
        flash(_("WhatsApp number is not registered"))
        flash("alert-danger")
        return redirect(url_for("auth.signup"))
        
    room = Room.query.filter_by(roomid=roomid).first()

    if not room or room.password != roompass:
        flash(_("Wrong room or room password"))
        flash("alert-danger")
        return redirect(url_for("auth.signup"))

    # create a new user with the form data. Hash the password so the plaintext version isn't saved.
    new_user = User(
        name=name,
        password=generate_password_hash(password, method="pbkdf2:sha256"),
        email=email,
        mobile=mobile,
        admin="",
        whatsapp_id=whatsapp_id,
        language=language,
        theme="dark",
        roomadm="",
        roomid=roomid,
        warning="X",
    )

    # add the new user to the database
    db.session.add(new_user)
    db.session.commit()

    message = _("User created, please login")

    flash(message)
    flash("alert-success")

    return redirect(url_for("auth.login"))

@auth.route("/recoverlogin")
def recoverlogin():
    
    form = RecoverLoginForm()
    return render_template("recoverlogin.html", form=form)


@auth.route("/recoverlogin", methods=["POST"])
def recoverlogin_post():

    mobile = request.form.get("mobile")

    user = User.query.filter_by(mobile=mobile).first()

    if not user:
        flash(_("Phone number don't exist in database."))
        flash("alert-danger")
    else:
        password = os.urandom(4).hex()
        contact_fail = whatsapp_send_message(
            base_url=WHATSAPP_BASE_URL,
            api_key=WHATSAPP_API_KEY,
            session=WHATSAPP_SESSION,
            contacts=[user.whatsapp_id],
            content=_("Your new Karatube password is: "),
            content_type="string",
        )
        contact_fail = whatsapp_send_message(
            base_url=WHATSAPP_BASE_URL,
            api_key=WHATSAPP_API_KEY,
            session=WHATSAPP_SESSION,
            contacts=[user.whatsapp_id],
            content=password,
            content_type="string",
        )        
        if not contact_fail:
            user.password = generate_password_hash(password, method="pbkdf2:sha256")
            db.session.commit()
            flash(_("Recover message has been sent"))
            flash("alert-success")  
        else:
            flash(_("Failed to send recover message. Contact administrator"))
            flash("alert-danger")
            
    return redirect(url_for("auth.login"))


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))
