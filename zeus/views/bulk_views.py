import uuid
import logging
from pathlib import Path
from zeus import registry
from typing import Type, Dict
from zeus.app import job_queue
from .base_views import ToolView
from flask_login import current_user
from pydantic import ValidationError
from zeus.shared.stores import RedisWorkSheetStore
from flask import request, render_template, send_file
from .template_table import TemplateTable, default_bulk_table
from zeus.exceptions import ZeusCmdError, extract_first_validation_error
from zeus.shared import data_type_models as dm, helpers, workbook_creator as wc
from zeus.services import SuccessResponse, FailureResponse, SvcResponse, SvcClient, WorksheetLoadResp


log = logging.getLogger(__name__)


class BulkSubmitView(ToolView):
    """
    Handles bulk submissions from uploaded workbook rows.
    When a job is submitted, gets the data from the worksheet store
    based on the job_id and row_id in the submission and uses it
    to construct a model to pass to the service.

    Renders a result icon (success/fail based on the service response)
    that is inserted in the DOM via a htmx oob-swap

    Registers as:
        methods POST
        endpoint: `{tool}.bulk_{data_type}`
        rule: `/{tool}/import/data_type`

    Registration requires:
        tool: 'five9', 'zoom', etc.

    Must be sub-classed for each tool with the following:
        data_type class attribute
        model_cls: class attribute
        svc_client property
        org_credentials property
    """
    def __init__(self, name, data_type):
        super().__init__(name)
        self._store = None
        self.result: str = ""
        self.error: str = ""
        self.stored_model = None
        self.submitted_model = None
        self.data_type: str = data_type
        self.job_id = request.form.get("job_id")
        self.row_id = request.form.get("row_id")
        self.post_template = "tool/bulk_result_icon.html"

    @property
    def svc_client(self):
        """
        Instance of SvcClient subclass for tool
        """
        return SvcClient()

    @property
    def org_credentials(self) -> dict:
        """
        Dictionary with credentials to pass to tool's API client constructor
        """
        return {}

    @property
    def model_cls(self) -> Type[dm.DataTypeBase]:
        return registry.get_data_type(self.tool, self.data_type)

    @property
    def id_field(self) -> str:
        """
        ID field for this view's model. Used for the event log entry
        """
        return self.model_cls.schema().get("id_field", "")

    @property
    def store(self):
        if not self._store:
            self._store = RedisWorkSheetStore(job_queue.connection)
        return self._store

    def post(self):
        try:
            resp = self.process()
            self.result = resp.result.title()
            self.error = resp.message

            if self.result.lower() != "ignore":
                self.log_event()

        except ZeusCmdError as exc:
            return helpers.redirect_on_cmd_err(f"{self.tool}.bulk", exc)

        return render_template(self.post_template, vm=self.context_vars())

    def process(self) -> SvcResponse:
        """
        Send request to process a single request based on the data in the submitted form.
         - Get the model from the store based on the row id in the submission
         - If no model retrieval fails, create a FailureResponse and return it.
         - If the action is 'IGNORE', return a SuccessResponse with result of 'Ignore'.
         - Pass the model to the send_request method to execute the appropriate service.
         - Return the service's Response.
        """
        try:
            self.get_model_for_submission()
        except ZeusCmdError as exc:
            return FailureResponse(message=exc.message)

        if self.submitted_model.action == "IGNORE":
            return SuccessResponse(result="Ignore")

        return self.send_request(self.submitted_model)

    def get_model_for_submission(self):
        """
        Get the model from the store based on the provided data_type and row_id.

        Update the model's action to the value in the form to allow user
        to change the action between upload and submission. Then re-create
        the model to allow any action-specific validators to run.
        """
        self.stored_model = self.store.get_row(self.job_id, self.data_type, self.row_id)

        if not self.stored_model:
            raise ZeusCmdError("Workbook row submission failed. Please re-upload the workbook and try again.")

        submitted_model = self.stored_model.copy()
        submitted_model.action = request.form.get("action")

        try:
            self.submitted_model = self.model_cls.parse_obj(submitted_model)
        except ValidationError as exc:
            raise ZeusCmdError(f"Validation Failed: {extract_first_validation_error(exc)}")

    def send_request(self, model) -> SvcResponse:
        return self.svc_client.bulk(self.org_credentials, model)

    def log_event(self):
        """
        Add an event record to the DB with the details and result
        of the operation.
        Derive the entity value from the model's id field. This is
        the identity field in the model (ex: email for user, name for skill).
        """
        try:
            action = request.form.get("action")
            entity = getattr(self.stored_model, self.id_field, "")
            current_user.add_event(
                entity=entity,
                error=self.error,
                job_id=self.job_id,
                result=self.result,
                org_id=int(self.org_id),
                data_type=self.data_type,
                action=action.title(),
            )
        except Exception:
            log.exception("Add Event Fatal Error")

    @classmethod
    def register(cls, app, data_type, model_cls=None):
        view = cls.as_view(f"bulk_{data_type}", app.name, data_type)
        app.add_url_rule(f"/import/{data_type}", view_func=view)


class BulkUploadView(ToolView):
    """
    Provides home page with controls to upload provisioning workbook
    When submitted, renders a tab with a table for each worksheet processed

    Registers as:
        methods GET, POST
        endpoint: `{tool}.bulk`
        rule: `/{tool}/import`

    Registration requires:
        tool: 'five9', 'zoom', etc.
        get_template: Optionally, override default template

    Must be sub-classed for each tool with the following:
        data_types property
        svc_client property
        build_table method

    Subclass should also have the decorators class attr set
    to `[helpers.org_required({tool})]`
    """
    def __init__(self, tool, **kwargs):
        super().__init__(tool)
        self._store = None
        self.tables: dict = {}
        self.job_id = ""
        self.load_errors: Dict[str, dict] = {}
        self.post_template = "tool/bulk_tabs.html"
        self.get_template = kwargs.get("get_template") or "tool/bulk.html"
        self.ws_responses: Dict[str, WorksheetLoadResp] = {}

    @property
    def data_types(self) -> dict:
        return registry.get_data_types(self.tool, "bulk")

    @property
    def svc_client(self):
        """
        Instance of SvcClient subclass for tool
        """
        return SvcClient()

    @property
    def job_id_prefix(self) -> str:
        """portion of a job id that uniquely identifies the tool, operation, user and org"""
        return f"{self.tool}:bulk:{current_user.id}:{self.org_id}"

    def new_job_id(self) -> str:
        """Generate a unique random job ID using the job_id_prefix"""
        return f"{self.job_id_prefix}:{uuid.uuid4()}"

    def get(self):
        return render_template(self.get_template)

    def post(self):
        self.job_id = self.new_job_id()
        try:
            self.process()
        except ZeusCmdError as exc:
            return helpers.redirect_on_cmd_err(f"{self.tool}.bulk", exc)

        return render_template(self.post_template, vm=self.context_vars())

    @property
    def store(self):
        if not self._store:
            self._store = RedisWorkSheetStore(job_queue.connection)
        return self._store

    @property
    def workbook_file(self):
        fs = request.files.get("workbook")

        if not fs:
            raise ZeusCmdError("Workbook not found in upload")

        check_file_type(fs, file_types=["xlsx"])
        return fs.stream._file  # noqa

    def process(self):
        log.info(f"Processing {type(self)} bulk upload request from {current_user}...")
        self.ws_responses = self.send_request()
        self.process_ws_responses()
        self.build_tables()

    def send_request(self):
        resp = self.svc_client.upload(self.workbook_file)
        if not resp.ok:
            raise ZeusCmdError(message=resp.message)

        return resp.value

    def process_ws_responses(self):
        """
        Process the response for each uploaded worksheet for rendering
        the bulk tables.

        Save any sheet-level or row-level errors to the loaded_errors attribute
        for rendering the error modals.

        Store successfully loaded rows so, they are available to the
        views when submitted.
        """
        for data_type, ws_resp in self.ws_responses.items():
            if ws_resp.sheet_error or ws_resp.error_rows:
                self.load_errors[data_type] = {
                    "sheet": ws_resp.sheet_error,
                    "rows": ws_resp.error_rows,
                }
            if ws_resp.loaded_rows:
                self.store.save(self.job_id, ws_resp)

    def build_tables(self):
        for data_type, ws_resp in self.ws_responses.items():
            # Only build tables for specified data types.
            if data_type not in self.data_types:
                continue
            # Add key to tables dict for all processed data_types regardless if sheet was parsed successfully
            # This ensures tabs are rendered for all processed worksheets
            self.tables[data_type] = None

            if ws_resp.loaded_rows:
                table_rows = [dict(id=resp.index, **resp.data.dict()) for resp in ws_resp.loaded_rows]
            else:
                table_rows = []

            self.tables[data_type] = self.build_table(data_type, table_rows)

    def build_table(self, data_type, rows) -> "TemplateTable":
        try:
            builder = registry.get_bulk_table(self.tool, data_type)
            return builder(rows)
        except LookupError:
            model = registry.get_data_type(self.tool, data_type)
            return default_bulk_table(model, rows)

    @classmethod
    def register(cls, app, **kwargs):
        view = cls.as_view("bulk", app.name, **kwargs)
        app.add_url_rule("/import", view_func=view)


def check_file_type(file, file_types=None, content_types=None):
    if file_types:
        extension = Path(file.filename).suffix.strip(".")
        if not all([extension and str(extension).lower() in file_types]):
            raise ZeusCmdError(message=f"{file.filename} is an unsupported file type")

    if content_types:
        if str(file.content_type.lower()) not in [c.lower() for c in content_types]:
            raise ZeusCmdError(
                message=f"{file.filename} {file.content_type} content type is not supported"
            )

    return True


class BulkTemplateView(ToolView):
    """
    Generates a template provisioning workbook for download
    with a worksheet for each data type

    Registers as:
        methods POST
        endpoint: `{tool}.export_template`
        rule: `/{tool}/export/template`

    Registration requires:
        tool: 'five9', 'zoom', etc.
    """

    @property
    def data_types(self) -> dict:
        """
        Since the file is intended as a bulk file template, include all data types
        that support bulk operations.  Sort the data types if implemented on the model.
        """
        return helpers.sort_data_types(registry.get_data_types(self.tool, "bulk"))

    def get(self):
        """
        Provide a provisioning workbook template with a sheet with the correct
        headers for each data type.
        """
        try:
            filename = f"{self.tool.title()}_Template.xlsx"
            wb_stream = self.build_template_file()
            return send_file(wb_stream, as_attachment=True, download_name=filename)
        except ZeusCmdError as exc:
            return helpers.redirect_on_cmd_err(f"{self.tool}.bulk", exc)

    def build_template_file(self):
        export_data = {}

        for model in self.data_types.values():
            doc = model.model_doc()
            sheetname = doc.title
            empty_row = {d.doc_name: "" for d in doc.doc_fields}

            export_data[sheetname] = [empty_row]

        creator = wc.ExportWorkbookCreator(self.data_types)
        return creator.run(export_data)

    @classmethod
    def register(cls, app, **kwargs):
        view = cls.as_view("bulk_wb_template", app.name, **kwargs)
        app.add_url_rule("/bulk/wb_template", view_func=view)
