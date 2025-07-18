import logging
from flask_security import current_user
from zeus.exceptions import ZeusCmdError
from zeus.models import ProvisioningOrg as Org, OAuthApp
from zeus.shared.oauth_form import create_oauth_form, update_oauth_form
from flask import session, request
from .base_views import CRUDUpdateView, CRUDDeleteView, CRUDFormView

log = logging.getLogger(__name__)


class OAuthFormView(CRUDFormView):
    """
    Provides form for user OAuth app update/create requests.

    Registers as:
        methods: POST
        endpoint: `{tool}.orgs_oauth_form`
        rule: `/{tool}/orgs/oauth_form`

    Registration requires:
        tool: 'wbxc', 'zoom', etc.
        template: Optionally, override default template
    """

    def __init__(self, tool, **kwargs):
        super().__init__()
        self.tool = tool
        self.op: str = ""
        self.partial_template = "tool/oauth_form.html"
        self.redirect_view = f"{self.tool}.orgs"
        self.redirect_params = dict(active="oauth")
        self.template = kwargs.get("template") or "tool/tool_modal.html"

    def prepare_record(self, oauth_id):
        self.record = lookup_oauth(oauth_id, self.tool)

    def build_create_form(self):
        self.form = create_oauth_form(self.tool)

    def build_update_form(self):
        self.form = update_oauth_form(request.form, self.tool, obj=self.record)
        if hasattr(self.form, "scopes"):
            self.form.scopes.data = self.record.scopes

    @classmethod
    def register(cls, app, **kwargs):
        view = cls.as_view("orgs_oauth_form", app.name, **kwargs)
        app.add_url_rule("/orgs/oauth_form", view_func=view)


class OAuthUpdateView(CRUDUpdateView):
    """
    Process user Oauth app update request.
    Respond with HX-Redirect to org home page with flashed message.

    Registers as:
        methods: POST
        endpoint: `{tool}.orgs_auth_update`
        rule: `/{tool}/orgs/oauth_update`

    Registration requires:
        tool: 'wbxc', 'zoom', etc.
        template: Optionally, override default template
    """
    op = "update"
    is_modal = True

    def __init__(self, tool, **kwargs):
        super().__init__()
        self.tool = tool
        self.redirect_view = f"{self.tool}.orgs"
        self.redirect_params = dict(active="oauth")
        self.partial_template = "tool/oauth_form.html"
        self.template = kwargs.get("template") or "tool/oauth_form.html"

    def build_form(self):
        self.form = update_oauth_form(request.form, self.tool)

    def prepare_record(self):
        self.record = lookup_oauth(int(self.form.id.data), self.tool)
        self.form.populate_obj(self.record)
        if hasattr(self.form, "scopes"):
            self.record.scopes = self.form.scopes.data

    @classmethod
    def register(cls, app, **kwargs):
        view = cls.as_view("orgs_oauth_update", app.name, **kwargs)
        app.add_url_rule("/orgs/oauth_update", view_func=view)


class OAuthCreateView(CRUDUpdateView):
    """
    Process user OAuth app create request.
    Respond with HX-Redirect to org home page with flashed message.

    Registers as:
        methods: POST
        endpoint: `{tool}.orgs_oauth_create`
        rule: `/{tool}/orgs/oauth_create`

    Registration requires:
        tool: 'wbxc', 'zoom', etc.
        template: Optionally, override default template
    """
    op = "create"
    is_modal = True

    def __init__(self, tool, **kwargs):
        super().__init__()
        self.tool = tool
        self.redirect_view = f"{self.tool}.orgs"
        self.redirect_params = dict(active="oauth")
        self.template = kwargs.get("template") or "tool/oauth_form.html"

    def build_form(self):
        self.form = update_oauth_form(request.form, self.tool)

    def prepare_record(self):
        scopes = self.form.scopes.data if hasattr(self.form, "scopes") else None

        self.record = OAuthApp.create(
            org_type=self.tool,
            name=self.form.name.data,
            is_global=False,
            user=current_user,
            client_id=self.form.client_id.data,
            client_secret=self.form.client_secret.data,
            redirect_uri=self.form.redirect_uri.data,
            api_endpoint=self.form.api_endpoint.data,
            auth_endpoint=self.form.auth_endpoint.data,
            token_endpoint=self.form.token_endpoint.data,
            scopes=scopes,
        )

    @classmethod
    def register(cls, app, **kwargs):
        view = cls.as_view("orgs_oauth_create", app.name, **kwargs)
        app.add_url_rule("/orgs/oauth_create", view_func=view)


class OAuthDeleteView(CRUDDeleteView):
    """
    Process user OAuth app delete request.
    Respond with HX-Refresh header and flashed message.

    Only apps with no associated orgs can be deleted

    Registers as:
        methods: POST
        endpoint: `{tool}.orgs_oauth_delete`
        rule: `/{tool}/orgs/oauth_delete`

    Registration requires:
        tool: 'wbxc', 'zoom', etc.
    """
    def __init__(self, tool, **kwargs):
        super().__init__()
        self.tool = tool
        self.redirect_view = f"{self.tool}.orgs"
        self.redirect_params = dict(active="oauth")

    def prepare_record(self):
        to_delete_id = request.args.get("id")
        self.record = lookup_oauth(to_delete_id, self.tool)
        associated_orgs = Org.query.filter(Org.oauth_id == self.record.id).count()

        if associated_orgs:
            raise ZeusCmdError(f"Cannot delete OAuth with associated Orgs")

    def process(self):
        super().process()

        if self.record.id == session.get(f"{self.tool}org"):
            session.pop(f"{self.tool}org")

    @classmethod
    def register(cls, app, **kwargs):
        view = cls.as_view("orgs_oauth_delete", app.name)
        app.add_url_rule(f"/orgs/oauth_delete", view_func=view)


def lookup_oauth(oauth_id, tool) -> OAuthApp:
    try:
        _id = int(oauth_id)
    except Exception:
        raise ZeusCmdError(f"Invalid OAuth ID: '{oauth_id}'")

    record = OAuthApp.query.filter(OAuthApp.user_id == current_user.id).filter(OAuthApp.id == _id).first()

    if not record:
        raise ZeusCmdError(f"OAuth ID: {_id} Not Found")

    return record
