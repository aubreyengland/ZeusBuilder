from flask import url_for, current_app
from zeus.shared.helpers import deep_get
from zeus.models import User, Role, OAuthApp, OrgType, User
from flask_login import current_user
from sqlalchemy.sql.operators import ilike_op
from wtforms.validators import DataRequired, StopValidation, Optional
from zeus.shared.helpers import FirstLastConfirmRegisterForm
from wtforms import (
    Form,
    StringField,
    SelectMultipleField,
    EmailField,
    BooleanField,
    SelectField,
)
from ..tokenmgr.msteams import MSTEAMS_OAUTH_DEFAULTS
from ..tokenmgr.wxcc import WXCC_OAUTH_DEFAULTS
from ..tokenmgr.wbxc import WBXC_OAUTH_DEFAULTS
from ..tokenmgr.zoom import ZOOM_OAUTH_DEFAULTS


def admin_role_validator(form, field):
    """
    Form field validator that ensures a user update does not
    remove the Admin role from the last user.
    """
    admin_role = Role.query.filter_by(name="Admin").first()

    # If Admin role doesn't exist, fail open
    if not admin_role:
        return

    # if user references in the form does not exist, fail open
    user = User.query.filter_by(email=form.email.data).first()
    if not user:
        return

    # If user is not currently and admin, validation succeeds
    if admin_role not in user.roles:
        return

    # If Admin role is selected, validation succeeds
    if str(admin_role.id) in [f[0] for f in field.data]:
        return

    # If Admin role is to be removed, check for another active
    # user with the Admin role
    for admin_user in admin_role.users:
        if all(
            [
                admin_user != user,
                admin_user.confirmed_at,
                admin_user.active,
            ]
        ):
            return

    # No other active, confirmed account with Admin role exists.
    raise StopValidation(f"Cannot remove 'Admin' role from only active admin account")


def role_name_validator(form, field):
    role_name = field.data
    if Role.query.filter(ilike_op(Role.name, role_name)).count():
        raise StopValidation(f"Role '{role_name}' already exists")


def admin_membership_validator(form, field):
    if form.name.data == "Admin" and not field.data:
        raise StopValidation("Admin role must have at least one member")


def create_user_form(*args, **kwargs):
    """
    Create form based on user registration from to leverage the same
    validation. Adds switch fields to active and confirm the user and a
    multiselect to assign roles
    """
    role_choices = [(str(r.id), r.name) for r in Role.query]

    class CreateForm(FirstLastConfirmRegisterForm):
        id = StringField("User Id", render_kw={"hidden": ""})
        active = BooleanField("Enabled", render_kw={"role": "switch"})
        confirmed = BooleanField("Confirmed", render_kw={"role": "switch"})
        roles = SelectMultipleField("Roles", choices=role_choices)

    return CreateForm(*args, **kwargs)


def update_user_form(formdata, **kwargs):
    """
    Update form is dynamically constructed to:
    - set role choices based on current roles in database
    - Prevent current user from deactivating their account
    - Prevent removal of Admin role if no other Admin account exists
    """
    # Replace empty formdata dict with None so Form constructor will
    # use `obj` in kwargs to populate fields.
    if not formdata:
        formdata = None

    switch_kw = {"role": "switch"}

    if kwargs.get("obj") == current_user:
        switch_kw = {"role": "switch", "disabled": ""}

    role_choices = [(str(r.id), r.name) for r in Role.query]

    class UpdateForm(Form):
        id = StringField("User Id", render_kw={"hidden": ""})
        email = EmailField("Email", render_kw={"readonly": ""})
        first_name = StringField("First Name", validators=[DataRequired()])
        last_name = StringField("Last Name", validators=[DataRequired()])
        active = BooleanField("Enabled", render_kw=switch_kw)
        confirmed = BooleanField("Confirmed", render_kw=switch_kw)
        roles = SelectMultipleField(
            "Roles", choices=role_choices, validators=[admin_role_validator]
        )

    form = UpdateForm(formdata, **kwargs)
    return form


class RoleForm(Form):
    id = StringField("Role Id", render_kw={"hidden": ""})
    name = StringField("Name", validators=[DataRequired()])
    users = SelectMultipleField(
        "Assigned Users", choices=[], validators=[admin_membership_validator]
    )


def role_form(*args, **kwargs):
    form = RoleForm(*args, **kwargs)
    form.users.choices = [(str(u.id), u.email) for u in User.query]
    return form


def oauth_org_choices():
    choices = [("", "--Org Type--")]
    oauth_org_types = OrgType.query.filter_by(is_oauth=True).order_by(OrgType.name)
    for record in oauth_org_types:
        choices.append((record.name, record.title))
    return choices


def oauth_owner_choices():
    choices = [("", "--Owner--")]
    oauth_owners = User.query.order_by(User.email)
    for record in oauth_owners:
        choices.append((record.id, record.email))
    return choices


def oauth_name_validator(form, field):
    """
    Ensure name is unique for records with the same user id or globally.

    Name must be unique for records owned by the same user.
    Names must also be unique between all global OAuth records (those without
    a user id).
    """
    name = field.data

    if form.user.data:
        existing_for_owner = OAuthApp.query.filter(OAuthApp.user_id == form.user.data)
    else:
        existing_for_owner = OAuthApp.query.filter(OAuthApp.user_id.is_(None))

    if form.id.data:
        existing_for_owner = existing_for_owner.filter(OAuthApp.id != form.id.data)

    if existing_for_owner.filter(ilike_op(OAuthApp.name, name)).count():
        raise StopValidation(f"OAuth App '{name}' already exists")


def oauth_owner_validator(form, field):
    """Ensure user is provided if is_global is false"""
    if not form.is_global.data and not field.data:
        raise StopValidation(message="User must be selected if 'Global' is disabled.")


class OAuthFormBase(Form):
    id = StringField("OAuth App Id", render_kw={"hidden": ""})
    name = StringField(
        "Name", validators=[DataRequired(), oauth_name_validator], default=""
    )
    org_type = SelectField("Org Type", choices=oauth_org_choices)
    is_global = BooleanField("Global", render_kw={"role": "switch"})
    user = SelectField("Owner", choices=oauth_owner_choices, validators=[oauth_owner_validator, Optional()])
    client_id = StringField("Client ID", validators=[DataRequired()])
    client_secret = StringField("Client Secret", validators=[DataRequired()])
    redirect_uri = StringField("Redirect URI", validators=[DataRequired()])
    api_endpoint = StringField("API Endpoint", validators=[DataRequired()])
    auth_endpoint = StringField("Auth Endpoint", validators=[DataRequired()])
    token_endpoint = StringField("Refresh Endpoint", validators=[DataRequired()])


class OAuthFormWithScopes(OAuthFormBase):
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
        form = OAuthFormWithScopes(*args, **kwargs)
        form.scopes.choices = scopes
    else:
        form = OAuthFormBase(*args, **kwargs)

    return form


def update_oauth_form(formdata, org_type, **kwargs):
    # Replace empty formdata dict with None so Form constructor will
    # use `obj` in kwargs to populate fields.
    if not formdata:
        formdata = None

    form = build_oauth_form(org_type, formdata, **kwargs)
    form.org_type.data = org_type
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
    if not org_type:
        form = OAuthFormBase(*args, **kwargs)
    else:
        form = build_oauth_form(org_type, *args, **kwargs)

        if hasattr(form, "scopes"):
            form.scopes.data = form.scopes.choices

        scheme = current_app.config.get("ZEUS_REDIR_URL_SCHEME") or "https"
        redir_uri = url_for(
            f"tokenmgr.{org_type.lower()}_redir", _external=True, _scheme=scheme
        )
        form.org_type.data = org_type
        form.redirect_uri.data = redir_uri

        defaults = OAUTH_DEFAULTS[org_type.lower()]
        form.api_endpoint.data = defaults["api_endpoint"]
        form.auth_endpoint.data = defaults["auth_endpoint"]
        form.token_endpoint.data = defaults["token_endpoint"]

    return form
