from flask import Blueprint, session

wbxc = Blueprint('wbxc', __name__, url_prefix="/wbxc")

from . import views, template_tables
from flask_security import auth_required


@wbxc.before_request
@auth_required()
def before_request():
    """
    Make sure session cookie is always included in response so
    login does not expire for active users
    """
    session.modified = True
