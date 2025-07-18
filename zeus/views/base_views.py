import uuid
import logging
from zeus.app import db, job_queue
from typing import Optional, List, Union
from flask.views import MethodView
from flask_security import current_user
from rq.exceptions import NoSuchJobError
from zeus.flask_job_queue import ZeusJob
from zeus.shared.helpers import redirect_on_cmd_err
from zeus.exceptions import ZeusCmdError, ZeusCmdFormValidationError
from flask import session, request, flash, render_template, make_response, url_for

log = logging.getLogger(__name__)

job_queue_error = "Operation failed. Please refresh the page and try again."


class JobQueueToolView(MethodView):
    """
    Base method view for tool views that use the job queue.

    Sets the org_id based on the session cookie.
    Provides methods for handling flashing messages and
    providing instance attributes as context vars.

    `job_type` attribute used to generate job_id_prefix. Set
    to 'browse', 'export' on the respective child classes.
    """

    job_type = ""

    def __init__(self, tool):
        self.tool: str = tool
        self.job_id: str = ""
        self.job: Union[ZeusJob, None] = None
        self.org_id: str = session.get(f"{self.tool}org")
        self.messages: Optional[List[tuple]] = []

    @property
    def is_htmx_request(self) -> bool:
        return "HX-Request" in request.headers

    @property
    def job_id_prefix(self) -> str:
        """portion of a job id that uniquely identifies the tool, operation, user and org"""
        return f"{self.tool}:{self.job_type}:{current_user.id}:{self.org_id}"

    @property
    def session_key(self) -> str:
        """
        Save job ID to the session with key identified by the tool, org id and operation.
        This allows a user to have access to exports for different orgs and tools.
        """
        return f"{self.tool}_{self.org_id}_{self.job_type}"

    @property
    def job_queue(self):
        return job_queue

    def flash_message(self, message, category="danger"):
        """
        Flash the provided message using the appropriate method
        based on the request type.

        For htmx requests:
         Add the message, category tuple to the messages list so
         the flash_alert template macro can swap them into the dom.
         This requires an oob:swap element in the template rendered.

        For non-htmx requests:
         Use the normal flask mechanism to flash the messages using
         the alert_block template macro called in the base template.
        """
        self.messages.append((message, category))
        flash(message, category)

    def context_vars(self) -> dict:
        vm = self.__dict__.copy()
        vm["is_htmx_request"] = self.is_htmx_request
        return vm

    def new_job_id(self) -> str:
        """Generate a unique random job ID using the job_id_prefix"""
        return f"{self.job_id_prefix}:{uuid.uuid4()}"

    def get_job(self, job_id, raise_if_not_found=True) -> Optional[ZeusJob]:
        """
        Get the Rq Job matching the provided job_id or raise a ZeusCmdError
        if the job is not found.
        """
        try:
            return job_queue.get_job(job_id)
        except NoSuchJobError:
            if raise_if_not_found:
                log.warning(f"{self.tool} RQ job {job_id} not found")
                raise ZeusCmdError(message=job_queue_error)
            else:
                return None

    def check_job_id(self, job_id) -> None:
        """
        Verify the job_id provided in the current request is valid for the
        route, current user and active org. If not, raise ZeusCmdError.
        """
        if not self.job_id_is_valid(job_id):
            log.error(f"Job ID: {job_id} does not match expected prefix: {self.job_id_prefix}")
            raise ZeusCmdError(message=job_queue_error)

    def job_id_is_valid(self, job_id) -> bool:
        return job_id and str(job_id).startswith(self.job_id_prefix)


class ToolView(MethodView):
    """
    Base method view for tool views.

    Sets the org_id based on the session cookie.
    Provides methods for handling flashing messages and
    providing instance attributes as context vars.
    """

    def __init__(self, tool):
        self.tool: str = tool
        self.org_id: str = session.get(f"{self.tool}org")
        self.messages: Optional[List[tuple]] = []

    @property
    def is_htmx_request(self) -> bool:
        return "HX-Request" in request.headers

    def flash_message(self, message, category="danger"):
        """
        Flash the provided message using the appropriate method
        based on the request type.

        For htmx requests:
         Add the message, category tuple to the messages list so
         the flash_alert template macro can swap them into the dom.
         This requires an oob:swap element in the template rendered.

        For non-htmx requests:
         Use the normal flask mechanism to flash the messages using
         the alert_block template macro called in the base template.
        """
        self.messages.append((message, category))
        flash(message, category)

    def process(self):
        pass

    def context_vars(self) -> dict:
        vm = self.__dict__
        vm["is_htmx_request"] = self.is_htmx_request
        return vm


class CRUDView(MethodView):
    def __init__(self):
        super().__init__()
        self.messages: Optional[List[tuple]] = []

    @property
    def is_htmx_request(self):
        return "HX-Request" in request.headers

    def flash_message(self, message, category="danger"):
        """
        Flash the provided message using the appropriate method
        based on the request type.

        For htmx requests:
         Add the message, category tuple to the messages list so
         the flash_alert template macro can swap them into the dom.
         This requires an oob:swap element in the template rendered.

        For non-htmx requests:
         Use the normal flask mechanism to flash the messages using
         the alert_block template macro called in the base template.
        """
        self.messages.append((message, category))
        flash(message, category)

    def context_vars(self):
        vm = self.__dict__
        vm["is_htmx_request"] = self.is_htmx_request
        return vm

    @classmethod
    def register(cls, app, name, rule, *args, **kwargs):
        view = cls.as_view(name, *args, **kwargs)
        app.add_url_rule(rule, view_func=view)


class CRUDTableView(CRUDView):
    """
    Base method view for rendering database rows in a
    html table as part of a CRUD app.

    Methods:
        GET: Renders self.template with context_vars

    Context Vars:
        rows: List of dicts for table rows

    To Subclass:
        build_table_rows: Method that sets self.rows to a list of dicts
        template: Name of template to render

    Registration requires:
        app: app instance
        name: view name (ex: 'admin_users')
        rule: url rule (ex: /admin/users)
    """

    template = ""

    def __init__(self):
        super().__init__()
        self.rows: list = []

    def build_table_rows(self):
        pass

    def get(self):
        self.process()
        return render_template(self.template, vm=self.context_vars())

    def process(self):
        """
        Get the orgs owned by the current user for display
        in the Zoom/org landing page table.
        """
        self.build_table_rows()


class CRUDFormView(CRUDView):
    """
    Base method view for rendering create/update forms
    as part of a CRUD app.

    Methods:
        GET: Renders self.template with context_vars

    Context Vars:
        form: Form instance
        op: either 'create' or 'update'
        record: Set to db model on update operations

    To Subclass:
        prepare_record: Method called on update operations to set self.record attribute
        build_create_form: Method called on create op to set self.form attribute
        build_update_form: Method called on update op to set self.form attribute
        template: Name of template to render
        redirect_view: Redirects to this view on ZeusCmdError. (ex: 'admin.users')

    Registration requires:
        app: app instance
        name: view name (ex: 'admin_users')
        rule: url rule (ex: /admin/users)
    """

    redirect_view = ""
    redirect_params = dict()
    template = ""

    def __init__(self):
        super().__init__()
        self.op: str = ""
        self.form = None
        self.record = None

    def prepare_record(self, record_id):
        pass

    def build_create_form(self):
        pass

    def build_update_form(self):
        pass

    def get(self):
        try:
            self.process()
        except ZeusCmdError as exc:
            return redirect_on_cmd_err(self.redirect_view, exc, params=self.redirect_params)

        return render_template(self.template, vm=self.context_vars())

    def process(self):
        """
        Build an edit form for a create or update or operation
        """
        record_id = request.args.get("id")
        if record_id:
            self.op = "update"
            self.prepare_record(record_id)
            self.build_update_form()
        else:
            self.build_create_form()
            self.op = "create"


class CRUDUpdateView(CRUDView):
    """
    Base method view for processing create/update form submissions
    as part of a CRUD app.

    This can be used to subclass an update or create view.

    This assumes the template provided is the same template used to render
    the form and that template renders the full page. If a form validation error
    occurs, the response will include HX- headers to retarget the response to
    the body so the full page is rendered again.

    Methods:
        POST: Returns response with HX-Redirect header set to self.redirect_view

    Context Vars:
        form: Form instance
        op: either 'create' or 'update'
        record: Set to db model representing object created/updated

    To Subclass:
        prepare_record: Method called to set self.record attribute
        build_form: Method called set self.form attribute from request
        template: Template to render form with validation errors
        redirect_view: Redirects to this view on ZeusCmdError. (ex: 'admin.users')
        op: Set to 'update' or 'create' to identify the operation the class handles

    Registration requires:
        app: app instance
        name: view name (ex: 'admin_users')
        rule: url rule (ex: /admin/users)
    """

    redirect_view = ""
    redirect_params = dict()
    template = ""
    op = ""
    is_modal = False

    def __init__(self):
        super().__init__()
        self.form = None
        self.record = None

    def prepare_record(self):
        pass

    def build_form(self):
        pass

    def context_vars(self):
        vm = super().context_vars()
        vm["op"] = self.op
        vm["is_htmx_request"] = self.is_htmx_request
        return vm

    def post(self):
        try:
            self.process()

        except ZeusCmdFormValidationError:
            response = make_response(render_template(self.template, vm=self.context_vars()))
            if not self.is_modal:
                # Add headers to retarget htmx response to body so full page is rendered
                # TODO: once we update htmx > 1.9.3 this can use `HX-Reselect` to avoid a full page reload
                response.headers["HX-Reswap"] = "outerHTML"
                response.headers["HX-Retarget"] = "body"
            return response

        except ZeusCmdError as exc:
            return redirect_on_cmd_err(self.redirect_view, exc, params=self.redirect_params)

        response = make_response()
        response.headers["HX-Redirect"] = url_for(self.redirect_view, **self.redirect_params)
        return response

    def process(self):
        """
        Check the submitted form's validity. If invalid, stop processing
        and allow view response to show form errors.

        Check the provided credentials by making a small API call. If invalid,
        stop flash a warning and stop processing.

        Save the form data to DB. If save fails, flash a warning message
        otherwise flash a success message.
        """
        self.build_form()
        self.check_form()
        self.save_to_db()

        self.flash_message(f"Record {self.op}d", "success")

    def check_form(self):
        if not self.form.validate():
            raise ZeusCmdFormValidationError(message="form validation failed")

    def save_to_db(self):
        self.prepare_record()

        try:
            db.session.commit()
        except Exception:
            log.exception(f"{self.op.title()} operation error {self.form.data}")
            raise ZeusCmdError(message="Object save failed")


class CRUDDeleteView(CRUDView):
    """
    Base method view for processing delete requests as part of a CRUD app.

    Methods:
        POST: Returns response with HX-Refresh header

    Context Vars:
        record: Set to db model representing object to be deleted

    To Subclass:
        prepare_record: Method called to set self.record attribute
        redirect_view: Redirects to this view on ZeusCmdError. (ex: 'admin.users')

    Registration requires:
        app: app instance
        name: view name (ex: 'admin_users')
        rule: url rule (ex: /admin/users)
    """

    redirect_view = ""
    redirect_params = dict()

    def __init__(self):
        super().__init__()
        self.record = None

    def prepare_record(self):
        pass

    def post(self):
        try:
            self.process()

        except ZeusCmdError as exc:
            return redirect_on_cmd_err(self.redirect_view, exc, params=self.redirect_params)

        response = make_response()
        response.headers["HX-Refresh"] = "true"
        return response

    def process(self):
        self.prepare_record()
        self.delete_from_db()

        self.flash_message("Record deleted", "success")

    def delete_from_db(self):
        try:
            db.session.delete(self.record)
            db.session.commit()

        except Exception:
            raise ZeusCmdError("Object Removal Failed")
