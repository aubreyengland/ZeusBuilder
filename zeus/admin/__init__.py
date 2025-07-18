from flask import Blueprint

admin = Blueprint('admin', __name__, url_prefix="/admin")

from . import views
from flask_security import roles_accepted


@admin.before_request
@roles_accepted("Admin")
def before_request():
    pass
