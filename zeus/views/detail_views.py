import logging
from zeus.shared import helpers
from .base_views import ToolView
from flask import request, render_template
from zeus.exceptions import ZeusCmdError
from zeus.services import SvcResponse, SvcClient


log = logging.getLogger(__name__)


class DetailView(ToolView):
    """
    Handles detail submissions from a browse table.
    Executes the appropriate Detail Task and provides the
    returned data to the detail template.

    Registers as:
        methods POST
        endpoint: `{tool}.detail_{data_type}`
        rule: `/{tool}/detail/data_type`

    Registration requires:
        tool: 'five9', 'zoom', etc.

    Must be sub-classed for each tool with the following:
        svc_client property
        org_credentials property
    """
    def __init__(self, name):
        super().__init__(name)
        self.tables: list = []
        self.get_template = "tool/detail_modal.html"
        self.data_type = request.form.get("data_type")
        self.data: dict = {}

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

    def context_vars(self) -> dict:
        vm = super().context_vars()
        vm["detail_template"] = f"{self.tool}/{self.data_type}_detail.html"
        return vm

    def post(self):
        try:
            self.data = self.process()
        except ZeusCmdError as exc:
            return helpers.redirect_on_cmd_err(f"{self.tool}.browse", exc)

        return render_template(self.get_template, vm=self.context_vars())

    def process(self):
        resp = self.send_request()

        if not resp.ok:
            raise ZeusCmdError(message=resp.message)

        return resp.value

    def send_request(self) -> SvcResponse:
        return self.svc_client.detail(
            self.org_credentials,
            data_type=self.data_type,
            browse_row=request.form.to_dict()
        )

    @classmethod
    def register(cls, app):
        view = cls.as_view("detail", app.name)
        app.add_url_rule(f"/detail/", view_func=view)
