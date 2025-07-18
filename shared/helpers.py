import logging
from pathlib import Path
from zeus import registry
from functools import wraps
from wtforms import StringField
from wtforms.validators import DataRequired
from flask_security.mail_util import MailUtil
from typing import Any, Union, Iterable, List
from werkzeug.datastructures import FileStorage
from ..exceptions import ZeusCmdError, ZeusMailSendError
from flask_principal import Permission, RoleNeed, PermissionDenied
from flask_security import ConfirmRegisterForm, RegisterForm, current_user
from flask import (
    Response,
    make_response,
    request,
    flash,
    url_for,
    redirect,
    current_app,
    session,
)

log = logging.getLogger(__name__)


class ZeusMailUtil(MailUtil):
    """
    Subclass of Flask-Security MailUtil to catch email send failures.
    This is provided as the `mail_util_cls` kwarg to `Security.init_app`
    Without this, the user gets a generic 500 page with no indication what to do next.
    With this, a custom Flask error handler will be invoked and provide useful information to the user.
    """

    def send_mail(
        self,
        template: str,
        subject: str,
        recipient: str,
        sender: Union[str, tuple],
        body: str,
        html: str,
        **kwargs: Any,
    ) -> None:
        try:
            super().send_mail(template, subject, recipient, sender, body, html, **kwargs)
        except Exception as exc:
            raise ZeusMailSendError(
                sender=sender, recipient=recipient, subject=subject
            ) from exc

    def validate(self, email: str) -> str:
        """
        Fail email address validation if domain is not in the `ZEUS_ALLOWED_REGISTRATION_DOMAINS`
        Flask Config value.
        """
        validated = super().validate(email)

        allowed_domains = config_value(
            "ZEUS_ALLOWED_REGISTRATION_DOMAINS", default=["cdw.com"], strict=False
        )

        # if config value is explicitly set to an empty value, allow any domain
        if allowed_domains:
            domain = validated.split("@")[-1]
            if domain.lower() not in allowed_domains:
                msg = f"Registration Requires a {','.join(allowed_domains)} email address"
                raise ValueError(msg)

        return validated


def redirect_on_cmd_err(endpoint: str, exc: ZeusCmdError, params=None) -> Response:
    """
    When a FlaskCmdErr is raised, flash the message contained in the exception
    and redirect to the provided location.

    For htmx requests, use the HX-Redirect header to trigger the redirect

    Args:
        endpoint: str (str): redirect destination
        exc (ZeusCmdError): raised exception instance
        params (dict, None): Optional query params

    Returns:
        response (Response): Response that will trigger the redirect
    """
    params = params or {}
    # exc.message = '' indicates no error should be flashed
    if exc.message:
        flash(exc.message, exc.severity)

    if "HX-Request" in request.headers:
        response = make_response()
        response.headers["HX-Redirect"] = url_for(endpoint, **params)
    else:
        response = redirect(url_for(endpoint, **params))

    return response


def page_window(current_page, total_pages, before_current=3, after_current=3) -> list:
    """
    Return a list of page numbers to include in the Html table paging controls.

    This attempts to always provide a window of the same size calculated as
        before_current + 1 + after current (7 by default)

    >>> page_window(1, 10, 3, 3)
    [1, 2, 3, 4, 5, 6, 7]
    >>> page_window(5, 10, 3, 3)
    [2, 3, 4, 5, 6, 7, 8]
    >>> page_window(9, 10, 3, 3)
    [4, 5, 6, 7, 8, 9, 10]
    >>> page_window(3, 4, 3, 3)
    [1, 2, 3, 4]
    >>> page_window(1, 1, 3, 3)
    [1]

    Args:
        current_page (int): The page currently displayed in the table
        total_pages (int): Total number of pages
        before_current (int): Number of pages to show before current page (if avail)
        after_current (int): Number of pages to show after current page (if avail)

    Returns:
        pages_in_window (list): List of page number to include in the paging control
    """
    window_size = before_current + 1 + after_current
    all_pages = list(range(1, total_pages + 1))
    if total_pages <= window_size:
        return all_pages

    current_idx = all_pages.index(current_page)
    last_idx = len(all_pages)

    start_overflow = 0
    end_overflow = 0
    start_idx = current_idx - before_current
    if start_idx < 0:
        start_idx = 0
        end_overflow = before_current - current_idx

    end_idx = current_idx + after_current + 1
    if end_idx > last_idx:
        end_idx = last_idx
        start_overflow = current_idx + after_current - last_idx + 1

    if start_idx != 0 and start_overflow:
        if start_idx - start_overflow <= 0:
            start_idx = 0
        else:
            start_idx = start_idx - start_overflow

    if end_idx != last_idx and end_overflow:
        if end_idx + end_overflow > last_idx:
            end_idx = last_idx
        else:
            end_idx = end_idx + end_overflow

    pages_in_window = all_pages[start_idx:end_idx]

    return pages_in_window


def check_file_type(file: FileStorage, file_types=None, content_types=None):
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


def config_value(key, app=None, default=None, strict=True):
    """Get a Flask configuration value.
    Lifted from flask-security utils module.
    """
    app = app or current_app
    key = key.upper()
    if strict and key not in app.config:
        raise ValueError(f"Key {key} doesn't exist")
    return app.config.get(key, default)


class FirstLastConfirmRegisterForm(ConfirmRegisterForm):
    """Used when send confirmation is enabled"""

    first_name = StringField("First Name", [DataRequired()])
    last_name = StringField("Last Name", [DataRequired()])


class FirstLastRegisterForm(RegisterForm):
    """Used when send confirmation is disabled (includes password confirmation field)."""

    first_name = StringField("First Name", [DataRequired()])
    last_name = StringField("Last Name", [DataRequired()])


def org_required(tool):
    """
    Flask view function decorator to redirect to the tool home page and
    flash a warning if the tool active org session cookie is not valid
    """

    def wrapper(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            key = f"{tool}org"
            active_org_id = session.get(key)
            try:
                current_user.active_org(tool, active_org_id)
            except Exception:
                session[key] = ""
                flash(f"No Organization Selected", "warning")
                return redirect(f"/{tool}/")

            return func(*args, **kwargs)

        return wrapped

    return wrapper


def is_enabled_app(app_name) -> bool:
    """Nav include function returns True if user is logged in and app is enabled in config"""
    if current_user and current_user.is_authenticated:
        val = str(current_app.config.get(f"ZEUS_APP_{app_name.upper()}_ENABLED", "0"))
        return val.lower() in ("1", "true", "on")
    return False


def has_all_roles(*roles) -> bool:
    """Return True if the current user is assigned all provided roles"""
    for role in roles:
        try:
            p = Permission(RoleNeed(role))
            p.test()
        except PermissionDenied:
            return False
    return True


def tool_help_url(tool):
    default = "/help/"
    if tool in request.path:
        return f"/help{request.path}"
    return default


NODEFAULT = object()


def deep_get(target, path: Union[Iterable, str], default=NODEFAULT):
    """
    Helper function to get value from deeply nested data structure
    without a lot of guard code.

    To get a deeply-nested value without raising an exception
    if a key or attribute is not present, one would do something like:
    ```
    target = {"a": {"b": {"c": {"d": "deep value"}}}}

    value = "default"
    if "a" in target:
        if "b" in target:
            if "c" in target:
                if "d" in target:
                    value = target["a"]["b"]["c"]["d"]
    ```

    Or:
    ```
    target = {"a": {"b": {"c": {"d": "deep value"}}}}
    value = (((target.get("a") or {}).get("b") or {}).get("c") or {}).get("d", "default")
    ```

    With deep_get:
    >>> obj = {"a": {"b": {"c": {"d": "deep value"}}}}
    >>> deep_get(obj,"a.b.c.d")
    'deep value'

    If the path cannot be resolved, a ValueError is raised indicating
    where the lookup failed
    >>> obj = {"a": {"b": {"c": {"d": "deep value"}}}}
    >>> deep_get(obj,"a.b.c.e")
    Traceback (most recent call last):
        ...
    ValueError: Path lookup failed. Reason: Key: 'e' not found in object: '{'d': 'deep value'}'.

    If the default argument is provided, this will be returned instead if the lookup fails
    >>> obj = {"a": {"b": {"c": {"d": "deep value"}}}}
    >>> deep_get(obj,"a.b.c.e",default='default')
    'default'

    The target can be a dictionary, object or any combination
    >>> class DataObj:
    ...     def __init__(self):
    ...         self.x = {'xx': 'deep value'}
    ...
    >>> obj = {"a": {"b": {"c": {"d": DataObj()}}}}
    >>> deep_get(obj,"a.b.c.d.x.xx")
    'deep value'

    Args:
        target: Mapping with keys to match the provided path or object with attributes
         to match the provided path
        path (str): Iterable of lookup keys or string with periods separating keys
        default: Default value to return if lookup of any key fails

    Returns:
        (Any): The value of the last key in the path or the default, if provided

    Raises:
        (ValueError): Raised if a KeyError or TypeError occurs and no default is provided
    """

    def get_item_or_attr(obj, k):
        val = getattr(obj, k, NODEFAULT)
        if val is NODEFAULT:
            try:
                val = obj[k]
            except (KeyError, TypeError):
                raise ValueError(
                    f"Path lookup failed. Reason: Key: '{k}' not found in object: '{obj}'."
                )
        return val

    if isinstance(path, str):
        path = path.split(".")

    working = target

    for key in path:
        try:
            working = get_item_or_attr(working, key)
        except ValueError:
            if default is NODEFAULT:
                raise
            return default

    return working


def ensure_all_rows_include_all_columns(rows: List[dict]) -> List[dict]:
    """
    Accumulate a set of arbitrary columns (keys containing '.') from
    all rows, then loop over the rows and add any missing columns to
    ensure all rows have the same keys.

    Once accumulated, the arbitrary columns are sorted, so they are in
    a consistent order.

    Used for exports of models with arbitrary dict fields because
    there is no guarantee all objects returned by the source
    system will have the same set of keys.

    Updated 7/2023 to support WxccQueue Call Distribution Group X
    columns. Updated static_cols logic to accumulate columns from every
    row.

    Args:
         rows (list): List of dictionaries for each worksheet row

    Returns:
        updated_rows (list): List of dicts with missing keys added
    """
    static_cols = []
    for row in rows:
        for key in row:
            if "." not in key and key not in static_cols:
                static_cols.append(key)

    dynamic_cols = set([])
    for row in rows:
        dynamic_cols.update({key for key in row if "." in key})

    all_columns = static_cols + sorted(list(dynamic_cols))

    updated_rows = []
    for row in rows:
        updated_row = {key: row.get(key, "") for key in all_columns}
        updated_rows.append(updated_row)

    return updated_rows


def actions_for_data_type(tool, data_type):
    try:
        dt = registry.get_data_type(tool, data_type)
        action_field = dt.__fields__["action"]
        return list(action_field.type_.values)
    except Exception as exc:
        log.warning(f"Could not get supported actions for {tool=}, {data_type=}")
        return ["CREATE", "UPDATE", "DELETE", "IGNORE"]


def sort_data_types(data_types: dict) -> dict:
    """
    Sort items in a data_type dict by custom sort defined in the model,
    or sort by alpha as the default if no sort_order key exists.
    Args:
         data_types (dict): Data Type dictionary

    Returns:
        data_types_sorted (dict): Sorted dict based on data type name or custom order
    """
    try:
        data_types_sorted = sorted(data_types.items(), key=lambda x: x[1].schema()['sort_order'])
    except:
        data_types_sorted = sorted(data_types.items())

    return dict(data_types_sorted)

