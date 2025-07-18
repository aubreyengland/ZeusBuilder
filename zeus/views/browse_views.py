import logging
from zeus import registry
from zeus.shared import helpers
from zeus.services import SvcClient
from zeus.exceptions import ZeusCmdError
from flask import request, render_template
from .base_views import JobQueueToolView, job_queue_error
from .template_table import TemplateTable, default_browse_table

log = logging.getLogger(__name__)


class BrowseView(JobQueueToolView):
    """
    Provides browse home page with tabs for each data type.
    When a table is clicked, calls the browse svc client
    and renders a table of returned items in an HTMX response

    Registers as:
        methods GET, POST
        endpoint: `{tool}.browse`
        rule: `/{tool}/browse`
        request args: `data_type` for POST

    Registration requires:
        tool: 'five9', 'zoom', etc.

    Must be sub-classed for each tool with the following:
        data_types property
        svc_client property
        org_credentials property
        build_table method

    Subclass should also have the decorators class attr set
    to `[helpers.org_required({tool})]`
    """

    job_type = "browse"

    def __init__(self, tool):
        super().__init__(tool)
        self.table = None
        self.get_template = "tool/browse.html"
        self.post_template = "tool/browse_tables.html"
        self.data_type = request.form.get("data_type")

    @property
    def data_types(self) -> dict:
        """
        Dictionary of data types as keys and title as values
        for the browse-able data types based on model schema
        """
        browse_types = helpers.sort_data_types(registry.get_data_types(self.tool, "browse"))
        data_types = {
            data_type: model.schema()["title"]
            for data_type, model in browse_types.items()
        }

        return data_types

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

    def context_vars(self):
        vm = super().context_vars()

        if self.job:
            vm["status"] = self.job.status
        else:
            vm["status"] = ""

        return vm

    def build_table(self, rows) -> "TemplateTable":
        """
        Create a TemplateTable instance using the data returned by the Browse service.
        Use the custom table builder in the TableRegistry if on exists for the tool/data type.
        Otherwise, use the default browse table builder.
        """
        try:
            builder = registry.get_browse_table(self.tool, self.data_type)
            return builder(rows)
        except LookupError:
            model = registry.get_data_type(self.tool, self.data_type)
            return default_browse_table(model, rows)

    def get(self):
        return render_template(self.get_template, data_types=self.data_types)

    def post(self):
        """
        Submit browse job for the data_type in the form.

        On ZeusCmdError, redirect to browse home page and flash error.
        """
        self.job_id = self.new_job_id()
        try:
            self.submit_job()
        except ZeusCmdError as exc:
            return helpers.redirect_on_cmd_err(f"{self.tool}.browse", exc)

        return render_template(self.post_template, vm=self.context_vars())

    def put(self):
        """
        Get browse job status for the job_id in the form.
        If finished, build a table with the returned objects.
        If still running, render the status polling element again.

        On ZeusCmdError, redirect to browse home page and flash error
        Exception raised if:
        - Job ID does not exit
        - Job ID is invalid
        - Job not found
        - Job final status is 'failed'
        - Job succeeded but browse service returned an error
        - Job succeeded but browse service returned no objects
        """
        try:
            self.job_id = request.form.get("job_id")
            self.check_job_id(self.job_id)

            self.job = self.get_job(self.job_id)
            self.check_job()

            if self.job.is_finished:
                rows = self.job.return_value().value
                self.table = self.build_table(rows)

        except ZeusCmdError as exc:
            return helpers.redirect_on_cmd_err(f"{self.tool}.browse", exc)

        return render_template(self.post_template, vm=self.context_vars())

    def submit_job(self):
        self.job = self.job_queue.enqueue_job(
            f=self.svc_client.browse,
            job_id=self.job_id,
            meta=dict(data_type=self.data_type),
            result_ttl=self.job_queue.result_ttl_browse,
            description=f"{self.tool} browse {self.data_type}",
            kwargs=dict(credentials=self.org_credentials, data_type=self.data_type),
        )

    def check_job(self):
        """
        Check RQ job and raise ZeusCmdError any error conditions are found
        to flash an alert in the browser
        Raise if:
        - Job completed with an error status OR
        - The BrowseSvc response includes an error OR
        - The BrowseSvc response includes no data
        """
        if self.job.status == "failed":
            message = self.job.meta.get("error_message", job_queue_error)
            raise ZeusCmdError(message=message)

        if self.job.is_finished:
            resp = self.job.return_value()

            if not resp.ok:
                raise ZeusCmdError(message=resp.message)

            if not resp.value:
                raise ZeusCmdError(f"No {self.data_type} found.", "info")

    @classmethod
    def register(cls, app):
        view = cls.as_view("browse", app.name)
        app.add_url_rule("/browse", view_func=view)
