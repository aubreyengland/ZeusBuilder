"""
Zeus Flask Config

All Flask config variables that are customized and/or exposed as environment variables are
documented within the Config class below. For each variable the following information is given:

- What is the source (Flask, a Flask extension or Zeus defined the variable)
- Is an environment variable required, optional or not supported
- How is the value used

Unless otherwise noted, the environment variable name must match the Config attribute name.

Note: An exception will be raised upon import if a value for a required variable isn't found,
therefore, this module should only be imported by the `app.py` file. Any other modules that need
access to config values should get them from `current_app` or read them from `os.getenv`.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import timedelta

dotenv_path = Path.cwd() / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)

NO_VALUE = object()


def getenv(var, default=NO_VALUE):
    val = os.getenv(var, default)
    if val is NO_VALUE:
        raise ValueError(f'"{var}" value not found.')
    return val


def build_db_uri():
    """
    Construct SQLAlchemy DB URI from environment variables.
    Either the full uri must be provided in `DB_URI` or
    the uri will be built from the individual `DB_` variables.
    """
    uri = getenv("DB_URI", "")

    if not uri:
        engine = getenv("DB_ENGINE", "postgresql")
        name = getenv("DB_NAME", "zeus")
        user = getenv("DB_USER", "")
        host = getenv("DB_HOST", "db")
        port = getenv("DB_PORT", "5342")
        password = getenv("DB_PASSWORD", "")

        if engine.lower() == "postgresql":
            uri = f"postgresql://{user}:{password}@{host}:{port}/{name}"
        else:
            uri = f"sqlite:///{name}"

    return uri


logging_defaults = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            }
        },
        "handlers": {
            "stream": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "default",
            },
        },
        "root": {"level": "DEBUG", "handlers": ["stream"]},
    }


class Config:
    # Source: Flask https://flask.palletsprojects.com/en/2.3.x/config/
    # Env Value: Required
    # Signs the Flask session cookie and CSRF tokens
    SECRET_KEY = getenv("SECRET_KEY")

    # Source: Flask-Security https://flask-security-too.readthedocs.io/en/stable/configuration.html
    # Env Value: Required
    # Used to sign salted password hashes
    SECURITY_PASSWORD_SALT = getenv("SECURITY_PASSWORD_SALT")

    # Source: Flask-SQLAlchemy https://flask-sqlalchemy.palletsprojects.com/en/3.0.x/config/
    # Env Value: Required.
    # Either `DB_URI` or all of `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT`
    # must be provided
    SQLALCHEMY_DATABASE_URI = build_db_uri()

    # Source: Zeus
    # Env Value: Required if default is not correct
    # Default is production Docker network value
    REDIS_URL = getenv("REDIS_URL", "redis://redis:6379/0")

    # Source: Flask-Security https://flask-security-too.readthedocs.io/en/stable/configuration.html
    # Env Value: Required unless using mock_smtp server
    # SMTP server/port/tls for Flask-Security emails
    MAIL_SERVER = getenv("MAIL_SERVER", "localhost")
    MAIL_PORT = int(getenv("MAIL_PORT", "25000"))
    MAIL_USE_TLS = getenv("MAIL_USE_TLS", "false").lower() in [
        "true",
        "on",
        "1",
    ]

    # Source: Flask-Security https://flask-security-too.readthedocs.io/en/stable/configuration.html
    # Env Value: Required if SMTP requires authentication
    # SMTP username/password for Flask-Security emails (if necessary)
    MAIL_USERNAME = getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = getenv("MAIL_PASSWORD", "")

    # Source: Zeus
    # Env Value: Required if multiple OAuth apps exist for tool
    # Sets the OAuth app to use when users create an Org.
    WBXC_OAUTH_APP_NAME = getenv("WBXC_OAUTH_APP_NAME", "")
    WXCC_OAUTH_APP_NAME = getenv("WXCC_OAUTH_APP_NAME", "")
    ZOOM_OAUTH_APP_NAME = getenv("ZOOM_OAUTH_APP_NAME", "")
    MSTEAMS_OAUTH_APP_NAME = getenv("MSTEAMS_OAUTH_APP_NAME", "")

    # Source: Zeus
    # Env Value: Required
    # API key for MsTeams location geo coordinates look up
    AZURE_MAPS_API_KEY = getenv("AZURE_MAPS_API_KEY", "")

    # Source: Flask https://flask.palletsprojects.com/en/2.3.x/config/
    # Env Value: Optional. Variable name is `FLASK_DEBUG`
    # Debugging disabled by default for Production config. Enabled for Testing, Development.
    DEBUG = False

    # Source: Flask https://flask.palletsprojects.com/en/2.3.x/config/
    # Env Value: No
    # Enabled only for Testing config. When True, Flask app error handlers do not handle exceptions.
    TESTING = False

    # Source: Flask https://flask.palletsprojects.com/en/2.3.x/config/
    # Env Value: No
    # Sets expiration time on session
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)

    # Source: Flask https://flask.palletsprojects.com/en/2.3.x/config/
    # Env Value: No
    # Allows custom logger settings to be defined per-environment.
    LOGGING = logging_defaults

    # Source: Zeus
    # Env Value: Optional
    # Determines if menu entries for each tool are shown on the navbar and home page.
    ZEUS_APP_FIVE9_ENABLED = getenv("ZEUS_APP_FIVE9_ENABLED", True)
    ZEUS_APP_ZOOM_ENABLED = getenv("ZEUS_APP_ZOOM_ENABLED", True)
    ZEUS_APP_ZOOMCC_ENABLED = getenv("ZEUS_APP_ZOOMCC_ENABLED", False)
    ZEUS_APP_WXCC_ENABLED = getenv("ZEUS_APP_WXCC_ENABLED", True)
    ZEUS_APP_RC_ENABLED = getenv("ZEUS_APP_RC_ENABLED", False)
    ZEUS_APP_MSTEAMS_ENABLED = getenv("ZEUS_APP_MSTEAMS_ENABLED", False)
    ZEUS_APP_WBXC_ENABLED = os.environ.get("ZEUS_APP_WBXC_ENABLED", False)

    # Source: Zeus
    # Env Value: No
    # If True, verify credentials when a Five9 org is created or updated
    ZEUS_APP_FIVE9_CHECK_ORG_AUTH = True

    # Source: Zeus
    # Env Value: Optional
    # Directory on local file system to save uploaded workbooks/prompts
    # Directory needs to exist
    # Not used when uploads are stored in Redis
    ZEUS_APP_UPLOAD_FOLDER = getenv("ZEUS_APP_UPLOAD_FOLDER", "upload")

    # Source: Zeus
    # Env Value: Optional
    # Allows redirect urls to be set to http for unit tests
    ZEUS_REDIR_URL_SCHEME = getenv("ZEUS_REDIR_URL_SCHEME", "https")

    # Source: Zeus
    # Env Value: No
    # Restricts user registration to cdw email addresses.
    ZEUS_ALLOWED_REGISTRATION_DOMAINS = ["cdw.com"]

    # Source: Zeus https://github.com/cdwlabs/zeus/wiki/Job-Queue
    # Env Value: Optional
    # Sets job queue-related timeouts
    RQ_JOB_RUNNING_TIMEOUT = getenv("RQ_JOB_RUNNING_TIMEOUT", 3600)
    RQ_JOB_QUEUED_TTL = getenv("RQ_JOB_QUEUED_TTL", 300)
    RQ_JOB_RESULT_TTL_BROWSE = getenv("RQ_JOB_RESULT_TTL_BROWSE", 60)
    RQ_JOB_RESULT_TTL_EXPORT = getenv("RQ_JOB_RESULT_TTL_EXPORT", 3600)
    RQ_JOB_FAILURE_TTL = getenv("RQ_JOB_FAILURE_TTL", 86400)
    RQ_JOB_CLASS = "zeus.flask_job_queue.ZeusJob"
    RQ_QUEUE_CLASS = "zeus.flask_job_queue.ZeusQueue"

    # Source: Flask-Security https://flask-security-too.readthedocs.io/en/stable/configuration.html
    # Env Value: No
    # Enables user account registration
    SECURITY_REGISTERABLE = True

    # Source: Flask-Security https://flask-security-too.readthedocs.io/en/stable/configuration.html
    # Env Value: No
    # Subject of registration email
    SECURITY_EMAIL_SUBJECT_REGISTER = "Welcome to Zeus"

    # Source: Flask-Security https://flask-security-too.readthedocs.io/en/stable/configuration.html
    # Env Value: No
    # Requires users to confirm their email address when registering
    SECURITY_CONFIRMABLE = True

    # Source: Flask-Security https://flask-security-too.readthedocs.io/en/stable/configuration.html
    # Env Value: No
    # Allow users to change their password
    SECURITY_CHANGEABLE = True

    # Source: Flask-Security https://flask-security-too.readthedocs.io/en/stable/configuration.html
    # Env Value: No
    # Allow users to request a password reset email
    SECURITY_RECOVERABLE = True

    # Source: Flask-Security https://flask-security-too.readthedocs.io/en/stable/configuration.html
    # Env Value: No
    # Enables tracking of logon stats (current/last IP, current/last login time)
    SECURITY_TRACKABLE = True

    # Source: Flask-Security https://flask-security-too.readthedocs.io/en/stable/configuration.html
    # Env Value: No
    # Enable messages for on Flask-Security views
    SECURITY_FLASH_MESSAGES = True

    # Source: Flask-Security https://flask-security-too.readthedocs.io/en/stable/configuration.html
    # Env Value: No
    # Disables the flash message when a user logs in
    SECURITY_MSG_LOGIN = ("", "")

    # Source: Flask-Security https://flask-security-too.readthedocs.io/en/stable/configuration.html
    # Env Value: No
    # Custom error flashed when user registers with an invalid email address
    SECURITY_MSG_INVALID_EMAIL_ADDRESS = ("Invalid @cdw.com email address", "error")

    # Source: Flask-Security https://flask-security-too.readthedocs.io/en/stable/configuration.html
    # Env Value: No
    # Determines where to redirect user after login if no redirect header is present
    SECURITY_POST_LOGIN_VIEW = "main.index"

    # Source: Flask-Security https://flask-security-too.readthedocs.io/en/stable/configuration.html
    # Env Value: No
    # Determines where to redirect user after logout
    SECURITY_POST_LOGOUT_VIEW = "security.login"

    # Source: Flask-Security https://flask-security-too.readthedocs.io/en/stable/configuration.html
    # Env Value: No
    # From address on registration, recovery emails
    MAIL_DEFAULT_SENDER = getenv("MAIL_DEFAULT_SENDER", "no-reply@localhost")

    # Source: FlaskSQLAlchemy https://flask-sqlalchemy.palletsprojects.com/en/3.0.x/config/
    # Env Value: No
    # Verifies DB connection is available before emitting queries
    # See https://docs.sqlalchemy.org/en/20/changelog/migration_12.html
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}


class DevelopmentConfig(Config):
    DEBUG = True

    # Source: Flask-Security
    # Env Value: No
    # Disable validation of email delivery
    SECURITY_EMAIL_VALIDATOR_ARGS = {"check_deliverability": False}


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    SECRET_KEY = "testsecret"
    SECURITY_PASSWORD_SALT = "testsalt"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    LOGGING = {}
    ZEUS_APP_FIVE9_CHECK_ORG_AUTH = False
    ZEUS_REDIR_URL_SCHEME = "http"
    SECURITY_CONFIRMABLE = False

    # Source: Flask-WTF
    # Env Value: No
    # Disabled for testing so POSTs with forms do not require CSRF token
    WTF_CSRF_ENABLED = False

    # Source: Flask-Security
    # Env Value: No
    # Disable validation of email delivery
    SECURITY_EMAIL_VALIDATOR_ARGS = {"check_deliverability": False}

    # Source: Flask-Security
    # Env Value: No
    # Reduce password hashing complexity to speed up tests
    SECURITY_PASSWORD_HASH = "plaintext"
    SECURITY_HASHING_SCHEMES = ["hex_md5"]
    SECURITY_DEPRECATED_HASHING_SCHEMES = []


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    LOGGING = logging_defaults


config_map = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": ProductionConfig,
}
