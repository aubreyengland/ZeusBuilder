from flask import url_for, current_app
from flask_login import current_user
from zeus.shared.helpers import deep_get
from zeus.models import OAuthApp
from sqlalchemy.sql.operators import ilike_op
from wtforms.validators import DataRequired, StopValidation
from wtforms import (
    Form,
    StringField,
    SelectMultipleField,
)
from ..tokenmgr.msteams import MSTEAMS_OAUTH_DEFAULTS
from ..tokenmgr.wxcc import WXCC_OAUTH_DEFAULTS
from ..tokenmgr.wbxc import WBXC_OAUTH_DEFAULTS
from ..tokenmgr.zoom import ZOOM_OAUTH_DEFAULTS


def oauth_name_validator(form, field):
    if not form.id.data:
        name = field.data
        if OAuthApp.query.filter(ilike_op(OAuthApp.name, name)).filter(OAuthApp.user_id == current_user.id).count():
            raise StopValidation(f"OAuth App '{name}' already exists")


class UserOAuthFormBase(Form):
    id = StringField("OAuth App Id", render_kw={"hidden": ""})
    name = StringField(
        "Name", validators=[DataRequired(), oauth_name_validator], default=""
    )
    client_id = StringField("Client ID", validators=[DataRequired()])
    client_secret = StringField("Client Secret", validators=[DataRequired()])
    redirect_uri = StringField("Redirect URI", validators=[DataRequired()])
    api_endpoint = StringField("API Endpoint", validators=[DataRequired()])
    auth_endpoint = StringField("Auth Endpoint", validators=[DataRequired()])
    token_endpoint = StringField("Refresh Endpoint", validators=[DataRequired()])


class UserOAuthFormWithScopes(UserOAuthFormBase):
    scopes = SelectMultipleField("Scopes", choices=[], validators=[DataRequired()])


OAUTH_DEFAULTS = {
    "wbxc": WBXC_OAUTH_DEFAULTS,
    "wxcc": WXCC_OAUTH_DEFAULTS,
    "zoom": ZOOM_OAUTH_DEFAULTS,
    "zoomcc": ZOOM_OAUTH_DEFAULTS,
    "msteams": MSTEAMS_OAUTH_DEFAULTS,

}


def build_oauth_form(org_type, *args, **kwargs):
    """
    Create an OauthForm with or without a scopes field based
    on the org typ defaults
    """
    scopes = deep_get(OAUTH_DEFAULTS, f"{org_type.lower()}.scopes", default=None)
    if scopes:
        form = UserOAuthFormWithScopes(*args, **kwargs)
        form.scopes.choices = scopes
    else:
        form = UserOAuthFormBase(*args, **kwargs)

    return form


def update_oauth_form(formdata, org_type, **kwargs):
    # Replace empty formdata dict with None so Form constructor will
    # use `obj` in kwargs to populate fields.
    if not formdata:
        formdata = None
    form = build_oauth_form(org_type, formdata, **kwargs)
    return form


def create_oauth_form(org_type, *args, **kwargs):
    """
    Build the OAuth create form.
    When the user clicks **New** this function is called with org_type="".
    OAuthFormBase will be returned with a select field to choose the org type.
    This will trigger an ajax request that will call this function again with
    the selected org_type so a form can be customized with the defaults for the
    org_type.
    """
    form = build_oauth_form(org_type, *args, **kwargs)

    if hasattr(form, "scopes"):
        form.scopes.data = form.scopes.choices

    scheme = current_app.config.get("ZEUS_REDIR_URL_SCHEME") or "https"
    redir_uri = url_for(
        f"tokenmgr.{org_type.lower()}_redir", _external=True, _scheme=scheme
    )
    form.redirect_uri.data = redir_uri

    defaults = OAUTH_DEFAULTS[org_type.lower()]
    form.api_endpoint.data = defaults["api_endpoint"]
    form.auth_endpoint.data = defaults["auth_endpoint"]
    form.token_endpoint.data = defaults["token_endpoint"]

    return form
