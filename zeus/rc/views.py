from . import rc
from flask import render_template
from flask_security import auth_required


@rc.route("/", methods=["GET"])
def index():
    return render_template("index.html", title="Rc Index")


