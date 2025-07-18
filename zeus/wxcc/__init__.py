from flask import Blueprint, session

wxcc = Blueprint('wxcc', __name__, url_prefix="/wxcc")

from . import views, template_tables
from flask_security import auth_required


@wxcc.before_request
@auth_required()
def before_request():
    """
    Make sure session cookie is always included in response so
    login does not expire for active users
    """
    session.modified = True
