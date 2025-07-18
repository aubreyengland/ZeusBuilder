from zeus import registry as reg
from .. import five9_models as fm
from .shared import Five9BulkSvc
from zeus.shared.helpers import deep_get
from zeus.services import BrowseSvc, ExportSvc


@reg.bulk_service("five9", "dispositions", "CREATE")
class Five9DispositionCreateSvc(Five9BulkSvc):

    def run(self):
        payload = build_payload(self.model)
        self.client.createDisposition(payload)


@reg.bulk_service("five9", "dispositions", "UPDATE")
class Five9DispositionUpdateSvc(Five9BulkSvc):

    def run(self):
        payload = build_payload(self.model)
        self.client.modifyDisposition(payload)


def build_payload(model):
    """
    Build a disposition payload based on the request provided.

    They payload should only include fields set by the user so fields
    with None as a value are excluded.

    Only include the typeParameters object for disposition types
    that use type parameters to avoid API validation failures.
    """
    payload = model.to_payload(exclude=type_param_fields, drop_unset=True)

    if model.type in fm.disposition_types_that_use_type_params:
        payload["typeParameters"] = build_type_params_payload(model)

    return payload


def build_type_params_payload(model):
    """
    Build the disposition typeParameters payload using only values explicitly
    set in the request.

    If timer is set, convert the 'days:hours:minutes' string to the
    expected payload timer dict.
    """
    type_params = model.to_payload(include=type_param_fields, drop_unset=True)

    if model.timer:
        timer_items = model.timer.split(":")
        type_params["timer"] = {
            "days": int(timer_items[0]),
            "hours": int(timer_items[1]),
            "minutes": int(timer_items[2]),
            "seconds": 0,
        }

    return type_params


@reg.bulk_service("five9", "dispositions", "DELETE")
class Five9DispositionDeleteSvc(Five9BulkSvc):

    def run(self):
        self.client.removeDisposition(self.model.name)


type_param_fields = {"timer", "attempts", "useTimer", "allowChangeTimer"}


@reg.export_service("five9", "dispositions")
class Five9DispositionExportSvc(ExportSvc):

    def run(self) -> dict:
        rows = []
        errors = []
        data_type = fm.Five9Disposition.schema()["data_type"]

        for resp in self.client.getDispositions():
            try:
                model = build_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("name", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


@reg.browse_service("five9", "dispositions")
class Five9DispositionBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        for item in self.client.getDispositions():
            model = build_model(item)
            rows.append(model.dict())

        return rows


def build_model(resp: dict):
    """
    Create a Five9Disposition instance for the provided API response.
    Object is created using the construct method to bypass validation as the
    data returned may not conform to the validation rules
    """
    type_params = resp.pop("typeParameters", None) or {}
    type_params["timer"] = parse_type_params_timer_resp(type_params)
    return fm.Five9Disposition.safe_build(action="IGNORE", **resp, **type_params)


def parse_type_params_timer_resp(type_params_resp: dict):
    """
    Convert timer API response dictionary into a string in format 'days:hours:minutes'
    """
    days = deep_get(type_params_resp, "timer.days", "0")
    hours = deep_get(type_params_resp, "timer.hours", "0")
    minutes = deep_get(type_params_resp, "timer.minutes", "0")

    return f"{days}:{hours}:{minutes}"
