from flask import current_app
from flask_login import current_user
from wtforms import Form, StringField, SelectField
from wtforms.validators import DataRequired
from zeus.exceptions import ZeusCmdError
from zeus.models import OAuthApp, OrgType


def ZoomCCOrgForm(*args, **kwargs):
    """
    Build an OAuth-enabled organization form.

    For ZoomCC, users should be allowed to choose global apps
    or Oauth apps they've created.
    """
    choices = get_zoomcc_oauth_choices()

    class _ZoomCCOrgForm(Form):
        id = StringField("Org Id", render_kw={"hidden": ""})
        name = StringField(
            "Name", validators=[DataRequired("Org Name is Required")], default=""
        )
        oauth_app = SelectField("OAuth App", choices=choices)

    return _ZoomCCOrgForm(*args, **kwargs)


def get_zoomcc_oauth_choices() -> list[tuple[int, str]]:
    """
    Return OAuthApp records owned by the current user.

    If no records found, raise a ZeusCmdError
    """
    oauth_apps = current_user.available_oauth_apps("zoomcc", include_global=False)

    if not oauth_apps:
        raise ZeusCmdError("No Zoom CC OAuth App Records Found")

    return [(app.id, app.name) for app in oauth_apps]
