"""
Zeus is an engineering tool portal for cloud-based UCaaS and CCaaS platforms.
"""

import jinja_partials
from flask_mail import Mail
from .audit import FlaskAudit
from zeus.shared import helpers
from sqlalchemy import MetaData
from flask_migrate import Migrate
from .flask_job_queue import JobQueue
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, redirect, url_for
from flask_security import Security, SQLAlchemyUserDatastore


convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)

db = SQLAlchemy(metadata=metadata)
mail = Mail()
migrate = Migrate()
security = Security()
flask_audit = FlaskAudit()
job_queue = JobQueue()


def create_app(config_name="production"):
    from .config import config_map
    cfg = config_map[config_name]

    # Configure loggers based on Flask config before app is created
    init_logging(cfg)

    app = Flask(__name__)
    app.config.from_object(cfg)

    mail.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)
    flask_audit.init_app(app)
    job_queue.init_app(app)

    init_security(app)
    init_views(app)
    init_templates(app)

    return app


def init_logging(cfg):
    import logging
    from logging.config import dictConfig

    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.INFO)
    logging.getLogger("flask").setLevel(logging.WARNING)
    logging.getLogger("zeep").setLevel(logging.WARNING)
    logging.getLogger("passlib").setLevel(logging.WARNING)
    logging.getLogger("watchdog").setLevel(logging.WARNING)
    logging.getLogger("fsevents").setLevel(logging.WARNING)

    if cfg.LOGGING:
        dictConfig(cfg.LOGGING)
        logging.getLogger(__name__).info(
            f"---- Logging initialized from {type(cfg).__name__} ----"
        )


def init_views(app):
    from .views import error_handlers
    from .main import main as main_blueprint
    from .admin import admin as admin_blueprint
    from .five9 import five9 as five9_blueprint
    from .support import support as support_blueprint
    from .msteams import msteams as msteams_blueprint
    from .rc import rc as rc_blueprint
    from .wxcc import wxcc as wxcc_blueprint
    from .wbxc import wbxc as wbxc_blueprint
    from .zoom import zoom as zoom_blueprint
    from .zoomcc import zoomcc as zoomcc_blueprint
    from .tokenmgr import tokenmgr as tokenmgr_blueprint
    from zeus.exceptions import ZeusMailSendError

    def index():
        """application root with no auth"""
        return redirect(url_for("main.index"))

    # Register the index view and error handlers
    app.add_url_rule("/", view_func=index)
    app.add_url_rule("/help/<path:path>", view_func=error_handlers.help_page)
    app.register_error_handler(403, error_handlers.forbidden)
    app.register_error_handler(404, error_handlers.page_not_found)
    app.register_error_handler(500, error_handlers.internal_server_error)
    app.register_error_handler(ZeusMailSendError, error_handlers.mail_send_error)

    # Register blueprints
    app.register_blueprint(main_blueprint)
    app.register_blueprint(admin_blueprint)
    app.register_blueprint(five9_blueprint)
    app.register_blueprint(msteams_blueprint)
    app.register_blueprint(rc_blueprint)
    app.register_blueprint(support_blueprint)
    app.register_blueprint(wxcc_blueprint)
    app.register_blueprint(wbxc_blueprint)
    app.register_blueprint(zoom_blueprint)
    app.register_blueprint(zoomcc_blueprint)
    app.register_blueprint(tokenmgr_blueprint)


def init_security(app):
    from .models import User, Role

    user_datastore = SQLAlchemyUserDatastore(db, User, Role)
    security.init_app(
        app,
        user_datastore,
        mail_util_cls=helpers.ZeusMailUtil,
        register_form=helpers.FirstLastRegisterForm,
        confirm_register_form=helpers.FirstLastConfirmRegisterForm,
    )


def init_templates(app):
    jinja_partials.register_extensions(app)
    helper_fn = {
        "len": len,
        "navbar_options": nav_options,
        "data_type_actions": helpers.actions_for_data_type,
    }
    app.jinja_env.globals.update(**helper_fn)


def nav_options():
    """
    Return dictionaries for navbar menu options.
    Each returned dictionary defines an option on the navbar.

    The presence of the 'route' key indicates a nav-link.
    The presence of the `dropdown` key indicates a dropdown menu.
    """
    zoom_dropdown = [
        {
            "name": "zoomcc",
            "title": "Zoom CC",
            "route": "zoomcc.zoomcc_home",
            "include": helpers.is_enabled_app("ZOOMCC"),
        },
        {
            "name": "zoom",
            "title": "Zoom Phone",
            "route": "zoom.zoom_home",
            "include": helpers.is_enabled_app("ZOOM"),
        },
    ]
    webex_dropdown = [
        {
            "name": "wbxc",
            "title": "Webex Calling",
            "route": "wbxc.wbxc_home",
            "include": helpers.is_enabled_app("WBXC"),
        },
        {
            "name": "wxcc",
            "title": "Webex Contact Center",
            "route": "wxcc.wxcc_home",
            "include": helpers.is_enabled_app("WxCC"),
        },
    ]
    return [
        {
            "name": "five9",
            "title": "Five9",
            "route": "five9.five9_home",
            "include": helpers.is_enabled_app("FIVE9"),
        },
        {
            "name": "msteams",
            "title": "MS Teams",
            "route": "msteams.msteams_home",
            "include": helpers.is_enabled_app("MSTEAMS"),
        },
        {
            "name": "rc",
            "title": "RingCentral",
            "route": "rc.rc_home",
            "include": helpers.is_enabled_app("RC"),
        },
        {
            "name": "webex",
            "title": "Webex",
            "dropdown": webex_dropdown,
            "include": any(w["include"] for w in webex_dropdown),
        },
        {
            "name": "zoom",
            "title": "Zoom",
            "dropdown": zoom_dropdown,
            "include": any(z["include"] for z in zoom_dropdown),
        },
        {
            "name": "admin",
            "title": "Admin",
            "route": "admin.admin_home",
            "include": helpers.has_all_roles("Admin"),
        },
        {
            "name": "support",
            "title": "Support",
            "route": "support.support_home",
            "include": helpers.has_all_roles("Support"),
        },
    ]
