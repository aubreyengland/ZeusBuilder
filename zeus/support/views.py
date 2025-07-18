import logging
from . import support
from flask import render_template, send_file

log = logging.getLogger(__name__)

ZEUS_LOG_FILE = '/app/zeus/logs/zeus-containers.log'

SUPPORT_OPTIONS = [
    {
        "name": "download",
        "title": "Download Logs",
        "route": "support.download_logs",
        "text": "Download Zeus Logs",
    },
    {
        "name": "display",
        "title": "Display Logs",
        "route": "support.view_logs",
        "text": "Display Zeus Logs",
    }
]


@support.context_processor
def support_ctx():
    return {
        "tool": "support",
        "title": "Support",
        "options": SUPPORT_OPTIONS,
    }


@support.get("/")
def support_home():
    return render_template("support/support_home.html")


@support.route('logs/download', methods=['GET', 'POST'])
def download_logs():
    return send_file(ZEUS_LOG_FILE, as_attachment=True)


@support.route('logs/view', methods=['GET', 'POST'])
def view_logs():
    with open(ZEUS_LOG_FILE, "r") as f:
        content = f.read()
    content = content.replace('\n', '<br>')
    return render_template('support/support_log_view.html', log_messages=content)







