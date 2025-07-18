from flask import Blueprint

tokenmgr = Blueprint("tokenmgr", __name__, url_prefix="/tokenmgr")

from . import views
