import time
import logging
from zeus import registry
from rq.job import Dependency
from zeus.shared import helpers
from zeus.services import SvcClient
from flask_login import current_user
from zeus.exceptions import ZeusCmdError
from werkzeug.utils import secure_filename
from zeus.models import ProvisioningOrg as Org
from .base_views import JobQueueToolView, job_queue_error
from flask import render_template, send_file, request, session
from ..shared.workbook_creator import ExportWorkbookCreator
from ..shared.post_processors import ExportPostProcessor
from rq.command import send_stop_job_command


log = logging.getLogger(__name__)


class ZeusExportJobCanceled(ZeusCmdError):
    pass


def parent_job_null_func():
    pass


class DownloadView(JobQueueToolView):
    """
    Process request to download file after export jobs complete
    Returns file stream for browser download

    Registers as:
        methods POST
        endpoint: `{tool}.export_download`
        rule: `/{tool}/export/download/<job_id>`

    Registration requires:
        tool: 'five9', 'zoom', etc.

    Subclass should also have the decorators class attr set
    to `[helpers.org_required({tool})]`
    """

    job_type = "export"
    post_processor = ExportPostProcessor

    @property
    def data_types(self):
        """
        Dictionary of data type props
        for tool data types enabled for export.
        Returns:
            (dict): Key is data_type, Value is dict of properties
        """
        return helpers.sort_data_types(registry.get_data_types(self.tool, "export"))

    def post(self, job_id):
        try:
            self.check_job_id(job_id)
            job = self.get_job(job_id)
            wb_data = self.process_export_data(job)
            wb_stream = self.build_workbook_file(wb_data)
            filename = self.build_filename()
        except ZeusCmdError as exc:
            return helpers.redirect_on_cmd_err(f"{self.tool}.export", exc)
        finally:
            # Ensure job_id is removed from session on successful or failed download
            # otherwise be redirected to the download form again
            session.pop(self.session_key, None)

        return send_file(wb_stream, as_attachment=True, download_name=filename)

    def process_export_data(self, job):
        export_data = {}

        for dep in job.dependencies():
            resp = dep.return_value()
            if resp and resp.value:
                export_data.update(resp.value)

        try:
            processor = self.post_processor(self.tool, export_data)
            return processor.run()
        except Exception as exc:
            raise ZeusCmdError(f"Export processing failed: {exc}")

    def build_filename(self):
        """
        Build the attachment filename based on the active org name
        and timestamp
        """
        org_name = (
            Org.query.filter_by(user_id=current_user.id)
            .filter_by(id=int(self.org_id))
            .one()
        )
        ts = time.strftime("%m%d%Y")
        filename = secure_filename(f"{self.tool.title()}_{org_name.name}_Export_{ts}.xlsx")
        return filename or f"{self.tool.title()}_Export.xlsx"

    def build_workbook_file(self, wb_data):
        try:
            creator = ExportWorkbookCreator(self.data_types)
            return creator.run(wb_data)
        except Exception as exc:
            raise ZeusCmdError(f"Spreadsheet creation failed: {exc}")

    @classmethod
    def register(cls, app):
        view = cls.as_view("export_download", app.name)
        app.add_url_rule("/export/download/<job_id>", view_func=view)


class ExportView(JobQueueToolView):
    """
    Provides export home page with check box for each data type.
    When submitted, places a Rq job in the Redis queue for each
    selected data type and links these as dependencies to a container
    job used to track job status.

    The client will POST the job_id intermittently to get status on
    the export jobs.

    Registers as:
        methods GET, POST
        endpoint: `{tool}.export`
        rule: `/{tool}/export`

    Registration requires:
        tool: 'five9', 'zoom', etc.

    Must be sub-classed for each tool with the following:
        data_types property
        svc_client property
        org_credentials property

    Subclass should also have the decorators class attr set
    to `[helpers.org_required({tool})]`
    """

    job_type = "export"

    def __init__(self, tool):
        super().__init__(tool)
        self.get_template = "tool/export.html"
        self.post_template = "tool/export_form.html"
        self.clear_job_id = False

    @property
    def data_types(self) -> dict:
        """
        Dictionary of data type props
        for tool data types enabled for export.
        Returns:
            (dict): Key is data_type, Value is dict of properties
        """
        return helpers.sort_data_types(registry.get_data_types(self.tool, "export"))

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
    def selected_data_types(self) -> list:
        return [r for r in request.form.to_dict()]

    def context_vars(self):
        """
        Collect job status details into a dict for each data type for the
        export form template to render the checkboxes.
        """
        vm = super().context_vars()
        vm["data_types"] = self.data_types

        if self.job:
            vm["status"] = self.job.status
        else:
            vm["status"] = ""

        vm["form_items"] = self.process_job_progress()
        return vm

    def process_job_progress(self) -> list[dict]:
        """
        Parse the export job for the status of each child job and
        return in a dictionary formated as expected by the export form view.
        """
        form_items = []
        progress = {}

        if self.job:
            try:
                progress = self.job.progress
            except Exception as exc:
                self.clear_job_id = True
                raise ZeusCmdError(f"Export job timed-out or not found: {exc}")

        for data_type, model in self.data_types.items():
            status, message = progress.get(data_type) or ("", "")
            checked = "checked" if status else ""

            item = {
                "status": status,
                "name": data_type,
                "checked": checked,
                "message": message,
                "label": model.schema()["title"],
            }

            form_items.append(item)

        return form_items

    def dispatch_request(self, **kwargs):
        """
        Read/set the export job id between the session and instance attribute.

        Before dispatch:
        - Check for an existing job_id in the session based on `self.session_key`. If found,
          verify it is valid and set the `self.job_id` instance attribute.

        After dispatch:
        - Set or remove `self.session_key` from the session based on the following conditions:
            - Remove if `self.job` is set and has a failed status.
            - Set if `self.job_id` is set
        """

        job_id = session.get(self.session_key, "")
        if job_id and not self.job_id_is_valid(job_id):
            log.warning(
                f"{self.session_key}: {job_id} failed validity check: {self.job_id_prefix}"
            )
            job_id = ""

        self.job_id = job_id

        try:
            rv = super().dispatch_request(**kwargs)
        except ZeusCmdError as exc:
            rv = helpers.redirect_on_cmd_err(f"{self.tool}.export", exc)

        if not self.job_id or (self.job and self.job.is_failed) or self.clear_job_id:
            session.pop(self.session_key, None)
        else:
            session[self.session_key] = self.job_id

        return rv

    def get(self):
        """
        Add job_id to the session or, if job_id already exists,
        get the existing job.

        Response will render new export form or in progress form
        based on the presence of an existing job.
        """
        if not self.job_id:
            # This is a new request so add a job id to the session
            self.job_id = self.new_job_id()

        else:
            # User returning to check on in progress job .
            # Get the job so the in-progress or finished form can be rendered.
            # If job has failed, flash error and reset job id so new job can be submitted.
            self.job = self.get_job(self.job_id, False)
            self.flash_for_failed_job()

        return render_template(self.get_template, vm=self.context_vars())

    def post(self):
        """
        Submit new export job and render in progress form.
        Exception raised if:
        - job_id is not set
        - job already exists for job_id
        """
        if not self.job_id:
            log.warning("Attempt to submit export job without a job id")
            raise ZeusCmdError(message="")

        self.job = self.get_job(self.job_id, raise_if_not_found=False)
        if self.job:
            log.warning("Attempt to submit export job with duplicate job id")
            raise ZeusCmdError(message="")

        if not self.selected_data_types:
            raise ZeusCmdError(message="No data types selected for export")

        self.submit_job()

        return render_template(self.post_template, vm=self.context_vars())

    def put(self):
        """
        Get existing job for status polling request.
        Exception raised if:
        - job_id is not set
        - job not found for job_id
        """
        if not self.job_id:
            raise ZeusCmdError(message="")

        self.job = self.get_job(self.job_id)
        self.flash_for_failed_job()

        return render_template(self.post_template, vm=self.context_vars())

    def delete(self):
        """
        Handle export job cancel request.

        Attempt to cancel/stop queued/running child jobs
        then cancel the parent export job.

        Ensure job_id is cleared and raise ZeusExportJobCanceled
        to trigger redirect and flash message
        """
        self.clear_job_id = True
        self.job = self.get_job(self.job_id)

        try:
            export_jobs = self.job.dependencies()
        except Exception as exc:
            log.warning(f"{self.job_id} cancel failed: {exc}")
            export_jobs = []

        export_jobs.append(self.job)

        for export_job in export_jobs:
            if export_job.worker_name:
                # Job is running
                try:
                    send_stop_job_command(self.job_queue.connection, export_job.id)
                except Exception as exc:
                    log.warning(f"{self.job_id} cancel failed stopping job: {export_job}: {exc}")
            else:
                try:
                    export_job.cancel()
                except Exception as exc:
                    log.warning(f"{self.job_id} cancel failed canceling job: {export_job}: {exc}")

        raise ZeusExportJobCanceled("Export job cancelled", "warning")

    def submit_job(self):
        """
        Process a POST request.
        If the request includes an export_id, it is a request for status on currently
        running export jobs.
        If no export_id is included, it is a request to begin a new export based
        on the boxes checked in the form.
        """
        export_jobs = self.submit_export_jobs()
        depends_on = (
            Dependency(jobs=export_jobs, allow_failure=True, enqueue_at_front=False),
        )

        job_timeout = min([
            int(self.job_queue.job_timers()["job_timeout"] * len(export_jobs)),
            86400 * 2,
        ])
        log.info(f"**** {job_timeout=}")
        self.job = self.job_queue.enqueue_job(
            f=parent_job_null_func,
            job_id=self.job_id,
            depends_on=depends_on,
            job_timeout=job_timeout,
            result_ttl=self.job_queue.result_ttl_export,
            description=f"{self.tool} export group",
        )

    def submit_export_jobs(self):
        export_jobs = []

        selected_data_types = [r for r in request.form.to_dict()]

        for data_type in selected_data_types:
            job = self.job_queue.enqueue_job(
                self.svc_client.export,
                result_ttl=self.job_queue.result_ttl_export,
                description=f"{self.tool} export {data_type}",
                meta=dict(data_type=data_type, progress_id=data_type),
                kwargs=dict(credentials=self.org_credentials, data_type=data_type),
            )
            export_jobs.append(job)

        return export_jobs

    def flash_for_failed_job(self):
        if self.job and self.job.status == "failed":
            message = self.job.meta.get("error_message", job_queue_error)
            self.clear_job_id = True
            self.flash_message(message, "danger")

    @classmethod
    def register(cls, app):
        view = cls.as_view("export", app.name)
        app.add_url_rule("/export", view_func=view)
