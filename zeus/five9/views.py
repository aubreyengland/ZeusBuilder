import logging
from . import five9
from zeus import registry
from zeus.shared import helpers
from zeus.app import job_queue
from zeus import views as vw
from .forms import Five9OrgForm
from flask_security import current_user
from zeus.exceptions import ZeusCmdError
from zeus.views.base_views import CRUDTableView
from zeus.five9.services import Five9SvcClient
from zeus.shared.stores import RedisWavFileStore
from zeus.views.bulk_views import check_file_type
from flask import render_template, session, request
from zeus.models import ProvisioningOrg as Org, OrgType

log = logging.getLogger(__name__)

TOOL = "five9"
FIVE9_OPTIONS = [
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
        "text": "View the results of previous Five9 organization import events.",
    },
    {
        "name": "orgs",
        "title": "Organizations",
        "route": f"{TOOL}.orgs",
        "active_org_required": False,
        "text": "Create, edit or delete your defined Five9 organizations.",
    },
]


@five9.context_processor
def five9_ctx():
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
        "options": FIVE9_OPTIONS,
        "active_org": session.get(f"{TOOL}org"),
    }


@five9.get("/")
def five9_home():
    """
    Tool home page with sidebar and dropdown to select active org
    """
    return render_template("tool/home.html")


class Five9OrgListView(CRUDTableView):
    """
    Provides org management table with controls to
    manage each row for org types that authenticate with
    a username/password.

    Registers as:
        methods: GET
        endpoint: `{tool}.orgs`
        rule: `/{tool}/orgs`

    Registration requires:
        tool: 'five9' etc.
        template: Optionally, override default template
    """
    def __init__(self, tool, **kwargs):
        super().__init__()
        self.tool = tool
        self.org_rows: list = []
        self.template = "five9/five9_orgs.html"

    def build_table_rows(self):
        self.org_rows = current_user.orgs_of_type(self.tool)

    @classmethod
    def register(cls, app, **kwargs):
        view = cls.as_view("orgs", app.name, **kwargs)
        app.add_url_rule("/orgs", view_func=view)


class Five9OrgCreateView(vw.OrgCreateView):
    """Custom View needed because Five9 does not use OAuth"""
    def prepare_record(self):
        self.record = Org.create(
            org_type=self.tool,
            user_id=current_user.id,
            name=self.form.name.data,
            api_user=self.form.api_user.data,
            api_password=self.form.api_password.data,
        )


class Five9BrowseView(vw.BrowseView):
    decorators = [helpers.org_required(TOOL)]

    @property
    def svc_client(self):
        return Five9SvcClient()

    @property
    def org_credentials(self):
        return five9_org_credentials(self.org_id)


class Five9ExportView(vw.ExportView):
    decorators = [helpers.org_required(TOOL)]

    @property
    def svc_client(self):
        return Five9SvcClient()

    @property
    def org_credentials(self):
        return five9_org_credentials(self.org_id)


class Five9DownloadView(vw.DownloadView):
    decorators = [helpers.org_required(TOOL)]


class Five9BulkTemplateView(vw.BulkTemplateView):
    decorators = [helpers.org_required(TOOL)]


class Five9BulkUploadView(vw.BulkUploadView):
    decorators = [helpers.org_required(TOOL)]

    @property
    def svc_client(self):
        return Five9SvcClient()

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
        available for job submission.

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


class Five9BulkSubmitView(vw.BulkSubmitView):

    @property
    def svc_client(self):
        return Five9SvcClient()

    @property
    def org_credentials(self):
        return five9_org_credentials(self.org_id)


class Five9BulkSubmitPromptView(Five9BulkSubmitView):

    def send_request(self, model):
        wav_bytes = None

        if model.wav_file and model.action in ("CREATE", "UPDATE"):
            store = RedisWavFileStore(conn=job_queue.connection)
            wav_bytes = store.get_file(self.job_id, model.wav_file)

        return self.svc_client.bulk(self.org_credentials, model, wav_bytes=wav_bytes)


def five9_org_credentials(org_id):
    org = current_user.active_org(org_id=org_id, org_type=TOOL)
    return dict(username=org.api_user, password=org.api_password)


Five9ExportView.register(five9)
Five9DownloadView.register(five9)
Five9BrowseView.register(five9)
Five9BulkTemplateView.register(five9)
Five9BulkUploadView.register(five9, get_template="five9/five9_bulk.html")

# Register bulk view for each supported data type except prompts
for data_type in registry.get_data_types(TOOL, "bulk"):
    if data_type != "prompts":
        Five9BulkSubmitView.register(five9, data_type)

# Register customized bulk view with wav file handling for prompts
Five9BulkSubmitPromptView.register(five9, "prompts")

# Register event views
vw.BulkEventView.register(five9)
vw.EventHistoryView.register(five9)

# Register active org selection view
vw.OrgSelectView.register(five9)

# Register org management views
Five9OrgListView.register(five9)
vw.OrgFormView.register(five9, Five9OrgForm, partial_template=f"{TOOL}/five9_orgs_form.html")
Five9OrgCreateView.register(five9, Five9OrgForm, template=f"{TOOL}/five9_orgs_form.html")
vw.OrgUpdateView.register(five9, Five9OrgForm, template=f"{TOOL}/five9_orgs_form.html")
vw.OrgDeleteView.register(five9)
