import time
import logging
from sqlalchemy import func
from datetime import datetime
from .base_views import ToolView
from flask_login import current_user
from zeus.models import Event, OrgType
from zeus.exceptions import ZeusCmdError
from werkzeug.utils import secure_filename
from sqlalchemy.sql.operators import desc_op, asc_op
from zeus.shared.helpers import redirect_on_cmd_err
from flask import request, render_template, send_file
from zeus.shared.workbook_creator import WorkbookCreator
from .template_table import TemplateTableCol, TemplateTable


log = logging.getLogger(__name__)
event_cols = {
    "job_id": {"name": "job_id", "title": "Job ID", "hidden": True},
    "timestamp": {"name": "timestamp", "title": "Timestamp", "hidden": False},
    "result": {"name": "result", "title": "Result", "hidden": False},
    "user": {"name": "user", "title": "User", "hidden": True},
    "tool": {"name": "tool", "title": "Tool", "hidden": False},
    "org": {"name": "org", "title": "Org", "hidden": False},
    "action": {"name": "action", "title": "Action", "hidden": False},
    "data_type": {"name": "data_type", "title": "Type", "hidden": False},
    "entity": {"name": "entity", "title": "Name", "hidden": False},
    "error": {"name": "error", "title": "Error", "hidden": False},
}


class EventHistoryQuery:
    def __init__(self, query_args, base_query):
        self.query_args = query_args
        self.base_query = base_query

    def process(self):
        """
        Query the Event table for events associated with the current user
        matching the search_text and/or job_id query params

        Create a Flask-SQLAlchemy paginate object using the query for
        events table rendering
        """
        query = self.build_query()
        return query

    def build_query(self):
        query = self.base_query

        if self.query_args.get("job_id"):
            query = query.filter(Event.job_id == self.query_args["job_id"])

        if self.query_args.get("org_type"):
            query = query.filter(
                func.lower(OrgType.name) == func.lower(self.query_args["org_type"])
            )

        if self.query_args.get("data_type"):
            query = query.filter(
                func.lower(Event.data_type) == func.lower(self.query_args["data_type"])
            )

        return query


class EventHistoryView(ToolView):
    def __init__(self, tool):
        super().__init__(tool)
        self.table: TemplateTable = TemplateTable("", [])
        self.get_template = "tool/events.html"

    def get(self):
        self.process()
        return render_template(self.get_template, vm=self.context_vars())

    @property
    def base_query(self):
        return (
            Event.query.join(Event.org, aliased=True)
            .join(OrgType, aliased=True)
            .filter(Event.user == current_user)
        )

    @property
    def query_args(self):
        query_args = dict(request.args)
        query_args["org_type"] = self.tool.title()
        return query_args

    def process(self):
        """
        Query the Event table for events associated with the current user
        matching the search_text and/or job_id query params

        Create a Flask-SQLAlchemy paginate object using the query for
        events table rendering
        """
        query_builder = EventHistoryQuery(self.query_args, self.base_query)
        query = query_builder.process()
        query = query.order_by(desc_op(Event.timestamp))
        self.table = event_table(query)

    @classmethod
    def register(cls, app):
        view = cls.as_view("events", app.name)
        app.add_url_rule(f"/events", view_func=view)


class EventDownloadView(ToolView):
    """
    Process download request from bulk results modal.
    Returns xlsx file stream for browser download

    Registers as:
        methods POST
        endpoint: `{tool}.events_download`
        rule: `/{tool}/events/download`

    Registration requires:
        tool: 'five9', 'zoom', etc.
    """

    def __init__(self, tool):
        super().__init__(tool)
        self.query_args: dict = request.form.to_dict()
        self.data_type = self.query_args.get("data_type", "")
        self.job_id = self.query_args.get("job_id", "")

    def post(self):
        try:
            wb_stream = self.build_workbook_file()
            filename = self.build_filename()
        except ZeusCmdError as exc:
            return redirect_on_cmd_err(f"{self.tool}.events", exc)

        return send_file(wb_stream, as_attachment=True, download_name=filename)

    @property
    def event_query(self):
        base_query = (
            Event.query.join(Event.org, aliased=True)
            .join(OrgType, aliased=True)
            .filter(Event.user == current_user)
        )
        query_builder = EventHistoryQuery(self.query_args, base_query)
        query = query_builder.process()
        query = query.order_by(asc_op(Event.timestamp))
        return query

    def build_workbook_file(self):
        rows = []
        sheetname = self.data_type

        for event in self.event_query:
            result = "OK" if event.result == "Success" else "FAIL"

            row = {
                "Time": self.convert_timestamp_for_excel(event.timestamp),
                "Result": result,
                "Org Name": event.org.name,
                "Action": event.action.upper(),
                "Data Type": self.data_type.replace("_", " ").title(),
                "Object": event.entity,
                "Error": event.error,
            }

            rows.append(row)

        creator = WorkbookCreator()
        return creator.run({sheetname: rows})

    @staticmethod
    def convert_timestamp_for_excel(ts: float):
        """
        Openpyxl will automatically apply a date format to a Datetime object
        """
        try:
            return datetime.fromtimestamp(ts)
        except Exception as exc:
            log.warning(f"Event timestamp {ts} Excel conversion failed: {exc}")
            return 0

    def build_filename(self):
        filename = secure_filename(f"{self.job_id}_results.xlsx")
        return filename or "results.xlsx"

    @classmethod
    def register(cls, app):
        view = cls.as_view("events_download", app.name)
        app.add_url_rule("/events/download", view_func=view)


class AdminEventHistoryView(EventHistoryView):
    """
    GET request to the /admin/events endpoint
    Queries db for events without current_user filter
    """

    template = "admin/admin_events.html"

    @property
    def base_query(self):
        return Event.query.join(Event.org, aliased=True).join(OrgType, aliased=True)

    @property
    def query_args(self):
        return dict(request.args)


class BulkEventView(ToolView):
    """
    Provides events associated with a submission.
    After a bulk job is complete, a link is provided to show the
    results for each row through this view.

    GET request returns event details in a TemplateTable
    POST request returns event details as a file download

    Requires job_id and data_type request args

    Registers as:
        methods GET, POST
        endpoint: `{tool}.bulk_results`
        rule: `/{tool}/import/results`

    Registration requires:
        tool: 'five9', 'zoom', etc.
    """

    def __init__(self, tool):
        super().__init__(tool)
        self.job_id = request.args.get("job_id", "")
        self.data_type = request.args.get("data_type", "")
        self.get_template = "tool/bulk_results_modal.html"

    def get(self):
        """
        Render a table including events for the bulk submission
        defined by the submitted. data_type and job_id.
        """
        try:
            query = self.event_query()
            table = event_table(query)
        except ZeusCmdError as exc:
            return redirect_on_cmd_err(f"{self.tool}.bulk", exc)

        vm = self.context_vars()
        vm.update({
            "table": table,
            "total_count": query.filter().count(),
            "title": self.data_type.replace("_", " ").title(),
            "failure_count": query.filter(Event.result == "Fail").count(),
        })

        return render_template(self.get_template, vm=vm)

    def post(self):
        """
        Create a spreadsheet including events for the bulk submission
        defined by the submitted. data_type and job_id.
        Return the file for download.
        """
        try:
            query = self.event_query()
            wb_stream = event_workbook_file(query, self.data_type)
        except ZeusCmdError as exc:
            return redirect_on_cmd_err(f"{self.tool}.events", exc)

        ts = time.strftime("%m%d%Y")
        filename = (
            secure_filename(f"{self.tool}_{self.data_type}_results_{ts}.xlsx")
            or "Results.xlsx"
        )
        return send_file(wb_stream, as_attachment=True, download_name=filename)

    def event_query(self):
        """
        Create a query for events associated with a specific bulk submission.
        Query is filtered on the current user (from Flask session), job_id
        and data_type.

        Returns:
             SqlAlchemy query or raises ZeusCmdError if filter info is missing
        """
        if not self.job_id or not self.data_type:
            raise ZeusCmdError("Job ID and Data Type required to identify Bulk Job")

        query_args = dict(job_id=self.job_id, data_type=self.data_type)

        base_query = (
            Event.query.join(Event.org, aliased=True)
            .join(OrgType, aliased=True)
            .filter(Event.user == current_user)
        )
        query_builder = EventHistoryQuery(query_args, base_query)
        query = query_builder.process()
        query = query.order_by(asc_op(Event.timestamp))
        return query

    @classmethod
    def register(cls, app):
        view = cls.as_view("bulk_results", app.name)
        app.add_url_rule("/import/results", view_func=view)


def event_table(event_query):
    rows = []
    for event in event_query:
        user = "" if not event.user else event.user.email
        dtype = event.data_type or ""
        result = "OK" if event.result == "Success" else "FAIL"
        row = {
            "job_id": event.job_id,
            "timestamp": event.timestamp,
            "result": result,
            "org": event.org.name,
            "tool": event.org.org_type.name,
            "user": user,
            "action": event.action.upper(),
            "type": dtype.replace("_", " ").title(),
            "name": event.entity,
            "error": event.error,
        }
        rows.append(row)

    return TemplateTable(
        data_type="event",
        rows=rows,
        columns=[
            TemplateTableCol("job_id", "Job ID", hidden=True),
            TemplateTableCol("timestamp"),
            TemplateTableCol("result"),
            TemplateTableCol("User"),
            TemplateTableCol("tool"),
            TemplateTableCol("org"),
            TemplateTableCol("action"),
            TemplateTableCol("data_type", "Type"),
            TemplateTableCol("entity", "Object"),
            TemplateTableCol("error"),
        ],
    )


def event_workbook_file(event_query, data_type):
    """
    Create a spreadsheet with a single worksheet containing
    event records from the provided query.

    Returns:
        Workbook file as a BytesIO object
    """
    rows = []
    sheetname = data_type

    for event in event_query:
        result = "OK" if event.result == "Success" else "FAIL"

        try:
            time_value = datetime.fromtimestamp(event.timestamp)
        except Exception as exc:
            log.warning(f"Event timestamp {event.timestamp} Excel conversion failed: {exc}")
            time_value = 0

        rows.append(
            {
                "Time": time_value,
                "Action": event.action.upper(),
                "Result": "OK" if event.result == "Success" else "FAIL",
                "Object": event.entity,
                "Data Type": data_type.replace("_", " ").title(),
                "Org Name": event.org.name,
                "Error": event.error,
            }
        )

    creator = WorkbookCreator()
    return creator.run({sheetname: rows})
