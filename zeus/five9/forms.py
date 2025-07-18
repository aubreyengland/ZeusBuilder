from wtforms import Form, StringField, PasswordField
from wtforms.validators import InputRequired


class Five9OrgForm(Form):
    id = StringField("Org Id", render_kw={"hidden": ""})
    name = StringField("Name", validators=[InputRequired("Name is required.")])
    api_user = StringField("Username", validators=[InputRequired("Api User is required.")])
    api_password = PasswordField(
        "Password", validators=[InputRequired("Api Password is required.")]
    )
