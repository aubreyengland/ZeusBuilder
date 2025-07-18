import logging
from . import wxcc
from zeus.models import OrgType
from zeus.shared import helpers
from .forms import WxccOrgForm
from .services import WxccSvcClient
from zeus import registry, views as vw
from flask_security import current_user
from zeus.exceptions import ZeusCmdError
from flask import render_template, session
from zeus.tokenmgr.wxcc import WxccTokenMgr, TokenMgrError

log = logging.getLogger(__name__)

TOOL = "wxcc"
WXCC_OPTIONS = [
    {
        "name": "browse",
        "title": "Browse",
        "route": f"{TOOL}.browse",
        "active_org_required": True,
        "text": "Browse existing objects in the selected organization.",
    },
    {
        "name": "import",
        "title": "Import",
        "route": f"{TOOL}.bulk",
        "active_org_required": True,
        "text": "Import objects from a provisioning workbook into the selected organization.",
    },
    {
        "name": "export",
        "title": "Export",
        "route": f"{TOOL}.export",
        "active_org_required": True,
        "text": "Export existing object from the selected organization to spreadsheet.",
    },
    {
        "name": "events",
        "title": "Import History",
        "route": f"{TOOL}.events",
        "active_org_required": False,
        "text": "View the results of previous Webex CC organization import events.",
    },
    {
        "name": "orgs",
        "title": "Organizations",
        "route": f"{TOOL}.orgs",
        "active_org_required": False,
        "text": "Create, edit or delete your defined Webex CC organizations.",
    },
]


@wxcc.context_processor
def wxcc_ctx():
    """
    Make commonly-used information available to all templates.
    User orgs are needed by the base template to render the org select dropdown
    Making them always available in the template context removes the need to
    include them in every render_template call.
    """
    user_orgs = current_user.orgs_of_type(TOOL)
    org_type = OrgType.query.filter_by(name=TOOL).first()

    return {
        "tool": TOOL,
        "title": org_type.title,
        "abbr": org_type.abbr,
        "help_url": helpers.tool_help_url(TOOL),
        "orgs": user_orgs,
        "active_org": session.get(f"{TOOL}org"),
        "options": WXCC_OPTIONS,
    }


@wxcc.get("/")
def wxcc_home():
    return render_template("tool/home.html")


class WxccBrowseView(vw.BrowseView):
    decorators = [helpers.org_required(TOOL)]

    @property
    def svc_client(self):
        return WxccSvcClient()

    @property
    def org_credentials(self):
        return wxcc_org_credentials(self.org_id)


class WxccDetailView(vw.DetailView):
    decorators = [helpers.org_required(TOOL)]

    @property
    def svc_client(self):
        return WxccSvcClient()

    @property
    def org_credentials(self):
        return wxcc_org_credentials(self.org_id)


class WxccExportView(vw.ExportView):
    decorators = [helpers.org_required(TOOL)]

    @property
    def svc_client(self):
        return WxccSvcClient()

    @property
    def org_credentials(self):
        return wxcc_org_credentials(self.org_id)


class WxccDownloadView(vw.DownloadView):
    decorators = [helpers.org_required(TOOL)]


class WxccBulkTemplateView(vw.BulkTemplateView):
    decorators = [helpers.org_required(TOOL)]


class WxccBulkUploadView(vw.BulkUploadView):
    decorators = [helpers.org_required(TOOL)]

    @property
    def svc_client(self):
        return WxccSvcClient()


class WxccBulkSubmitView(vw.BulkSubmitView):
    @property
    def svc_client(self):
        return WxccSvcClient()

    @property
    def org_credentials(self):
        return wxcc_org_credentials(self.org_id)


def wxcc_org_credentials(org_id) -> dict:
    token_mgr = WxccTokenMgr()
    org = current_user.active_org(TOOL, org_id)
    try:
        return dict(
            access_token=token_mgr.access_token(org=org),
            base_url=org.oauth.api_endpoint,
        )
    except TokenMgrError as exc:
        raise ZeusCmdError(message=f"Connection Failed: {exc.message}")


WxccExportView.register(wxcc)
WxccDownloadView.register(wxcc)
WxccBrowseView.register(wxcc)
WxccDetailView.register(wxcc)
WxccBulkUploadView.register(wxcc)
WxccBulkTemplateView.register(wxcc)

# Register bulk view for each supported data type
for data_type in registry.get_data_types(TOOL, supports="bulk"):
    WxccBulkSubmitView.register(wxcc, data_type)

# Register event views
vw.BulkEventView.register(wxcc)
vw.EventHistoryView.register(wxcc)

# Register active org select view
vw.OrgSelectView.register(wxcc)

# Register org management views
vw.OrgListView.register(wxcc, WxccTokenMgr)
vw.OrgFormView.register(wxcc, WxccOrgForm)
vw.OrgCreateView.register(wxcc, WxccOrgForm)
vw.OrgUpdateView.register(wxcc, WxccOrgForm)
vw.OrgDeleteView.register(wxcc)
