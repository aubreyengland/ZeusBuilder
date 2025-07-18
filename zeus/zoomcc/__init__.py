from flask import Blueprint, session

zoomcc = Blueprint("zoomcc", __name__, url_prefix="/zoomcc")

from . import views, template_tables
from flask_security import auth_required


@zoomcc.before_request
@auth_required()
def before_request():
    """
    Make sure session cookie is always included in response so
    login does not expire for active users
    """
    session.modified = True
