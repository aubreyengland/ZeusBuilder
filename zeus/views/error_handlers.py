import logging
from flask_security import current_user
from zeus.exceptions import ZeusMailSendError
from flask import request, jsonify, render_template, redirect, url_for, g, session

log = logging.getLogger(__name__)


class ErrVm:
    def __init__(self, code, detail, back_link="/", back_text="Home", support_contact=""):
        self.code = code
        self.detail = detail
        self.back_link = back_link
        self.back_text = back_text
        self.support_contact = support_contact
        self.incident = getattr(g, "audit_id", "")

    @staticmethod
    def is_json_request():
        return all([
            request.accept_mimetypes.accept_json,
            not request.accept_mimetypes.accept_html
        ])

    def json_response(self):
        response = jsonify({'error': self.detail})
        response.status_code = self.code
        return response



def help_page(path):
    vm = ErrVm(code=404, detail="Help Not Available")

    if vm.is_json_request():
        return vm.json_response()

    return render_template("error.html", vm=vm), 404


def forbidden(_):
    if current_user.is_anonymous:
        return redirect(url_for("security.login"))

    vm = ErrVm(code=403, detail="Unauthorized", back_link="/", back_text="Home")

    if vm.is_json_request():
        return vm.json_response()

    return render_template("error.html", vm=vm), 403


def page_not_found(_):
    vm = ErrVm(code=404, detail="Not Found")

    if vm.is_json_request():
        return vm.json_response()

    return render_template("error.html", vm=vm), 404


def internal_server_error(_):
    vm = ErrVm(code=500, detail="Internal Server Error")
    log.exception(f"Unhandled Exception for Request ID: '{vm.incident}'")

    if vm.is_json_request():
        return vm.json_response()

    return render_template("error.html", vm=vm), 500


def mail_send_error(exc: ZeusMailSendError):
    vm = ErrVm(
        code=500,
        detail="Email Could Not Be Sent",
        support_contact="ciscodeldevsupport@il.cdw.com"
    )
    log.exception(f"Mail Send Error for Request ID: '{vm.incident}'")

    if vm.is_json_request():
        return vm.json_response()

    if "register" in request.path or "confirm" in request.path:
        resend_url = url_for("security.send_confirmation")
    elif "reset" in request.path:
        resend_url = url_for("security.forgot_password")
    else:
        resend_url = ""

    # flush any messages as Flask-Security adds them before attempting to send
    # an email. Any success messages likely aren't accurate.
    flashes = session.pop("_flashes", None)

    return render_template(
        "smtp_error.html",
        vm=vm,
        resend_url=resend_url,
    ), 500


def incident_details():
    if hasattr(g, "audit_id"):
        return f"Request ID: {g.audit_id}"
    return ""
