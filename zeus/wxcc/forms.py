from flask import current_app
from flask_login import current_user
from zeus.exceptions import ZeusCmdError
from zeus.models import OAuthApp, OrgType
from wtforms.validators import DataRequired
from wtforms import Form, StringField, SelectField


def WxccOrgForm(*args, **kwargs):
    """
    Build an OAuth-enabled organization form.

    For Wxcc, all orgs are expected to use the system default
    OAuth App so the select field only contains one item
    """

    choices = get_wxcc_oauth_choices()

    class _WxccOrgForm(Form):

        id = StringField("Org Id", render_kw={"hidden": ""})
        name = StringField(
            "Name", validators=[DataRequired("Org Name is Required")], default=""
        )
        oauth_app = SelectField("OAuth App", choices=choices)

    return _WxccOrgForm(*args, **kwargs)


def get_wxcc_oauth_choices() -> list[tuple[int, str]]:
    """
    Return OAuthApp choices for an Org form.
    If a default OAuthApp name is set in the Flask Config, the choices
    will only include this one item. Otherwise, the choices will include
    any OAuthApp records with `is_global` = True or that are owned by the current user.

    If no records found, raise a ZeusCmdError
    """
    default_oauth_app = get_default_wxcc_oauth_app()
    if default_oauth_app:
        return [(default_oauth_app.id, default_oauth_app.name)]

    oauth_apps = current_user.available_oauth_apps("wxcc", include_global=True)

    if not oauth_apps:
        raise ZeusCmdError("No Webex CC OAuth App Records Found")

    return [(app.id, app.name) for app in oauth_apps]


def get_default_wxcc_oauth_app() -> OAuthApp | None:
    """
    Return the appropriate Wxcc OAuthApp instance for Org creation.
    If the 'WXCC_OAUTH_APP_NAME' Flask Config variable is set, return
    the record with this name or raise a ZeusCmdError if it does not exist.
    """
    default_oauth_name = current_app.config.get("WXCC_OAUTH_APP_NAME", None)

    if default_oauth_name:
        try:
            default_oauth_app = (
                OAuthApp.query.join(OrgType)
                .filter(OrgType.name == "wxcc")
                .filter(OAuthApp.is_global == True)  # noqa
                .filter(OAuthApp.name == default_oauth_name)
            ).one()
        except Exception as exc:
            raise ZeusCmdError(f"Default Webex CC OAuth App: '{default_oauth_name}' does not exist")

        return default_oauth_app

    return None
