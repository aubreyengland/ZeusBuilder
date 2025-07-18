import logging
from .shared import WbxcBulkSvc
from zeus import registry as reg
from zeus.services import BrowseSvc, ExportSvc
from zeus.shared.helpers import deep_get
from zeus.exceptions import ZeusBulkOpFailed
from zeus.wbxc.wbxc_simple import WbxcSimpleClient
from zeus.wbxc.wbxc_simple.base import WbxcServerFault
from zeus.wbxc.wbxc_models.numbers import MAX_NUMBERS_PER_REQUEST, WbxcNumber

log = logging.getLogger(__name__)

PLUS_SIGN = "+"


def build_phone_number_array(start_number, end_number="") -> list[str]:
    """
    Build an array of phone numbers based on start and optional end number.
    This function can handle single numbers and ranges but assumes the numbers
    have been validated and converted to E.164 format.

    Args:
        start_number (str): E.164-formatted phone number
        end_number (str): E.164-formatted phone number or empty string

    Returns:
        (list): A list of phone numbers in E.164 format with range support.
    """
    if not end_number:
        # Single phone number, no range
        return [start_number]

    # Convert start and end numbers to integers (strip leading '+')
    start_int = int(start_number.lstrip(PLUS_SIGN))
    end_int = int(end_number.lstrip(PLUS_SIGN))

    # Generate range of phone numbers with inclusive bounds
    return [f"{PLUS_SIGN}{number}" for number in range(start_int, end_int + 1)]


@reg.bulk_service("wbxc", "numbers", "CREATE")
class WbxcNumberCreateSvc(WbxcBulkSvc):
    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.location: dict = {}

    def run(self):
        self.location = self.lookup.location(self.model.location_name)
        payload = self.build_payload()
        try:
            self.current = self.client.numbers.create(
                location_id=self.location["id"], payload=payload
            )

        except WbxcServerFault as exc:
            # 400 returned if number exists in this or any other Webex Org
            # No details provided so provide a general error
            if exc.response.status_code == 400:
                raise ZeusBulkOpFailed(
                    message=(
                        f"One or more numbers in range starting {self.model.phone_number_start} "
                        f"are invalid or already exist in Webex Calling"
                    )
                )
            raise

    def build_payload(self) -> dict:
        phone_numbers = build_phone_number_array(
                self.model.phone_number_start, self.model.phone_number_end
            )
        if len(phone_numbers) > MAX_NUMBERS_PER_REQUEST:
            raise ZeusBulkOpFailed(
                message=f"Numbers in range: {len(phone_numbers)} greater than max allowed: {MAX_NUMBERS_PER_REQUEST}"
            )

        return {
            "phoneNumbers": build_phone_number_array(
                self.model.phone_number_start, self.model.phone_number_end
            ),
            "state": self.model.state,
        }

    def rollback(self):
        if self.current:
            rollback_payload = {
                "phoneNumbers": build_phone_number_array(
                    self.model.phone_number_start, self.model.phone_number_end
                )
            }
            self.client.numbers.delete(
                location_id=self.location["id"],
                payload=rollback_payload,
            )


@reg.bulk_service("wbxc", "numbers", "UPDATE")
class WbxcNumberUpdateSvc(WbxcBulkSvc):
    def run(self):
        """
        Updates the current number's configuration based on the model state.

        API only allows a number to go from INACTIVE to ACTIVE, so checks if the desired state is 'ACTIVE'
        to ensure cycles are not wasted. If so, it retrieves the
        location details using the location name and builds the payload required for
        the update. The new configuration is then applied to the current number using
        the provided location ID and payload.
        """
        if self.model.state.lower() == "active":
            location = self.lookup.location(self.model.location_name)
            payload = self.build_payload()
            self.current = self.client.numbers.update(
                location_id=location["id"], payload=payload
            )

    def build_payload(self) -> dict:
        return {
            "phoneNumbers": build_phone_number_array(
                self.model.phone_number_start, self.model.phone_number_end
            )
        }


@reg.browse_service("wbxc", "numbers")
class WbxcNumberBrowseSvc(BrowseSvc):
    def run(self):
        """
        Builds a list of dictionary representations of number models from responses.

        The method processes the response objects retrieved from the client's numbers
        list, constructs models using `WbxcNumberModelBuilder`, converts the models
        into dictionaries, and collects them in a list.
        """
        rows = []
        builder = WbxcNumberModelBuilder(self.client)

        for resp in self.client.numbers.list():
            model = builder.build_model(resp)
            row = model.dict()
            rows.append(row)

        return rows


@reg.export_service("wbxc", "numbers")
class WbxcNumberExportSvc(ExportSvc):
    def run(self):
        rows = []
        errors = []
        data_type = WbxcNumber.schema()["data_type"]
        builder = WbxcNumberModelBuilder(self.client)

        for resp in self.client.numbers.list():
            try:
                model = builder.build_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("phoneNumber", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": errors}}


class WbxcNumberModelBuilder:

    def __init__(self, client):
        self.client: WbxcSimpleClient = client

    def build_model(self, resp):
        """
        Builds and returns a WbxcNumber instance using the given response data.

        This method processes the provided response data and creates a fully constructed
        WbxcNumber object by securely utilizing the safe_build functionality, along
        with invoking the summary_data method to extract necessary attributes.

        Args:
            resp (dict): The response object containing data to be used for building the
                WbxcNumber instance.

        Returns:
            A WbxcNumber object constructed using the extracted and processed response
            data.
        """
        return WbxcNumber.safe_build(**self.summary_data(resp))

    @staticmethod
    def summary_data(resp: dict) -> dict:
        """
        Generate a summary dictionary from the given response data.

        This static method processes the input dictionary to extract specific
        information about a location's owner and contact details. Data is
        collected using keys from the response and combined into a structured
        output dictionary. The method creates a full owner name by concatenating
        the first and last names retrieved from the response.

        Args:
            resp (dict): The input dictionary containing response data.

        Returns:
            (dict): A dictionary containing the summarized information with fields
            for phone number, extension, location name, state, owner type, and
            owner name.
        """
        name = (
            deep_get(resp, "owner.firstName", "")
            + " "
            + deep_get(resp, "owner.lastName", "")
        )

        return dict(
            phone_number_start=resp.get("phoneNumber", ""),
            extension=resp.get("extension", ""),
            location_name=deep_get(resp, "location.name"),
            state=resp.get("state", ""),
            owner_type=deep_get(resp, "owner.type", ""),
            owner_name=name,
        )
