import re
import logging
from . import shared
from zeus import registry as reg
from ..zoom_models import ZoomDevice
from zeus.services import BrowseSvc, ExportSvc

log = logging.getLogger(__name__)


@reg.bulk_service("zoom", "devices", "CREATE")
class ZoomDeviceCreateSvc(shared.ZoomBulkSvc):

    def run(self):
        payload = self.build_payload()
        self.current = self.client.phone_devices.create(payload)

    def build_payload(self) -> dict:
        payload = self.model.to_payload(include={"display_name", "mac_address", "model"})
        payload["type"] = shared.ZOOM_DEVICE_TYPES_CREATE_VALUES.get(
            self.model.type.lower(), self.model.type
        )

        # No models for type: other but a value must be included in the payload
        if self.model.type.lower() == "other":
            payload["model"] = "other"

        if "@" in self.model.assignee:
            payload["assigned_to"] = self.model.assignee
        else:
            payload["assignee_extension_ids"] = [
                self.lookup.assignee_id(self.model.assignee)
            ]

        if self.model.template_name:
            template = self.lookup.provision_template(self.model.template_name)
            payload["provision_template_id"] = template["id"]

        return payload

    def rollback(self):
        if self.current:
            self.client.phone_users.delete(self.current["id"])


@reg.bulk_service("zoom", "devices", "UPDATE")
class ZoomDeviceUpdateSvc(shared.ZoomBulkSvc):

    def run(self):
        self.current = self.lookup.device(self.model.mac_address, self.model.type)

        for task_cls in [ZoomDeviceUpdateTask, ZoomDeviceAssigneeTask]:
            task = task_cls(self)
            task.run()
            self.rollback_tasks.append(task)


@reg.bulk_service("zoom", "devices", "DELETE")
class ZoomDeviceDeleteSvc(shared.ZoomBulkSvc):

    def run(self):
        self.current = self.lookup.device(self.model.mac_address, self.model.type)
        self.client.phone_devices.delete(self.current["id"])


class ZoomDeviceUpdateTask(shared.ZoomBulkTask):
    def run(self):
        payload = self.build_payload()
        self.client.phone_devices.update(self.svc.current["id"], payload)

    def build_payload(self):
        """
        Create a payload dictionary for an UPDATE device operation.

        display_name is always updated because it will likely be set to a default
        value by the update_device_assignees operation.
        Other values are only included if they differ.
        """
        payload = {"display_name": self.model.display_name}

        if self.model.new_mac_address:
            payload["mac_address"] = self.model.new_mac_address

        if self.model.template_name:
            template = self.svc.lookup.provision_template(self.model.template_name)
            payload["provision_template_id"] = template["id"]

        return payload


class ZoomDeviceAssigneeTask(shared.ZoomBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.assignees_removed = []
        self.assignees_added = []

    def run(self):
        assignee_updates = self.get_assignee_updates()

        for assignee_id in assignee_updates["to_remove"]:
            self.client.phone_devices.unassign_entity(self.svc.current["id"], assignee_id)
            self.assignees_removed.append(assignee_id)

        if assignee_updates["to_add"]:
            payload = {"assignee_extension_ids": assignee_updates["to_add"]}
            self.client.phone_devices.assign_entities(self.svc.current["id"], payload)
            self.assignees_added = assignee_updates["to_add"]

    def get_assignee_updates(self) -> dict:
        current_assignee_ids = set([])
        request_assignee_ids = set([])

        if "assignees" in self.svc.current:
            current_assignee_ids = {
                a["extension_id"] for a in self.svc.current["assignees"]
            }

        if self.model.assignee:
            request_assignee_ids = {self.svc.lookup.assignee_id(self.model.assignee)}

        return dict(
            to_remove=list(current_assignee_ids.difference(request_assignee_ids)),
            to_add=list(request_assignee_ids.difference(current_assignee_ids)),
        )


@reg.browse_service("zoom", "devices")
class ZoomDeviceBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = ZoomDeviceModelBuilder(self.client)

        for type_ in ("assigned", "unassigned"):
            for resp in self.client.phone_devices.list(type=type_):
                model = builder.build_model(resp)
                rows.append(model.dict())

        return rows


@reg.export_service("zoom", "devices")
class ZoomDeviceExportSvc(ExportSvc):

    def run(self) -> dict:
        rows = []
        errors = []
        data_type = ZoomDevice.schema()["data_type"]
        builder = ZoomDeviceModelBuilder(self.client)

        for type_ in ("assigned", "unassigned"):
            for resp in self.client.phone_devices.list(type=type_):
                try:
                    model = builder.build_model(resp)
                    rows.append(model)
                except Exception as exc:
                    error = getattr(exc, "message", str(exc))
                    errors.append({"name": resp.get("mac_address", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class ZoomDeviceModelBuilder:
    def __init__(self, client):
        self.client = client
        self._provision_template_map = {}
        self._assignee_email_map = {}

    def build_models(self):
        models = []

        for type_ in ("assigned", "unassigned"):
            for resp in self.client.phone_devices.list(type=type_):
                model = self.build_model(resp)
                models.append(model)

        return models

    def get_assignees(self, resp) -> str:
        """
        Get the unique identifier(s) for the device assignees.
        if the assignee is a user, this is the user's email address, which
        is not included in the response so a separate GET request is needed.
        If the assignee is a common area, this is the extension
        Return these as a comma-separated list

        Args:
            resp (dict): GET device response

        Returns:
            (str): Comma-separated identifiers
        """
        assignees = []
        assignee_objs = resp.get("assignees") or []

        for item in assignee_objs:
            if item["extension_type"] == "commonArea":
                assignee = str(item["extension_number"])
            else:
                user = self.client.phone_users.get(item["id"])
                assignee = self.get_assignee_email(item["id"])

            assignees.append(assignee)

        return ",".join(assignees)

    def get_provision_template_name(self, template_id):
        if not self._provision_template_map:
            self._provision_template_map = {
                resp["id"]: resp["name"]
                for resp in self.client.phone_provision_templates.list()
            }
        return self._provision_template_map[template_id]

    def get_assignee_email(self, user_id):
        if user_id not in self._assignee_email_map:
            user = self.client.phone_users.get(user_id)
            self._assignee_email_map[user_id] = user["email"]
        return self._assignee_email_map[user_id]

    def get_provision_data(self, device_id):
        """
        Get the provision data for a given device ID.
        
        Returns:
            dict: The provision data or an empty dictionary if unavailable.
        """
        try:
            response = self.client.phone_devices.get(device_id)
            return response.get("provision", {})
        except Exception as e:
            return {}

    def get_sip_account_details(self, provision_data):
        """
        Extract SIP account details from the provision data.
        """
        if provision_data is None:
            provision_data = {}
        sip_accounts = provision_data.get("sip_accounts", [])
        if not sip_accounts:
            return {}

        sip_account = sip_accounts[0]
        return {
            "sip_password": sip_account.get("password", ""),
            "sip_domain": sip_account.get("sip_domain", ""),
            "outbound_proxy": sip_account.get("outbound_proxy", ""),
            "user_name": sip_account.get("user_name", ""),
            "authorization_id": sip_account.get("authorization_id", ""),
        }

    def build_model(self, resp: dict, provision_data: dict = None) -> ZoomDevice:
        device_type, model = process_device_type_resp(resp)
        template_name, assignees = "", ""

        if resp.get("provision_template_id"):
            template_name = self.get_provision_template_name(resp["provision_template_id"])

        if resp.get("assignees"):
            assignees = self.get_assignees(resp)
            
        sip_details = {}
        if device_type == "other":
            provision_data = self.get_provision_data(resp["id"])
            sip_details = self.get_sip_account_details(provision_data)

        return ZoomDevice.safe_build(
            action="IGNORE",
            display_name=resp["display_name"],
            mac_address=resp["mac_address"],
            type=device_type,
            model=model,
            assignee=assignees,
            template_name=template_name,
            sip_password=sip_details.get("sip_password", ""),
            sip_domain=sip_details.get("sip_domain", ""),
            outbound_proxy=sip_details.get("outbound_proxy", ""),
            user_name=sip_details.get("user_name", ""),
            authorization_id=sip_details.get("authorization_id", ""),
        )


def process_device_type_resp(resp: dict) -> tuple:
    """
    Split the API device_type value into the type and model values
    necessary to create a device.

    The "other" device_type does not have associated device models
    so an empty string is returned as device_model in this case
    """
    resp_device_type = str(resp.get("device_type", "")).strip().lower()

    # Return other device type for processing sip provisioning account details
    if resp_device_type == "other":
        return "other", ""

    # For other device types, split type and model
    split_device_type = re.split(r"\s+", resp_device_type, maxsplit=1)
    if len(split_device_type) > 1:
        return split_device_type[0], split_device_type[1]
    return split_device_type[0], ""
