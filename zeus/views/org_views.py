import logging
from flask_security import current_user
from zeus.exceptions import ZeusCmdError
from zeus.models import ProvisioningOrg as Org, OAuthApp, OrgType
from flask import session, request, make_response, url_for
from .base_views import ToolView, CRUDTableView, CRUDUpdateView, CRUDDeleteView, CRUDFormView

log = logging.getLogger(__name__)


class OrgSelectView(ToolView):
    """
    Set active org session variable when org is selected.
    Fired by htmx trigger on element in sidebar.
    Returns response with HX-Refresh header which tells htmx
    to refresh the page.

    Registers as:
        methods: POST
        endpoint: `{tool}.org_select`
        rule: `/{tool}/org_select`

    Since only the tool name differs for each use, no need
    to subclass this view for each tool.
    """
    def post(self):
        self.process()
        response = make_response()
        response.headers["HX-Refresh"] = "true"

        return response

    def process(self):
        key = f"{self.tool}org"
        org = request.form.to_dict().get(key, "")
        session[key] = org

    @classmethod
    def register(cls, app):
        view = cls.as_view("org_select", app.name)
        app.add_url_rule("/org_select", view_func=view)


class OrgOAuthTabbedListView(CRUDTableView):
    """
    Provides org and user-specific oauth app management tables
    for rendering in a tabbed interface.

    Registers as:
        methods: GET
        endpoint: `{tool}.orgs`
        rule: `/{tool}/orgs`

    Registration requires:
        tool: 'five9', 'zoom', etc.
        token_mgr: TokenMgr class object
        template: Optionally, override default template
    """
    def __init__(self, tool, token_mgr, **kwargs):
        super().__init__()
        self.tool = tool
        self.TokenMgr = token_mgr
        self.org_rows: list = []
        self.oauth_rows: list = []
        self.active_tab = request.args.get("active") or "orgs"
        self.orgs = current_user.orgs_of_type(self.tool.title())
        self.template = kwargs.get("template") or "tool/orgs_and_oauth.html"

    def build_org_table_rows(self):
        refresh_view = f"tokenmgr.{self.tool}_refresh"
        token_mgr = self.TokenMgr()
        for org in self.orgs:
            auth_url = token_mgr.auth_url(state=org.state, oauth_app=org.oauth)
            self.org_rows.append(
                {
                    "id": org.id,
                    "name": org.name,
                    "oauth_app": org.oauth.name,
                    "refresh_expires": org.refresh_expires,
                    "auth_url": auth_url,
                    "refresh_url": url_for(refresh_view, id=org.id),
                }
            )

    def build_oauth_table_rows(self):
        query = (
            OAuthApp.query
            .join(OrgType)
            .filter(OAuthApp.user == current_user)
            .filter(OrgType.name == self.tool)
            .order_by(OAuthApp.name)
        )
        self.oauth_rows = query.all()

    def process(self):
        """
        Get the orgs owned by the current user for display
        in the Zoom/org landing page table.
        """
        self.build_org_table_rows()
        self.build_oauth_table_rows()

    @classmethod
    def register(cls, app, token_mgr, **kwargs):
        view = cls.as_view("orgs", app.name, token_mgr, **kwargs)
        app.add_url_rule("/orgs", view_func=view)


class OrgListView(CRUDTableView):
    """
    Provides org management table with controls to
    manage each row.

    Registers as:
        methods: GET
        endpoint: `{tool}.orgs`
        rule: `/{tool}/orgs`

    Registration requires:
        tool: 'five9', 'zoom', etc.
        token_mgr: TokenMgr class object
        template: Optionally, override default template
    """
    def __init__(self, tool, token_mgr, **kwargs):
        super().__init__()
        self.tool = tool
        self.org_rows: list = []
        self.TokenMgr = token_mgr
        self.orgs = current_user.orgs_of_type(self.tool.title())
        self.template = kwargs.get("template") or "tool/orgs.html"

    def build_table_rows(self):
        refresh_view = f"tokenmgr.{self.tool}_refresh"
        token_mgr = self.TokenMgr()
        for org in self.orgs:
            auth_url = token_mgr.auth_url(state=org.state, oauth_app=org.oauth)
            self.org_rows.append(
                {
                    "id": org.id,
                    "name": org.name,
                    "oauth_app": org.oauth.name,
                    "refresh_expires": org.refresh_expires,
                    "auth_url": auth_url,
                    "refresh_url": url_for(refresh_view, id=org.id),
                }
            )

    @classmethod
    def register(cls, app, token_mgr, **kwargs):
        view = cls.as_view("orgs", app.name, token_mgr, **kwargs)
        app.add_url_rule("/orgs", view_func=view)


class OrgFormView(CRUDFormView):
    """
    Provides form for org update/create requests.

    Registers as:
        methods: POST
        endpoint: `{tool}.orgs_form`
        rule: `/{tool}/orgs/form`

    Registration requires:
        tool: 'five9', 'zoom', etc.
        form_cls: Class object of form for create/edit requests
        template: Optionally, override default template
    """

    def __init__(self, tool, form_cls, **kwargs):
        super().__init__()
        self.tool = tool
        self.form_cls = form_cls
        self.op: str = ""
        self.redirect_view = f"{self.tool}.orgs"
        self.redirect_params = dict(active="orgs")
        self.partial_template = kwargs.get("partial_template") or "tool/orgs_form.html"
        self.template = kwargs.get("template") or "tool/tool_modal.html"

    def prepare_record(self, org_id):
        self.record = lookup_org(org_id, self.tool)

    def build_create_form(self):
        self.form = self.form_cls()

    def build_update_form(self):
        self.form = self.form_cls(request.form, obj=self.record)
        if hasattr(self.form, "oauth_app"):
            self.form.oauth_app.data = str(self.record.oauth_id)

    @classmethod
    def register(cls, app, form_cls, **kwargs):
        view = cls.as_view("orgs_form", app.name, form_cls, **kwargs)
        app.add_url_rule("/orgs/form", view_func=view)


class OrgUpdateView(CRUDUpdateView):
    """
    Process org update request.
    Respond with HX-Redirect to org home page with flashed message.

    Registers as:
        methods: POST
        endpoint: `{tool}.orgs_update`
        rule: `/{tool}/orgs/update`

    Optionally, the view can be subclassed to provide a
    `verify_org_credentials` method to test the provided
    credentials and raise an exception if they are invalid .

    Registration requires:
        tool: 'five9', 'zoom', etc.
        form_cls: Class object of form for create/edit requests
        template: Optionally, override default template
    """
    op = "update"
    is_modal = True

    def __init__(self, tool, form_cls, **kwargs):
        super().__init__()
        self.tool = tool
        self.form_cls = form_cls
        self.redirect_view = f"{self.tool}.orgs"
        self.redirect_params = dict(active="orgs")
        self.template = kwargs.get("template") or "tool/orgs_form.html"

    def build_form(self):
        self.form = self.form_cls(request.form)

    def check_form(self):
        super().check_form()
        self.verify_org_credentials()

    def verify_org_credentials(self):
        pass

    def prepare_record(self):
        self.record = lookup_org(int(self.form.id.data), self.tool)
        self.form.populate_obj(self.record)
        if hasattr(self.form, "oauth_app"):
            self.record.oauth_id = int(self.form.oauth_app.data)

    @classmethod
    def register(cls, app, form_cls, **kwargs):
        view = cls.as_view("orgs_update", app.name, form_cls, **kwargs)
        app.add_url_rule("/orgs/update", view_func=view)


class OrgCreateView(CRUDUpdateView):
    """
    Process org create request.
    Respond with HX-Redirect to org home page with flashed message.

    Registers as:
        methods: POST
        endpoint: `{tool}.orgs_create`
        rule: `/{tool}/orgs/create`

    View must be sub-classed with a `prepare_record` method
    that uses `self.form` to create a ProvisioningOrg record and sets it
    to `self.record`.

    Optionally, the `verify_org_credentials` method can be provided
    to test the provided credentials and raise an exception if they
    are invalid .

    Registration requires:
        tool: 'five9', 'zoom', etc.
        form_cls: Class object of form for create/edit requests
        template: Optionally, override default template
    """
    op = "create"
    is_modal = True

    def __init__(self, tool, form_cls, **kwargs):
        super().__init__()
        self.tool = tool
        self.form_cls = form_cls
        self.redirect_view = f"{self.tool}.orgs"
        self.redirect_params = dict(active="orgs")
        self.template = kwargs.get("template") or "tool/orgs_form.html"

    def build_form(self):
        self.form = self.form_cls(request.form)

    def check_form(self):
        super().check_form()
        self.verify_org_credentials()

    def verify_org_credentials(self):
        pass

    def prepare_record(self):
        Org.create(
            org_type=self.tool,
            user_id=current_user.id,
            name=self.form.name.data,
            oauth_id=self.form.oauth_app.data,
        )

    @classmethod
    def register(cls, app, form_cls, **kwargs):
        view = cls.as_view("orgs_create", app.name, form_cls, **kwargs)
        app.add_url_rule("/orgs/create", view_func=view)


class OrgDeleteView(CRUDDeleteView):
    """
    Process org delete request.
    Respond with HX-Refresh header and flashed message.

    If the deleted org is the active org, clear the session
    cookie.

    Registers as:
        methods: POST
        endpoint: `{tool}.orgs_delete`
        rule: `/{tool}/orgs/delete`

    Registration requires:
        tool: 'five9', 'zoom', etc.
    """
    def __init__(self, tool, **kwargs):
        super().__init__()
        self.tool = tool
        self.redirect_view = f"{self.tool}.orgs"
        self.redirect_params = dict(active="orgs")

    def prepare_record(self):
        to_delete_id = request.args.get("id")
        self.record = lookup_org(to_delete_id, self.tool)

    def process(self):
        super().process()

        if self.record.id == session.get(f"{self.tool}org"):
            session.pop(f"{self.tool}org")

    @classmethod
    def register(cls, app, **kwargs):
        view = cls.as_view("orgs_delete", app.name)
        app.add_url_rule("/orgs/delete", view_func=view)


def lookup_org(org_id, tool) -> Org:
    try:
        org_id = int(org_id)
    except Exception:
        raise ZeusCmdError(f"Invalid Org ID: '{org_id}'")

    org = current_user.active_org(org_type=f"{tool.title()}", org_id=org_id)

    if not org:
        raise ZeusCmdError(f"Org ID: {org_id} Not Found")

    return org
