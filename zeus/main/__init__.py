from flask import Blueprint

main = Blueprint('main', __name__)

from . import views
from flask_security import auth_required


@main.before_request
@auth_required()
def before_request():
    pass
