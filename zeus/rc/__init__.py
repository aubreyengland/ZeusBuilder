from flask import Blueprint, session

rc = Blueprint('rc', __name__, url_prefix="/rc")

from . import views
from flask_security import auth_required


@rc.before_request
@auth_required()
def before_request():
    """
    Make sure session cookie is always included in response so
    login does not expire for active users
    """
    session.modified = True
