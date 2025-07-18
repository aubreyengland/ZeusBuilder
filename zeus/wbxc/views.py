import logging
from . import wbxc
from zeus.shared import helpers
from zeus.app import job_queue
from .forms import WbxcOrgForm
from .services import WbxcSvcClient
from flask_security import current_user
from zeus import registry, views as vw
from zeus.exceptions import ZeusCmdError
from zeus.shared.stores import RedisWavFileStore
from zeus.views.bulk_views import check_file_type
from zeus.models import ProvisioningOrg as Org, OrgType
from zeus.tokenmgr.wbxc import WbxcTokenMgr, TokenMgrError
from flask import render_template, session, request


log = logging.getLogger(__name__)

TOOL = "wbxc"

WBXC_OPTIONS = [
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
        "text": "View the results of previous Webex Calling organization import events.",
    },
    {
        "name": "orgs",
        "title": "Organizations",
        "route": f"{TOOL}.orgs",
        "active_org_required": False,
        "text": "Create, edit or delete your defined Webex Calling organizations.",
    },
]


@wbxc.context_processor
def wbxc_ctx():
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
        "options": WBXC_OPTIONS,
    }


@wbxc.get("/")
def wbxc_home():
    return render_template("tool/home.html")


class WbxcBrowseView(vw.BrowseView):
    decorators = [helpers.org_required(TOOL)]

    @property
    def svc_client(self):
        return WbxcSvcClient()

    @property
    def org_credentials(self):
        return wbxc_org_credentials(self.org_id)


class WbxcDetailView(vw.DetailView):
    decorators = [helpers.org_required(TOOL)]

    @property
    def svc_client(self):
        return WbxcSvcClient()

    @property
    def org_credentials(self):
        return wbxc_org_credentials(self.org_id)


class WbxcExportView(vw.ExportView):
    decorators = [helpers.org_required(TOOL)]

    @property
    def svc_client(self):
        return WbxcSvcClient()

    @property
    def org_credentials(self):
        return wbxc_org_credentials(self.org_id)


class WbxcDownloadView(vw.DownloadView):
    decorators = [helpers.org_required(TOOL)]


class WbxcBulkTemplateView(vw.BulkTemplateView):
    decorators = [helpers.org_required(TOOL)]


class WbxcBulkUploadView(vw.BulkUploadView):
    decorators = [helpers.org_required(TOOL)]

    @property
    def svc_client(self):
        return WbxcSvcClient()

    def send_request(self):
        wav_files = self.save_uploaded_wav_files()
        resp = self.svc_client.upload(self.workbook_file, wav_files=wav_files)

        if not resp.ok:
            raise ZeusCmdError(message=resp.message)

        return resp.value

    @property
    def prompts_file(self):
        fs = request.files.get("prompts")
        if fs:
            check_file_type(fs, file_types=["zip"])
            return fs
        return None

    @property
    def wav_store(self):
        return RedisWavFileStore(job_queue.connection)

    def save_uploaded_wav_files(self) -> list:
        """
        Look for a prompts file in the posted form and, if present,
        Verify the filetype and extract the contents so the wav files are
        available for batch job submission.

        Returns:
            (dict) prompt name as key and path as value or empty dict
        """
        if self.prompts_file:
            log.debug(f"Extracting prompts from {self.prompts_file.filename}...")

            self.wav_store.save(self.job_id, self.prompts_file.stream._file)  # noqa

            wav_file_names = self.wav_store.get_file_names(self.job_id)
        else:
            wav_file_names = []

        return wav_file_names


class WbxcBulkSubmitView(vw.BulkSubmitView):
    @property
    def svc_client(self):
        return WbxcSvcClient()

    @property
    def org_credentials(self):
        return wbxc_org_credentials(self.org_id)


class WbxcBulkSubmitGreetingsView(WbxcBulkSubmitView):
    def send_request(self, model):
        """
        Convert the form data into a BatchPrompt object and
        pass along with the Wbcx client to process greetings.

        For CREATE and UPDATE requests for busy and no answer
        greetings, add the wav file bytes to the model.
        """
        busy_wav_bytes = None
        no_ans_wav_bytes = None

        store = RedisWavFileStore(conn=job_queue.connection)

        if model.sendBusyCalls_file and model.action in ("CREATE", "UPDATE"):
            busy_wav_bytes = store.get_file(self.job_id, model.sendBusyCalls_file)

        if model.sendUnansweredCalls_file and model.action in ("CREATE", "UPDATE"):
            no_ans_wav_bytes = store.get_file(self.job_id, model.sendUnansweredCalls_file)

        return self.svc_client.bulk(
            self.org_credentials, model, busy_wav_bytes=busy_wav_bytes, no_ans_wav_bytes=no_ans_wav_bytes
            )


def wbxc_org_credentials(org_id) -> dict:
    token_mgr = WbxcTokenMgr()
    org = current_user.active_org(TOOL, org_id)
    try:
        return dict(
            access_token=token_mgr.access_token(org=org),
            base_url=org.oauth.api_endpoint,
        )
    except TokenMgrError as exc:
        raise ZeusCmdError(message=f"Connection Failed: {exc.message}")


WbxcExportView.register(wbxc)
WbxcDetailView.register(wbxc)
WbxcDownloadView.register(wbxc)
WbxcBrowseView.register(wbxc)
WbxcBulkTemplateView.register(wbxc)
WbxcBulkUploadView.register(wbxc, get_template="wbxc/wbxc_bulk.html")

# Data types with wav files
data_types_wav = ["user_calling", "workspace_calling", "virtual_lines"]

# Register bulk view for each supported data type
for data_type in registry.get_data_types(TOOL, "bulk"):
    if data_type not in data_types_wav:
        WbxcBulkSubmitView.register(wbxc, data_type)
    else:
        WbxcBulkSubmitGreetingsView.register(wbxc, data_type)

# Register event views
vw.BulkEventView.register(wbxc)
vw.EventHistoryView.register(wbxc)

# Register active org select view
vw.OrgSelectView.register(wbxc)

# Register org management views
vw.OrgOAuthTabbedListView.register(wbxc, WbxcTokenMgr)
vw.OrgFormView.register(wbxc, WbxcOrgForm)
vw.OrgCreateView.register(wbxc, WbxcOrgForm)
vw.OrgUpdateView.register(wbxc, WbxcOrgForm)
vw.OrgDeleteView.register(wbxc)

# Register oauth app management views
vw.OAuthFormView.register(wbxc)
vw.OAuthCreateView.register(wbxc)
vw.OAuthUpdateView.register(wbxc)
vw.OAuthDeleteView.register(wbxc)
