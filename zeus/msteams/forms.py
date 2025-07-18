from flask import current_app
from flask_login import current_user
from wtforms import Form, StringField, SelectField
from wtforms.validators import DataRequired
from zeus.exceptions import ZeusCmdError
from zeus.models import OAuthApp, OrgType


def MsTeamsOrgForm(*args, **kwargs):
    """
    Build an OAuth-enabled organization form.

    For MSTeams, all orgs are expected to use the system default
    OAuth App so the select field only contains one item
    """
    choices = get_msteams_oauth_choices()

    class _MsTeamsOrgForm(Form):
        id = StringField("Org Id", render_kw={"hidden": ""})
        name = StringField(
            "Name", validators=[DataRequired("Org Name is Required")], default=""
        )
        oauth_app = SelectField("OAuth App", choices=choices)

    return _MsTeamsOrgForm(*args, **kwargs)


def get_msteams_oauth_choices() -> list[tuple[int, str]]:
    """
    Return OAuthApp choices for an Org form.
    If a default OAuthApp name is set in the Flask Config, the choices
    will only include this one item. Otherwise, the choices will include
    any OAuthApp records with `is_global` = True or that are owned by the current user.

    If no records found, raise a ZeusCmdError
    """
    default_oauth_app = get_default_msteams_oauth_app()
    if default_oauth_app:
        return [(default_oauth_app.id, default_oauth_app.name)]

    oauth_apps = current_user.available_oauth_apps("msteams", include_global=True)

    if not oauth_apps:
        raise ZeusCmdError("No MS Teams OAuth App Records Found")

    return [(app.id, app.name) for app in oauth_apps]


def get_default_msteams_oauth_app() -> OAuthApp | None:
    """
    Return the appropriate Wxcc OAuthApp instance for Org creation.
    If the 'MSTEAMS_OAUTH_APP_NAME' Flask Config variable is set, return
    the record with this name or raise a ZeusCmdError if it does not exist.
    """
    default_oauth_name = current_app.config.get("MSTEAMS_OAUTH_APP_NAME", None)

    if default_oauth_name:
        try:
            default_oauth_app = (
                OAuthApp.query.join(OrgType)
                .filter(OrgType.name == "msteams")
                .filter(OAuthApp.is_global == True)  # noqa
                .filter(OAuthApp.name == default_oauth_name)
            ).one()
        except Exception as exc:
            raise ZeusCmdError(f"Default MS Teams OAuth App: '{default_oauth_name}' does not exist")

        return default_oauth_app

    return None
