from flask import Blueprint, session

five9 = Blueprint('five9', __name__, url_prefix="/five9")

from . import views, template_tables
from flask_security import auth_required


@five9.before_request
@auth_required()
def before_request():
    """
    Make sure session cookie is always included in response so
    login does not expire for active users
    """
    session.modified = True
