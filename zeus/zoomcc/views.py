import logging
from zeus.zoomcc import zoomcc
from zeus.shared import helpers
from .forms import ZoomCCOrgForm
from zeus import registry, views as vw
from flask_security import current_user
from zeus.exceptions import ZeusCmdError
from flask import render_template, session
from zeus.models import ProvisioningOrg as Org, OrgType
from zeus.zoomcc.services.shared import ZoomCCSvcClient
from zeus.tokenmgr.zoom import ZoomTokenMgr, TokenMgrError

log = logging.getLogger(__name__)

TOOL = "zoomcc"

ZOOMCC_OPTIONS = [
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
        "text": "View the results of previous ZoomCC organization import events.",
    },
    {
        "name": "orgs",
        "title": "Organizations",
        "route": f"{TOOL}.orgs",
        "active_org_required": False,
        "text": "Create, edit or delete your defined ZoomCC organizations.",
    },
]


@zoomcc.context_processor
def zoomcc_ctx():
    """
    Make commonly-used information available to all templates.
    User orgs are needed by the base template to render the org select dropdown
    Making them always available in the template context removes the need to
    include them in every render_template call.
    """
    user_orgs = current_user.orgs_of_type(TOOL).order_by(Org.name)
    org_type = OrgType.query.filter_by(name=TOOL).first()

    return {
        "tool": TOOL,
        "title": org_type.title,
        "abbr": org_type.abbr,
        "help_url": helpers.tool_help_url(TOOL),
        "orgs": user_orgs,
        "active_org": session.get(f"{TOOL}org"),
        "options": ZOOMCC_OPTIONS,
    }


@zoomcc.get("/")
def zoomcc_home():
    """
    Tool home page with sidebar and dropdown to select active org
    """
    return render_template("tool/home.html")


class ZoomCCBrowseView(vw.BrowseView):
    decorators = [helpers.org_required(f"{TOOL}")]

    @property
    def svc_client(self):
        return ZoomCCSvcClient()

    @property
    def org_credentials(self):
        return zoomcc_org_credentials(self.org_id)


class ZoomCCExportView(vw.ExportView):
    decorators = [helpers.org_required(f"{TOOL}")]

    @property
    def svc_client(self):
        return ZoomCCSvcClient()

    @property
    def org_credentials(self):
        return zoomcc_org_credentials(self.org_id)


class ZoomCCDownloadView(vw.DownloadView):
    decorators = [helpers.org_required(f"{TOOL}")]


class ZoomCCBulkTemplateView(vw.BulkTemplateView):
    decorators = [helpers.org_required(TOOL)]


class ZoomCCBulkUploadView(vw.BulkUploadView):
    decorators = [helpers.org_required(f"{TOOL}")]

    @property
    def svc_client(self):
        return ZoomCCSvcClient()


class ZoomCCBulkSubmitView(vw.BulkSubmitView):
    @property
    def svc_client(self):
        return ZoomCCSvcClient()

    @property
    def org_credentials(self):
        return zoomcc_org_credentials(self.org_id)


def zoomcc_org_credentials(org_id) -> dict:
    token_mgr = ZoomTokenMgr()
    org = current_user.active_org(f"{TOOL}", org_id)
    try:
        return dict(
            access_token=token_mgr.access_token(org=org),
            base_url=org.oauth.api_endpoint,
        )
    except TokenMgrError as exc:
        raise ZeusCmdError(message=f"Connection Failed: {exc.message}")


ZoomCCExportView.register(zoomcc)
ZoomCCDownloadView.register(zoomcc)
ZoomCCBrowseView.register(zoomcc)
ZoomCCBulkUploadView.register(zoomcc)
ZoomCCBulkTemplateView.register(zoomcc)

# Register bulk view for each supported data type
for data_type in registry.get_data_types(TOOL, "bulk"):
    ZoomCCBulkSubmitView.register(zoomcc, data_type)

# Register event views
vw.BulkEventView.register(zoomcc)
vw.EventHistoryView.register(zoomcc)

# Register active org select view
vw.OrgSelectView.register(zoomcc)

# Register org management views
vw.OrgOAuthTabbedListView.register(zoomcc, ZoomTokenMgr)
vw.OrgFormView.register(zoomcc, ZoomCCOrgForm)
vw.OrgCreateView.register(zoomcc, ZoomCCOrgForm)
vw.OrgUpdateView.register(zoomcc, ZoomCCOrgForm)
vw.OrgDeleteView.register(zoomcc)

# Register oauth app management views
vw.OAuthFormView.register(zoomcc)
vw.OAuthCreateView.register(zoomcc)
vw.OAuthUpdateView.register(zoomcc)
vw.OAuthDeleteView.register(zoomcc)
