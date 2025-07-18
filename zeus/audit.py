import re
import logging
from uuid import uuid4
from flask_login import current_user, user_logged_in, user_logged_out
from flask import request, Response, g, session, request_finished, got_request_exception
from flask_security import user_confirmed, user_registered, password_reset, password_changed, user_authenticated

log = logging.getLogger(__name__)


def signal_wrapper(fn):
    """Prevent error signal receiver from breaking app."""
    def inner(sender, *args, **kwargs):
        try:
            fn(sender, *args, **kwargs)
        except Exception:
            log.exception(f"FlaskAudit Signal Logger Failed")

    return inner


class FlaskAudit:
    """
    Registers with signals provided by Flask or plugins to
    to log significant events for audit/troubleshooting purposes.

    Sets a unique ID for each request that can be provided to clients
    when an error occurs for correlation with the logs.
    """
    def __init__(self, app=None):
        """
        app (Flask App)
        request_receivers (dict):  Key is a regular expression that matches a Flask
        or path. Value is a signal receiver callable
        """
        self.app = None
        self.request_receivers = {
            "^/static.*$": null_logger,
            "^/five9.*$": five9_resp_logger,
            ".+": default_resp_logger,
        }
        if app:
            self.init_app(app)

    def init_app(self, app):
        self.app = app

        # Register before request callback to set the audit_id
        self.app.before_request(before_request)

        # Register with request_finished signal to lookup
        # receiver function based on request path
        request_finished.connect(self.log_request_finished, self.app)

        # Register receiver for unhandled exceptions. This only fires if
        # an exception handler does not catch the exception.
        got_request_exception.connect(log_unhandled_exception, self.app)

        # Register receivers for Flask-Login and Flask-Security signals
        user_logged_in.connect(log_user_login, self.app)
        user_authenticated.connect(log_user_login, self.app)
        user_logged_out.connect(log_user_logout, self.app)
        user_registered.connect(log_user_registered, self.app)
        user_confirmed.connect(log_user_confirmed, self.app)
        password_reset.connect(log_pw_reset, self.app)
        password_changed.connect(log_pw_changed, self.app)

    @signal_wrapper
    def log_request_finished(self, sender, response: Response, **kwargs):
        """
        Find the first match receiver based on the request path.
        If a match is found, call it.
        """
        log_fn = self._get_log_fn()
        if log_fn:
            log_fn(sender, response)

    def _get_log_fn(self):
        """
        Return the first match in request_receivers based on
        regex match with the current request path
         """
        path = request.path
        for item, fn in self.request_receivers.items():
            try:
                if re.match(item, path):
                    return signal_wrapper(fn)
            except Exception:
                log.warning(f"Invalid path matcher: '{item}'")

        return None


def before_request():
    """Set a unique ID to display on error pages for correlating to logs"""
    g.audit_id = uuid4().hex[-8:]


def req_details():
    try:
        user = current_user.email
    except Exception:
        user = "NO USER INFO"

    id_ = getattr(g, "audit_id", "NOT SET")

    return (
        f"{id_}, "
        f"{request.remote_addr}, "
        f"{request.method}, "
        f"{request.path}, "
        f"{user}"
    )


def null_logger(*args, **kwargs):
    return


def default_resp_logger(sender, resp: Response):
    sender.logger.debug(
        f"AUDIT RESP, {resp.status}, "
        f"{req_details()}, "
    )


def five9_resp_logger(sender, resp: Response):
    five9org = session.get("five9org", "<NOT SET>")
    sender.logger.debug(
        f"AUDIT RESP, {resp.status}, "
        f"{req_details()}, "
        f"five9org: {five9org}, "
    )


@signal_wrapper
def log_unhandled_exception(sender, exception, **kwargs):
    if exception:
        sender.logger.error(f"AUDIT UNHANDLED EXCEPTION, {req_details()}, ", exc_info=exception)


@signal_wrapper
def log_user_login(sender, user, **kwargs):
    sender.logger.info(f"AUDIT USER LOGIN, {user.email}")


@signal_wrapper
def log_user_logout(sender, user, **kwargs):
    sender.logger.info(f"AUDIT USER LOGOUT, {user.email}")


@signal_wrapper
def log_user_registered(sender, user, **kwargs):
    sender.logger.info(f"AUDIT USER REGISTERED, {user.email}")


@signal_wrapper
def log_user_confirmed(sender, user, **kwargs):
    sender.logger.info(f"AUDIT USER CONFIRMED, {user.email}")


@signal_wrapper
def log_pw_reset(sender, user, **kwargs):
    sender.logger.info(f"AUDIT USER PW RESET, {user.email}")


@signal_wrapper
def log_pw_changed(sender, user, **kwargs):
    sender.logger.info(f"AUDIT USER PW CHANGED, {user.email}")
