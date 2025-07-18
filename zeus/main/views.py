import logging
from . import main
from datetime import datetime
from zeus.shared import helpers
from flask import render_template
from zeus import __version__

log = logging.getLogger(__name__)


@main.context_processor
def inject_year():
    return {'now': datetime.utcnow()}


def home_options():
    five9_disabled = not helpers.is_enabled_app("FIVE9")
    msteams_disabled = not helpers.is_enabled_app("MSTEAMS")
    wbxc_disabled = not helpers.is_enabled_app("WBXC")
    wxcc_disabled = not helpers.is_enabled_app("WXCC")
    zoom_disabled = not helpers.is_enabled_app("ZOOM")
    zoomcc_disabled = not helpers.is_enabled_app("ZOOMCC")

    five9_text = (
        "Coming Soon..."
        if five9_disabled
        else "Automate the provisioning of Five9 contact centers."
    )
    msteams_text = (
        "Coming Soon..."
        if msteams_disabled
        else "Import and export entities such as emergency addresses."
    )
    wbxc_text = (
        "Coming Soon..."
        if wbxc_disabled
        else "Import and export tools for Webex Calling."
    )
    wxcc_text = (
        "Coming Soon..."
        if wxcc_disabled
        else "Import and export entities such as skills, queues, and users."
    )
    zoom_text = (
        "Coming Soon..."
        if zoom_disabled
        else "Quickly deploy a Zoom site by using an Excel spreadsheet."
    )
    zoomcc_text = (
        "Coming Soon..."
        if zoomcc_disabled
        else "Quickly provision a Zoom Contact Center site by using an Excel spreadsheet."
    )
    options = [
        {
            "name": "five9",
            "disabled": five9_disabled,
            "route": "five9.five9_home",
            "title": "Five9",
            "text": five9_text,
        },
        {
            "name": "msteams",
            "disabled": msteams_disabled,
            "title": "MS Teams",
            "route": "msteams.msteams_home",
            "text": msteams_text,
        },
        {
            "name": "wbxc",
            "disabled": wbxc_disabled,
            "title": "Webex Calling",
            "route": "wbxc.wbxc_home",
            "text": wbxc_text,
        },
        {
            "name": "wxcc",
            "disabled": wxcc_disabled,
            "title": "Webex Contact Center",
            "route": "wxcc.wxcc_home",
            "text": wxcc_text,
        },
        {
            "name": "zoom",
            "disabled": zoom_disabled,
            "route": "zoom.zoom_home",
            "title": "Zoom Phone",
            "text": zoom_text,
        },
        {
            "name": "zoomcc",
            "disabled": zoomcc_disabled,
            "route": "zoomcc.zoomcc_home",
            "title": "Zoom Contact Center",
            "text": zoomcc_text,
        },
    ]

    return options


@main.route("/main", methods=["GET"])
def index():
    return render_template("index.html", options=home_options())


@main.route("/about", methods=["GET"])
def about():
    """
    Tool about page
    """
    return render_template("about.html", version=__version__)
