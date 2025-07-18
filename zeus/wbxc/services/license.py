import re
import logging
from zeus import registry as reg
from zeus.wbxc.wbxc_models import WbxcLicense
from .shared import WbxcBulkSvc, WbxcBulkTask
from zeus.services import UploadTask, RowLoadResp
from zeus.wbxc.wbxc_models.shared import WEBEX_CALLING_LICENSE_TYPES

log = logging.getLogger(__name__)


@reg.bulk_service("wbxc", "licenses", "UPDATE")
class WbxcLicenseSvc(WbxcBulkSvc):
    """Assign/unassign Webex Calling-related licenses to Webex users."""

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.model: WbxcLicense = model
        self.current_user: dict = {}
        self.model_licenses_by_name: dict[str, str] = {}

    def run(self):
        self.current_user = self.lookup.user(name=self.model.user_email, calling_data=True)
        self.lookup_licenses()
        task = WbxcUpdateLicenseTask(self)
        task.run()
        self.rollback_tasks.append(task)

    def lookup_licenses(self):
        """
        Lookup the license names in the model and save them to a dictionary
        keyed by the returned license id
        """
        for entry in self.model.licenses:
            resp = self.lookup.license(entry.license, entry.subscription)
            self.model_licenses_by_name[entry.license] = resp["id"]


class WbxcUpdateLicenseTask(WbxcBulkTask):
    def __init__(self, svc, **kwargs):
        super().__init__(svc, **kwargs)
        self.svc: WbxcLicenseSvc = svc
        self.update_payload: dict = {}

    def run(self):
        self.build_update_payload()
        if self.update_payload:
            self.client.licenses.assign(self.update_payload)

    def build_update_payload(self):
        """
        Build the payload to add or remove the licenses included
        in the model.

        Licenses are only included in the update payload if their
        inclusion will result in a change. A license will not be
        added if it already is assigned to the user and a license will
        not be removed if it is not currently assigned to the user=
        """
        payload_licenses = []
        for model_lic in self.model.licenses:
            if self.should_include_license(model_lic):
                entry = {
                    "operation": model_lic.operation,
                    "id": self.svc.model_licenses_by_name[model_lic.license],
                }
                if model_lic.license in WEBEX_CALLING_LICENSE_TYPES and model_lic.operation == "add":
                    entry["properties"] = self.build_webex_calling_license_properties()

                payload_licenses.append(entry)

        if payload_licenses:
            self.update_payload = {
                "email": self.model.user_email,
                "personId": self.svc.current_user["id"],
                "orgId": self.svc.current_user["orgId"],
                "licenses": payload_licenses,
            }

    def should_include_license(self, model_lic) -> bool:
        is_add_op = model_lic.operation == "add"
        license_id = self.svc.model_licenses_by_name[model_lic.license]
        is_already_assigned = license_id in self.svc.current_user.get("licenses", [])

        if is_add_op:
            should_include = not is_already_assigned
        else:
            should_include = is_already_assigned

        return should_include

    def build_webex_calling_license_properties(self):
        """
        Construct the Webex calling properties object that must be included when adding
        a Webex Calling-related licenses.

        The keys included depend on the values in the model but it must be one of three
        possibilities:
        - phoneNumber only if calling_phone_number is set in the model but extension is not
        - phoneNumber and extension if both are set in the model
        - extension and locationId if extension is set in the model but calling_phone_number is not

        It is assumed model validation ensures one of these can be met
        """
        properties = {}

        if self.model.calling_phone_number:
            properties["phoneNumber"] = self.model.calling_phone_number

        if self.model.calling_extension:
            properties["extension"] = self.model.calling_extension

        if self.model.calling_extension and not self.model.calling_phone_number:
            properties["locationId"] = self.svc.lookup.location(
                self.model.calling_location
            )["id"]

        return properties

    def build_rollback_payload(self) -> dict:
        """
        Build a payload to rollback changes made by the update request by
        flipping the operation in the update payload and ensuring the calling
        properties are included if a calling license is being re-added
        """
        rollback_licenses = []
        licenses_by_id = {v: k for k, v in self.svc.model_licenses_by_name.items()}
        for payload_lic in self.update_payload.get("licenses", []):
            op = "add" if payload_lic["operation"] == "remove" else "remove"
            rollback_lic = {"id": payload_lic["id"], "operation": op}
            lic_name = licenses_by_id[payload_lic["id"]]
            if lic_name in WEBEX_CALLING_LICENSE_TYPES and op == "add":
                rollback_lic["properties"] = self.build_webex_calling_license_properties()

            rollback_licenses.append(rollback_lic)

        if rollback_licenses:
            return {
                "email": self.model.user_email,
                "personId": self.svc.current_user["id"],
                "orgId": self.svc.current_user["orgId"],
                "licenses": rollback_licenses,
            }

        return {}

    def rollback(self):
        if self.update_payload:
            rollback_payload = self.build_rollback_payload()
            if rollback_payload:
                self.client.licenses.assign(payload=rollback_payload)


@reg.upload_task("wbxc", "licenses")
class WbxcLicenseUploadTask(UploadTask):
    """
    Override of the default UploadTask class for Webex Calling Licenses to account for multiple possible instances
    of Calling Licenses per user.
    """

    def validate_row(self, idx: int, row: dict) -> RowLoadResp:
        try:
            row["licenses"] = self.build_licenses(row)
        except Exception as exc:
            return RowLoadResp(index=idx, error=str(exc))

        return super().validate_row(idx, row)

    @staticmethod
    def build_licenses(row):
        """
        Builds a list of licenses from a provided row. Extracts
        relevant license information based on specific column headers containing
        "Calling License {index}" and associates it with corresponding operations.

        Args:
            row (dict): A dictionary with column headers as keys and values representing
            associated data. The keys should contain "Calling License {index}" and
            "Operation {index}" to associate licenses and their respective
            operations.

        Returns:
            (list): A list of dictionaries, where each dictionary contains the `idx`
            (license index), `license` (license type), and `operation` (operation to perform (add/remove)).
        """
        licenses = []
        for col_header, value in row.items():
            if m := re.search(r"Calling License\s*(\d+)", col_header):
                idx = m.group(1)
                if value:
                    try:
                        subscription = row[f"Subscription {idx}"]
                    except KeyError:
                        subscription = ""

                    try:
                        operation = row[f"Operation {idx}"]
                    except KeyError:
                        raise ValueError(f"Operation {idx}: column not found")

                    licenses.append(
                        dict(
                            idx=idx,
                            license=value,
                            subscription=subscription,
                            operation=operation,
                        )
                    )

        return licenses
