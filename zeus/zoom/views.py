import logging
from zoom import zoom
from .forms import ZoomOrgForm
from zeus.shared import helpers
from zeus import registry, views as vw
from flask_security import current_user
from zeus.exceptions import ZeusCmdError
from flask import render_template, session
from zoom.services.shared import ZoomSvcClient
from zeus.models import ProvisioningOrg as Org, OrgType
from zeus.tokenmgr.zoom import ZoomTokenMgr, TokenMgrError

log = logging.getLogger(__name__)

TOOL = "zoom"
ZOOM_OPTIONS = [
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
        "text": "View the results of previous Zoom organization import events.",
    },
    {
        "name": "orgs",
        "title": "Organizations",
        "route": f"{TOOL}.orgs",
        "active_org_required": False,
        "text": "Create, edit or delete your defined Zoom organizations.",
    },
]


@zoom.context_processor
def zoom_ctx():
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
        "options": ZOOM_OPTIONS,
    }


@zoom.get("/")
def zoom_home():
    """
    Tool home page with sidebar and dropdown to select active org
    """
    return render_template("tool/home.html")


class ZoomBrowseView(vw.BrowseView):
    decorators = [helpers.org_required(TOOL)]

    @property
    def svc_client(self):
        return ZoomSvcClient()

    @property
    def org_credentials(self):
        return zoom_org_credentials(self.org_id)


class ZoomDetailView(vw.DetailView):
    decorators = [helpers.org_required(TOOL)]

    @property
    def svc_client(self):
        return ZoomSvcClient()

    @property
    def org_credentials(self):
        return zoom_org_credentials(self.org_id)


class ZoomExportView(vw.ExportView):
    decorators = [helpers.org_required(TOOL)]

    @property
    def svc_client(self):
        return ZoomSvcClient()

    @property
    def org_credentials(self):
        return zoom_org_credentials(self.org_id)


class ZoomDownloadView(vw.DownloadView):
    decorators = [helpers.org_required(TOOL)]


class ZoomBulkTemplateView(vw.BulkTemplateView):
    decorators = [helpers.org_required(TOOL)]


class ZoomBulkUploadView(vw.BulkUploadView):
    decorators = [helpers.org_required(TOOL)]

    @property
    def svc_client(self):
        return ZoomSvcClient()


class ZoomBulkSubmitView(vw.BulkSubmitView):
    @property
    def svc_client(self):
        return ZoomSvcClient()

    @property
    def org_credentials(self):
        return zoom_org_credentials(self.org_id)


def zoom_org_credentials(org_id) -> dict:
    token_mgr = ZoomTokenMgr()
    org = current_user.active_org(TOOL, org_id)
    try:
        return dict(
            access_token=token_mgr.access_token(org=org),
            base_url=org.oauth.api_endpoint,
        )
    except TokenMgrError as exc:
        raise ZeusCmdError(message=f"Connection Failed: {exc.message}")


ZoomExportView.register(zoom)
ZoomDownloadView.register(zoom)
ZoomBrowseView.register(zoom)
ZoomDetailView.register(zoom)
ZoomBulkUploadView.register(zoom)
ZoomBulkTemplateView.register(zoom)

# Register bulk view for each supported data type
for data_type in registry.get_data_types(TOOL, "bulk"):
    ZoomBulkSubmitView.register(zoom, data_type)

# Register event views
vw.BulkEventView.register(zoom)
vw.EventHistoryView.register(zoom)

# Register active org select view
vw.OrgSelectView.register(zoom)

# Register org management views
vw.OrgOAuthTabbedListView.register(zoom, ZoomTokenMgr)
vw.OrgFormView.register(zoom, ZoomOrgForm)
vw.OrgCreateView.register(zoom, ZoomOrgForm)
vw.OrgUpdateView.register(zoom, ZoomOrgForm)
vw.OrgDeleteView.register(zoom)

# Register oauth app management views
vw.OAuthFormView.register(zoom)
vw.OAuthCreateView.register(zoom)
vw.OAuthUpdateView.register(zoom)
vw.OAuthDeleteView.register(zoom)
