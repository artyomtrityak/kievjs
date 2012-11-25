# -*- encoding: utf-8 -*-
from flask import render_template, request
from flask.ext.security import current_user

from city_lang.core import http

from . import bp
from .models import FlatPage, Speaker


@bp.route("/")
def speakers():
    context = {
        'speakers': Speaker.query.all()
    }
    return render_template('speakers.html', **context)


@bp.route("/partners/")
def partners():
    print 'partners'
    return render_template('partners.html', **{})


@bp.route("/venue/")
def venue():
    return render_template('venue.html', **{})


@bp.route("/organizers/")
def organizers():
    return render_template('organizers.html', **{})


@bp.route("/registration/")
def registration():
    return render_template('registration.html', **{})


def flatpage():
    path = request.path.strip('/')
    page = FlatPage.query.find_one({'slug': path})

    if page is None:
        return render_template('404.html'), http.NOT_FOUND

    if page.registration_required and current_user.is_anonymous():
        return render_template('404.html'), http.NOT_FOUND

    template = page.template_name or 'flatpage.html'

    return render_template(template, page=page)
