import datetime
import hashlib
import os
import pymongo

from flask import Flask, redirect, url_for, flash, render_template, \
    request, session, g, make_response
from werkzeug.contrib.fixers import ProxyFix

from api import add_user
from decorators import auth_only
from db import mongo_init
from forms import AuthForm, UserForm
from codes import generate_code, generate_badge

import settings

app = Flask(__name__)
app.config.from_object(settings)

CAMPAIGNS = getattr(settings, "CAMPAIGNS", {})
CONFIRMATION_URL = getattr(settings, "CONFIRMATION_URL", "")
REGISTRATION_URL = getattr(settings, "REGISTRATION_URL", "")
BADGE_TITLE = getattr(settings, "BADGE_TITLE", "")


def bytes_from_file(filename, chunksize=8192):
    with open(filename, "rb") as f:
        while True:
            chunk = f.read(chunksize)
            if chunk:
                for b in chunk:
                    yield b
            else:
                break


@app.route('/api/')
def index():
    return render_template("home.html")


@app.route('/api/confirm/<campaign>/<code>/')
def confirm(campaign, code):
    if CAMPAIGNS.get(campaign) is None:
        flash("Sorry, campaign not found", "alert-error")
        return redirect(url_for("index"))

    users = mongo_init().users
    campaign = CAMPAIGNS.get(campaign)

    user = users.find_one({"internalid": code})

    if not user:
        flash("Sorry, can't find such user", "alert-error")
        return redirect(url_for("index"))

    user[campaign] = "confirmed"
    users.save(user)

    flash(
        "You're successfully confirmed in current campaign",
        "alert-success")
    return redirect(url_for("index"))


@app.route("/api/pass/<reg_id>/")
def pass_registration(reg_id):
    flash("This url only for registration desk at the conference")
    return redirect("{}?query={}".format(
        url_for("registration_deck"), reg_id))


@app.route("/api/login/", methods=['GET', 'POST'])
def sign_in():
    form = AuthForm(request.form)

    if request.method == "POST" and form.validate():
        auth = mongo_init().auth
        user = auth.find_one({"username": form.data.get("username")})

        if not user:
            flash(
                "Sorry, user {username} not found".format(**form.data),
                "alert-error")
            return redirect(url_for("sign_in"))

        username, password = form.data.get("username"), \
            form.data.get("password")

        md5 = hashlib.md5()
        md5.update(password)

        if user["password"] == md5.hexdigest():
            session["username"] = user["username"]
            flash(
                "You're successfully authorized",
                "alert-success")

            return redirect(url_for("registration_deck"))

        return redirect(url_for("registration_deck"))
    return render_template("auth.html", form=form)


@app.route("/api/pass/", methods=['GET', 'POST'])
@auth_only
def registration_deck():
    users_c = mongo_init().users
    query = request.args.get("query", "")
    stats = {
        "passed": users_c.find({"passed": {"$ne": None}}).count(),
        "total": users_c.find({}).count(),
        "confirmed_shake1": users_c.find({"confirmationshake1": {
            "$ne": None}}).count(),
        "confirmed_shake2": users_c.find({"confirmationshake2": {
            "$ne": None}}).count(),

    }

    if not query:
        return render_template("deck.html", stats=stats)

    users = users_c.find({
        "$or": [
            {"name": {"$regex": query}},
            {"registrationid": {"$regex": query}},
            {"company": {"$regex": query}},
            {"email": {"$regex": query}}
        ]
    })

    return render_template(
        "deck.html",
        users=users,
        query=query,
        stats=stats)


@app.route("/api/registration/<action>/<reg_id>/", methods=['GET', 'POST'])
@auth_only
def confirm_pass(action, reg_id):
    query = request.args.get("query", "")
    users = mongo_init().users
    user = users.find_one({"registrationid": reg_id})
    history = mongo_init().history

    if not user:
        flash("User {} not found, sorry".format(reg_id))

    elif action == "confirm":
        user["passed"] = datetime.datetime.now().strftime(
            "%m.%d.%Y %H:%M")

        history.insert({
            "registrationid": reg_id,
            "passed_by": g.user["username"],
            "cancelled_by": None,
            "when": datetime.datetime.now(),
            "query": query})

        flash("Registration successfully confirmed", "alert-success")

    elif action == "cancel":
        history.insert({
            "registrationid": reg_id,
            "passed_by": None,
            "cancelled_by": g.user["username"],
            "when": datetime.datetime.now(),
            "query": query})
        user["passed"] = None
        flash("Registration for {} cancelled".format(reg_id),
              "alert-error")

    users.save(user)
    return redirect("{}?query={}".format(
        url_for("registration_deck"),
        query))


@app.route("/api/details/<reg_id>/", methods=['GET', 'POST'])
@auth_only
def details(reg_id):
    history = mongo_init().history
    query = request.args.get("query", "")
    details = mongo_init().users.find_one({
        "registrationid": reg_id})
    records = history.find({
        "registrationid": reg_id}).sort("when", pymongo.DESCENDING)

    if not details:
        flash("Sorry, can't find user {}".format(reg_id))
        return redirect("{}?query={}".format(
            url_for("registration_deck"), query))

    return render_template(
        "user_details.html",
        details=details,
        records=records)


@app.route("/api/new/", methods=['GET', 'POST'])
@auth_only
def add_new():
    form = UserForm(request.form)
    if request.method == "POST" and form.validate():
        if mongo_init().users.find_one({"email": form.data.get("email")}):
            flash("User with email {} already exist".format(
                form.data.get("email")), "alert-error")
            return render_template("add_new.html", form=form)

        user = add_user(**form.data)
        history = {
            "registrationid": user["registrationid"],
            "passed_by": None,
            "cancelled_by": None,
            "created_by": g.user["username"],
            "when": datetime.datetime.now(),
            "query": None}
        mongo_init().history.insert(history)

        flash("User {name} ({email}) successfully registered".format(
            **user))

        return redirect("{}?query={}".format(
            url_for("registration_deck"),
            user["registrationid"]
        ))

    return render_template(
        "add_new.html", form=form)


@app.route("/api/pdf/<internal_id>.pdf")
@auth_only
def generate_pdf(internal_id):
    # prepare context
    users = mongo_init().users
    user = users.find_one({"internalid": internal_id})

    registration_link = REGISTRATION_URL.format(user["registrationid"])

    code = generate_code(
        registration_link,
        output="build/codes/{}.png".format(internal_id))
    value_or_empty = lambda key: user.get(key, "") or ""

    if not user.get("registrationid", None):
        flash(
            "Skipping user {}, no registration ID".format(user["email"]),
            "alert-error")

        return redirect(url_for("registration_deck"))

    badge = generate_badge(
        title=BADGE_TITLE,
        name=value_or_empty("name").strip(),
        company=value_or_empty("company").strip(),
        position=value_or_empty("position").strip(),
        qr_code=code,
        reg_id=user.get("registrationid"),
        output="build/{}.pdf".format(internal_id))

    response = make_response()
    response.headers['Cache-Control'] = "no-cache"
    response.headers['Content-Type'] = "application/pdf"

    for bytes in bytes_from_file(badge):
        response.stream.write(bytes)
    #response.headers['X-Accel-Redirect'] = "/api/download/{}".format(
    #    os.path.basename(badge))

    return response


# fix for nginx proxy
app.wsgi_app = ProxyFix(app.wsgi_app)

if not app.debug:
    import logging
    from logging.handlers import SMTPHandler
    mail_handler = SMTPHandler('127.0.0.1',
                               'server-error@kyivjs.org.ua',
                               settings.ADMINS, 'KyivJS API Failed')
    mail_handler.setLevel(logging.ERROR)
    app.logger.addHandler(mail_handler)


def main():
    app.run()


if __name__ == '__main__':
    main()
