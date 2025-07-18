import logging
from zeus.shared import helpers
from . import msteams_models as ms
from zeus.msteams import msteams
from .forms import MsTeamsOrgForm
from zeus import registry, views as vw
from flask_security import current_user
from zeus.exceptions import ZeusCmdError
from zeus.models import ProvisioningOrg as Org, OrgType
from zeus.msteams.services.shared import MsTeamsSvcClient
from flask import render_template, session, current_app
from zeus.tokenmgr.msteams import MsTeamsTokenMgr, TokenMgrError

log = logging.getLogger(__name__)

TOOL = "msteams"
MSTEAMS_OPTIONS = [
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
        "text": "View the results of previous MS Teams organization import events.",
    },
    {
        "name": "orgs",
        "title": "Organizations",
        "route": f"{TOOL}.orgs",
        "active_org_required": False,
        "text": "Create, edit or delete your defined MS Teams organizations.",
    },
]


@msteams.context_processor
def msteams_ctx():
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
        "options": MSTEAMS_OPTIONS,
    }


@msteams.get("/")
def msteams_home():
    """
    Tool home page with sidebar and dropdown to select active org
    """
    return render_template("tool/home.html")


class MsTeamsBrowseView(vw.BrowseView):
    decorators = [helpers.org_required(TOOL)]

    @property
    def svc_client(self):
        return MsTeamsSvcClient()

    @property
    def org_credentials(self):
        return msteams_org_credentials(self.org_id)


class MsTeamsExportView(vw.ExportView):
    decorators = [helpers.org_required(TOOL)]

    @property
    def svc_client(self):
        return MsTeamsSvcClient()

    @property
    def org_credentials(self):
        return msteams_org_credentials(self.org_id)


class MsTeamsDownloadView(vw.DownloadView):
    decorators = [helpers.org_required(TOOL)]


class MsTeamsBulkTemplateView(vw.BulkTemplateView):
    decorators = [helpers.org_required(TOOL)]


class MsTeamsBulkUploadView(vw.BulkUploadView):
    decorators = [helpers.org_required(TOOL)]

    @property
    def svc_client(self):
        return MsTeamsSvcClient()


class MsTeamsBulkSubmitView(vw.BulkSubmitView):

    @property
    def svc_client(self):
        return MsTeamsSvcClient()

    @property
    def org_credentials(self):
        return msteams_org_credentials(self.org_id)


class MsTeamsBulkEmergencyAddressView(MsTeamsBulkSubmitView):

    def send_request(self, model):
        resp = self.svc_client.bulk(
            self.org_credentials,
            model,
            azure_maps_api_key=current_app.config["AZURE_MAPS_API_KEY"],
        )
        return resp


def msteams_org_credentials(org_id) -> dict:
    token_mgr = MsTeamsTokenMgr()
    org = current_user.active_org(TOOL, org_id)
    try:
        return dict(
            access_token=token_mgr.access_token(org=org),
            base_url=org.oauth.api_endpoint,
        )
    except TokenMgrError as exc:
        raise ZeusCmdError(message=f"Connection Failed: {exc.message}")


MsTeamsExportView.register(msteams)
MsTeamsDownloadView.register(msteams)
MsTeamsBrowseView.register(msteams)
MsTeamsBulkUploadView.register(msteams)
MsTeamsBulkTemplateView.register(msteams)

# Register bulk view for each supported data type
for data_type in registry.get_data_types(TOOL, supports="bulk"):
    if data_type != "emergency_addresses":
        MsTeamsBulkSubmitView.register(msteams, data_type)

# Register customized bulk view with bing maps api key handling for emergency address geolocation
MsTeamsBulkEmergencyAddressView.register(msteams, "emergency_addresses", ms.MsTeamsEmergencyAddress)

# Register event views
vw.BulkEventView.register(msteams)
vw.EventHistoryView.register(msteams)

# Register active org select view
vw.OrgSelectView.register(msteams)

# Register org management views
vw.OrgListView.register(msteams, MsTeamsTokenMgr)
vw.OrgFormView.register(msteams, MsTeamsOrgForm)
vw.OrgCreateView.register(msteams, MsTeamsOrgForm)
vw.OrgUpdateView.register(msteams, MsTeamsOrgForm)
vw.OrgDeleteView.register(msteams)
