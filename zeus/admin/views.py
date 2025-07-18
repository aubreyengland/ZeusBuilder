import logging
from uuid import uuid4
from . import admin, forms
from datetime import datetime
from zeus.app import security
from flask_login import current_user
from flask import render_template, request
from zeus.models import User, Role, OAuthApp
from flask_security.utils import hash_password
from zeus.exceptions import ZeusCmdError, ZeusMailSendError
from zeus.views import base_views as crud, event_views as ev
from zeus.shared.helpers import redirect_on_cmd_err, make_response
from flask_security.recoverable import send_reset_password_instructions


log = logging.getLogger(__name__)


ADMIN_OPTIONS = [
    {
        "name": "users",
        "title": "Users",
        "route": "admin.users",
        "text": "Manage Zeus Users",
    },
    {
        "name": "oauth",
        "title": "OAuth",
        "route": "admin.oauth",
        "text": "Manage OAuth Apps",
    },
    {
        "name": "roles",
        "title": "Roles",
        "route": "admin.roles",
        "text": "Manage Zeus Roles",
    },
    {
        "name": "events",
        "title": "Events",
        "route": "admin.events",
        "text": "View Events for all Users",
    },
]


@admin.context_processor
def admin_ctx():
    return {
        "tool": "admin",
        "title": "Admin",
        "options": ADMIN_OPTIONS,
    }


@admin.get("/")
def admin_home():
    return render_template("admin/admin_home.html")


class AdminUserTableView(crud.CRUDTableView):
    template = "admin/admin_users.html"

    def build_table_rows(self):
        self.rows = User.query


class AdminUserFormView(crud.CRUDFormView):
    template = "admin/admin_modal.html"
    redirect_view = "admin.users"

    def prepare_record(self, record_id):
        self.record = lookup_user(record_id, current_user_ok=True)

    def build_create_form(self):
        self.form = forms.create_user_form()

    def build_update_form(self):
        self.form = forms.update_user_form(request.form, obj=self.record)
        self.form.roles.data = [str(r.id) for r in self.record.roles]

        if self.record.confirmed_at:
            self.form.confirmed.data = True
        else:
            self.form.confirmed.data = False

    def context_vars(self):
        vm = super().context_vars()
        vm["user"] = self.record
        vm["partial_template"] = f"admin/admin_users_form.html"
        return vm


class AdminUserCreateView(crud.CRUDUpdateView):
    op = "create"
    is_modal = True
    redirect_view = "admin.users"
    template = "admin/admin_users_form.html"

    def build_form(self):
        self.form = forms.create_user_form(request.form)

    def prepare_record(self):
        """
        Convert data from the validated create form into the formats
        expected by the User record.

        This includes:
         - Hash the clear text password from the password field
         - Convert the confirmed value of True to a datetime
         - Convert any role Ids to Role instances
        """
        hashed_pw = hash_password(self.form.password.data)

        if self.form.confirmed.data:
            confirmed_at = datetime.utcnow()
        else:
            confirmed_at = None

        if self.form.roles.data:
            roles = [Role.query.get(int(r)) for r in self.form.roles.data]
        else:
            roles = []

        user = security.datastore.create_user(
            email=self.form.email.data,
            password=hashed_pw,
            first_name=self.form.first_name.data,
            last_name=self.form.last_name.data,
            active=self.form.active.data,
            confirmed_at=confirmed_at,
            roles=roles,
        )

        self.record = user


class AdminUserUpdateView(crud.CRUDUpdateView):
    op = "update"
    is_modal = True
    redirect_view = "admin.users"
    template = "admin/admin_users_form.html"

    def build_form(self):
        self.form = forms.update_user_form(request.form)

    def prepare_record(self):
        """
        Query the database for the user associated with the id in the form.

        Convert data from the validated form into the expected formats
        and update the User record accordingly
        """
        user = lookup_user(self.form.id.data, raise_if_not_found=True, current_user_ok=True)
        user.email = self.form.email.data
        user.first_name = self.form.first_name.data
        user.last_name = self.form.last_name.data
        user.active = self.form.active.data

        if not self.form.confirmed.data:
            user.confirmed_at = None
        elif not user.confirmed_at:
            user.confirmed_at = datetime.utcnow()

        if self.form.roles.data:
            user.roles = [Role.query.get(int(r)) for r in self.form.roles.data]
        else:
            user.roles = []

        self.record = user


class AdminUserDeleteView(crud.CRUDDeleteView):
    redirect_view = "admin.users"

    def prepare_record(self):
        to_delete_id = request.args.get("id")
        self.record = lookup_user(
            to_delete_id, current_user_ok=False, raise_if_not_found=True
        )


class AdminUserPasswordResetView(crud.CRUDView):
    redirect_view = "admin.users"

    def __init__(self):
        super().__init__()
        self.record = None

    def prepare_record(self):
        to_reset_id = request.args.get("id")
        self.record = lookup_user(
            to_reset_id, current_user_ok=True, raise_if_not_found=True
        )

    def post(self):
        try:
            self.process()

        except ZeusCmdError as exc:
            return redirect_on_cmd_err(self.redirect_view, exc)

        response = make_response()
        response.headers["HX-Refresh"] = "true"
        return response

    def process(self):
        """
        Reset the password and session cookie and send password reset
        email for the selected user.
        """
        self.prepare_record()
        self.reset_access()
        self.send_reset_email()

        self.flash_message(f"Password reset link sent to {self.record.email}", "info")

    def reset_access(self):
        """
        Reset the user's password to a random value and use the
        Flask-Security reset_user_access method to reset the users session cookie.
        """
        try:
            self.record.password = hash_password(uuid4().hex)
            security.datastore.reset_user_access(self.record)
        except Exception:
            log.exception(f"Reset user access for '{self.record.email}' failed")
            raise ZeusCmdError(f"Reset user access for '{self.record.email}' failed")

    def send_reset_email(self):
        """
        Send email to the user's email address with a link
        to reset their password.
        """
        try:
            send_reset_password_instructions(self.record)
        except ZeusMailSendError:
            raise ZeusCmdError("Email could not be sent")
        except Exception as exc:
            log.exception("Unhandled password reset error")
            raise ZeusCmdError(f"Unhandled Error: {exc}")


class AdminRoleTableView(crud.CRUDTableView):
    template = "admin/admin_roles.html"

    def build_table_rows(self):
        rows = []
        for role in Role.query:
            rows.append({"id": role.id, "name": role.name, "members": len(role.users)})

        self.rows = rows


class AdminRoleFormView(crud.CRUDFormView):
    template = "admin/admin_modal.html"
    redirect_view = "admin.roles"
    is_modal = True

    def prepare_record(self, record_id):
        self.record = lookup_role(record_id)

    def build_create_form(self):
        self.form = forms.role_form()

    def build_update_form(self):
        self.form = forms.role_form(request.form, obj=self.record)
        self.form.users.data = [str(u.id) for u in self.record.users]

    def context_vars(self):
        vm = super().context_vars()
        vm["role"] = self.record
        vm["partial_template"] = f"admin/admin_roles_form.html"
        return vm


class AdminRoleCreateView(crud.CRUDUpdateView):
    op = "create"
    is_modal = True
    redirect_view = "admin.roles"
    template = "admin/admin_roles_form.html"

    def build_form(self):
        self.form = forms.role_form(request.form)

    def prepare_record(self):
        if self.form.users.data:
            users = [User.query.get(int(u)) for u in self.form.users.data]
        else:
            users = []

        role = security.datastore.create_role(name=self.form.name.data, users=users)

        self.record = role


class AdminRoleUpdateView(crud.CRUDUpdateView):
    op = "update"
    is_modal = True
    redirect_view = "admin.roles"
    template = "admin/admin_roles_form.html"

    def build_form(self):
        self.form = forms.role_form(request.form)

    def prepare_record(self):
        role = lookup_role(self.form.id.data, raise_if_not_found=True)
        role.name = self.form.name.data

        if self.form.users.data:
            role.users = [User.query.get(int(r)) for r in self.form.users.data]
        else:
            role.users = []

        self.record = role


class AdminRoleDeleteView(crud.CRUDDeleteView):
    redirect_view = "admin.roles"

    def prepare_record(self):
        to_delete_id = request.args.get("id")
        self.record = lookup_role(to_delete_id, raise_if_not_found=True)


class AdminOAuthTableView(crud.CRUDTableView):
    template = "admin/admin_oauth.html"

    def build_table_rows(self):
        self.rows = OAuthApp.query.order_by(OAuthApp.name).all()


class AdminOAuthFormView(crud.CRUDFormView):
    template = "admin/admin_modal.html"
    redirect_view = "admin.oauth"

    def prepare_record(self, record_id):
        self.record = lookup_oauth(record_id)

    def build_create_form(self):
        org_type = request.args.get("org_type")
        self.form = forms.create_oauth_form(org_type)

    def build_update_form(self):
        org_type = self.record.org_type.name
        self.form = forms.update_oauth_form(request.form, org_type, obj=self.record)
        if hasattr(self.form, "scopes"):
            self.form.scopes.data = self.record.scopes

        if self.record.user_id:
            self.form.user.data = str(self.record.user_id)

    def context_vars(self):
        vm = super().context_vars()
        vm["oauth"] = self.record
        vm["partial_template"] = f"admin/admin_oauth_form.html"
        return vm

    def get(self):
        try:
            self.process()
        except ZeusCmdError as exc:
            return redirect_on_cmd_err(self.redirect_view, exc)

        if "org_type" in request.args:
            # org_type arg means this is a request to get the scopes after an org type was selected
            # in the create form so only render the form
            template = "admin/admin_oauth_form.html"
        else:
            # if org_type arg is not present, user clicked the create button so render the create form modal
            template = "admin/admin_modal.html"

        return render_template(template, vm=self.context_vars())


class AdminOAuthCreateView(crud.CRUDUpdateView):
    op = "create"
    redirect_view = "admin.oauth"
    template = "admin/admin_oauth_form.html"
    is_modal = True

    def build_form(self):
        org_type = request.form.get("org_type")
        self.form = forms.update_oauth_form(request.form, org_type)

    def prepare_record(self):
        """
        Ensure either is_global is True or a valid user was
        selected as the owner.
        """
        scopes = self.form.scopes.data if hasattr(self.form, "scopes") else None
        user = None
        if not self.form.is_global.data:
            try:
                user = User.query.get(int(self.form.user.data))
            except Exception:
                raise ZeusCmdError(f"Invalid user selection")

        self.record = OAuthApp.create(
            org_type=self.form.org_type.data,
            name=self.form.name.data,
            is_global=self.form.is_global.data,
            user=user,
            client_id=self.form.client_id.data,
            client_secret=self.form.client_secret.data,
            redirect_uri=self.form.redirect_uri.data,
            api_endpoint=self.form.api_endpoint.data,
            auth_endpoint=self.form.auth_endpoint.data,
            token_endpoint=self.form.token_endpoint.data,
            scopes=scopes,
        )


class AdminOAuthUpdateView(crud.CRUDUpdateView):
    op = "update"
    redirect_view = "admin.oauth"
    template = "admin/admin_oauth_form.html"
    is_modal = True

    def build_form(self):
        org_type = request.form.get("org_type")
        self.form = forms.update_oauth_form(request.form, org_type)

    def prepare_record(self):
        record = lookup_oauth(int(self.form.id.data))
        record.name = self.form.name.data
        record.is_global = self.form.is_global.data
        record.client_id = self.form.client_id.data
        record.client_secret = self.form.client_secret.data
        record.redirect_uri = self.form.redirect_uri.data
        record.api_endpoint = self.form.api_endpoint.data
        record.auth_endpoint = self.form.auth_endpoint.data
        record.token_endpoint = self.form.token_endpoint.data

        if hasattr(self.form, "scopes"):
            record.scopes = self.form.scopes.data

        if self.form.is_global.data:
            record.user = None
        else:
            try:
                record.user = User.query.get(int(self.form.user.data))
            except Exception:
                raise ZeusCmdError(f"Invalid user selection")

        self.record = record


class AdminOAuthDeleteView(crud.CRUDDeleteView):
    redirect_view = "admin.oauth"

    def prepare_record(self):
        to_delete_id = request.args.get("id")
        self.record = lookup_oauth(to_delete_id, raise_if_not_found=True)

        if (
            OAuthApp.query.filter(OAuthApp.org_type_id == self.record.org_type_id).count()
            == 1
        ):
            raise ZeusCmdError(f"Cannot remove last {self.record.org_type.name} OAuth App")


def lookup_user(user_id, current_user_ok=True, raise_if_not_found=False):
    try:
        user_id = int(user_id)
    except Exception:
        log.exception(f"Invalid User ID: '{user_id}'")
        raise ZeusCmdError(f"Invalid User ID: '{user_id}'")

    user = User.query.filter_by(id=user_id).first()

    if not user and raise_if_not_found:
        raise ZeusCmdError(f"User with ID: {user_id} Not Found")

    if not current_user_ok and (user.id == current_user.id):
        raise ZeusCmdError(f"Operation not permitted on current user.")

    return user


def lookup_role(role_id, raise_if_not_found=False):
    try:
        role_id = int(role_id)
    except Exception:
        log.exception(f"Invalid Role ID: '{role_id}'")
        raise ZeusCmdError(f"Invalid Role ID: '{role_id}'")

    role = Role.query.filter_by(id=role_id).first()

    if not role and raise_if_not_found:
        raise ZeusCmdError(f"Role with ID: {role_id} Not Found")

    return role


def lookup_oauth(oauth_id, raise_if_not_found=False):
    try:
        oauth_id = int(oauth_id)
    except Exception:
        log.exception(f"Invalid OAuth App ID: '{oauth_id}'")
        raise ZeusCmdError(f"Invalid OAuth App ID: '{oauth_id}'")

    record = OAuthApp.query.filter_by(id=oauth_id).first()

    if not record and raise_if_not_found:
        raise ZeusCmdError(f"OAuthApp with ID: {oauth_id} Not Found")

    return record


ev.AdminEventHistoryView.register(admin)
AdminUserTableView.register(admin, name="users", rule="/users")
AdminUserFormView.register(admin, name="users_form", rule="/users/form")
AdminUserCreateView.register(admin, name="users_create", rule="/users/create")
AdminUserUpdateView.register(admin, name="users_update", rule="/users/update")
AdminUserDeleteView.register(admin, name="users_delete", rule="/users/delete")
AdminUserPasswordResetView.register(admin, name="users_reset", rule="/users/reset")
AdminRoleTableView.register(admin, name="roles", rule="/roles")
AdminRoleFormView.register(admin, name="roles_form", rule="/roles/form")
AdminRoleCreateView.register(admin, name="roles_create", rule="/roles/create")
AdminRoleUpdateView.register(admin, name="roles_update", rule="/roles/update")
AdminRoleDeleteView.register(admin, name="roles_delete", rule="/roles/delete")
AdminOAuthTableView.register(admin, name="oauth", rule="/oauth")
AdminOAuthFormView.register(admin, name="oauth_form", rule="/oauth/form")
AdminOAuthCreateView.register(admin, name="oauth_create", rule="/oauth/create")
AdminOAuthUpdateView.register(admin, name="oauth_update", rule="/oauth/update")
AdminOAuthDeleteView.register(admin, name="oauth_delete", rule="/oauth/delete")
