from flask import Blueprint

support = Blueprint('support', __name__, url_prefix="/support")

from . import views
from flask_security import roles_accepted


@support.before_request
@roles_accepted("Support")
def before_request():
    pass