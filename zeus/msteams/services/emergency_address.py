import logging
from requests import Session, Response

from .shared import (
    MsTeamsBulkSvc,
    MsTeamsEmergencyLocationDeleteTask,
    MsTeamsSubnetDeleteTask,
    MsTeamsSwitchDeleteTask,
    MsTeamsPortDeleteTask,
    MsTeamsWAPDeleteTask,
)
from zeus import registry as reg
from zeus.exceptions import ZeusBulkOpFailed
from zeus.services import BrowseSvc, ExportSvc
from ..msteams_models import MsTeamsEmergencyAddress
from ..msteams_simple import MsTeamsSimpleClient, MsTeamsServerFault

log = logging.getLogger(__name__)


@reg.bulk_service("msteams", "emergency_addresses", "CREATE")
class MsTeamsEmergencyAddressCreateSvc(MsTeamsBulkSvc):

    def __init__(self, client, model, azure_maps_api_key, **kwargs):
        super().__init__(client, model, **kwargs)
        self.azure_maps = AzureMapsClient(azure_maps_api_key)

    def run(self):
        self.lookup.emergency_address(self.model.description, raise_if_exists=True)
        payload = self.model.to_payload()
        payload = self.validation(payload)
        payload["latitude"], payload["longitude"] = self.get_lat_lon(payload)
        self.current = self.client.emergency_addresses.create(payload)

    def validation(self, payload):
        """
        Validates the payload for an emergency address. Nulls empty strings on optional fields.

        Args:
            payload (dict): The payload to validate.

        Raises:
            ZeusBulkOpFailed: If any required fields are missing or if they are not in the correct format.

        Returns:
            dict: The validated payload.
        """
        # Validate required fields
        if len(payload["description"]) < 1:
            raise ZeusBulkOpFailed("Description is required")
        if len(payload["companyName"]) < 1:
            raise ZeusBulkOpFailed("Company Name is required")
        if len(payload["houseNumber"]) < 1:
            raise ZeusBulkOpFailed("House Number is required")
        if len(payload["streetName"]) < 1:
            raise ZeusBulkOpFailed("Street Name is required")
        if len(payload["cityOrTown"]) < 1:
            raise ZeusBulkOpFailed("City is required")
        if len(payload["postalOrZipCode"]) < 1:
            raise ZeusBulkOpFailed("Zip Code is required")

        # Validate state and country
        if len(payload["stateOrProvince"]) < 2:
            raise ZeusBulkOpFailed("State is required, two letter format preferred")
        if len(payload["country"]) != 2:
            raise ZeusBulkOpFailed(
                "Country is required, must be a two letter code (ISO-3166 format)"
            )

        # None the optional fields if they are empty strings
        for key in payload:
            if payload[key] == "":
                payload[key] = None

        return payload

    def get_lat_lon(self, payload: dict) -> tuple[str, str]:
        """
        Get the latitude and longitude of the given payload.

        If the payload already contains latitude and longitude, they are returned as is.

        Otherwise, the latitude and longitude are looked up using the Azure Maps API.

        Args:
            payload (dict): The payload containing the address parts.

        Returns:
            tuple: The latitude and longitude.
        """
        if payload.get("latitude") and payload.get("longitude"):
            return payload["latitude"], payload["longitude"]

        # Build queries from payload
        query_parts = [
            self.build_address_line(payload),
            payload["cityOrTown"],
            payload["stateOrProvince"],
            payload["postalOrZipCode"],
            payload["country"],
        ]
        display_query = ", ".join(query_parts)
        api_query = " ".join(query_parts)

        # Get Geocoding
        try:
            resp = self.azure_maps.geocode(query=api_query)
        except Exception as e:
            raise ZeusBulkOpFailed(f"Geolocation error: {e}")

        # Check response
        if not resp.get("features") or len(resp["features"]) == 0:
            raise ZeusBulkOpFailed(
                f"Geolocation error '{display_query}' not found. Verify the address is correct or manually add the latitude and longitude to the worksheet."
            )
        elif len(resp["features"]) > 1:
            raise ZeusBulkOpFailed(
                f"Geolocation error '{display_query}' returned multiple results. Verify the address is correct or manually add the latitude and longitude to the worksheet."
            )

        result = resp["features"][0]

        if result["properties"]["type"] != "Address":
            raise ZeusBulkOpFailed(
                f"Geolocation error '{display_query}' returned '{result['properties']['address']['formattedAddress']}' with '{result['properties']['type']}' instead of 'Address'. Verify the address is correct or manually add the latitude and longitude to the worksheet."
            )
        elif result["properties"]["confidence"] != "High":
            raise ZeusBulkOpFailed(
                f"Geolocation error '{display_query}' returned '{result['properties']['address']['formattedAddress']}' with confidence of '{result['properties']['confidence']}'. Verify the address is correct or manually add the latitude and longitude to the worksheet."
            )
        elif "Good" not in result["properties"]["matchCodes"]:
            raise ZeusBulkOpFailed(
                f"Geolocation error '{display_query}' returned '{result['properties']['address']['formattedAddress']}' with no 'Good' match code. Verify the address is correct or manually add the latitude and longitude to the worksheet."
            )

        # Get latitude and longitude from cordinates list
        # `The first two elements are longitude and latitude, precisely in that order.`
        # https://learn.microsoft.com/en-us/rest/api/maps/search/get-geocoding#geojsonpoint

        latitude = result["geometry"]["coordinates"][1]
        longitude = result["geometry"]["coordinates"][0]

        return latitude, longitude

    @staticmethod
    def build_address_line(payload: dict) -> str:
        """
        Get the address line from the payload.

        Args:
            payload (dict): The payload containing the address parts.

        Returns:
            str: The address line.
        """
        address_line = (
            f"{payload['houseNumber'] or ''} {payload['houseNumberSuffix'] or ''} {payload['preDirectional'] or ''} "
            f"{payload['streetName'] or ''} {payload['streetSuffix'] or ''} {payload['postDirectional'] or ''}"
        )
        return " ".join(address_line.split())


@reg.bulk_service("msteams", "emergency_addresses", "DELETE")
class MsTeamsEmergencyAddressDeleteSvc(MsTeamsBulkSvc):

    def __init__(self, client, model, **kwargs):
        super().__init__(client, model, **kwargs)
        self.locations_to_remove: list[dict] = []
        self.subnets_to_remove: list[dict] = []
        self.switches_to_remove: list[dict] = []
        self.ports_to_remove: list[dict] = []
        self.waps_to_remove: list[dict] = []

    def run(self):
        self.current = self.lookup.emergency_address(
            self.model.to_payload(), raise_if_multiple=False
        )
        self.check_if_address_is_in_use()
        self.get_locations_for_deletion()
        self.get_subnets_for_deletion()
        self.get_switches_for_deletion()
        self.get_ports_for_deletion()
        self.get_waps_for_deletion()
        self.delete_subnets()
        self.delete_switches()
        self.delete_ports()
        self.delete_waps()
        self.delete_locations()
        self.delete_address()

    def check_if_address_is_in_use(self):
        if (
            self.current["numberOfVoiceUsers"] > 0
            or self.current["numberOfTelephoneNumbers"] > 0
        ):
            raise ZeusBulkOpFailed(
                f"Failed to delete address because {self.current['numberOfVoiceUsers']} users and {self.current['numberOfTelephoneNumbers']} phone numbers are assigned to it."
            )

    def get_locations_for_deletion(self):
        self.locations_to_remove = self.client.emergency_locations.list(
            civicAddressId=self.current["id"],
            populateUsersAndNumbers=True,
        )

    def get_subnets_for_deletion(self):
        for subnet in self.client.subnets.list():
            if subnet["locationId"] in [
                location["id"] for location in self.locations_to_remove
            ]:
                self.subnets_to_remove.append(subnet)

    def get_switches_for_deletion(self):
        for switch in self.client.switches.list():
            if switch["locationId"] in [
                location["id"] for location in self.locations_to_remove
            ]:
                self.switches_to_remove.append(switch)

    def get_ports_for_deletion(self):
        for port in self.client.ports.list():
            if port["locationId"] in [
                location["id"] for location in self.locations_to_remove
            ]:
                self.ports_to_remove.append(port)

    def get_waps_for_deletion(self):
        for wap in self.client.waps.list():
            if wap["locationId"] in [
                location["id"] for location in self.locations_to_remove
            ]:
                self.waps_to_remove.append(wap)

    def delete_subnets(self):
        for subnet in self.subnets_to_remove:
            task = MsTeamsSubnetDeleteTask(self, subnet)
            task.run()
            self.rollback_tasks.append(task)

    def delete_switches(self):
        for switch in self.switches_to_remove:
            task = MsTeamsSwitchDeleteTask(self, switch)
            task.run()
            self.rollback_tasks.append(task)

    def delete_ports(self):
        for port in self.ports_to_remove:
            task = MsTeamsPortDeleteTask(self, port)
            task.run()
            self.rollback_tasks.append(task)

    def delete_waps(self):
        for wap in self.waps_to_remove:
            task = MsTeamsWAPDeleteTask(self, wap)
            task.run()
            self.rollback_tasks.append(task)

    def delete_locations(self):
        for location in self.locations_to_remove:
            if location["isDefault"]:
                continue  # skip default location, will be deleted with address
            task = MsTeamsEmergencyLocationDeleteTask(self, location)
            task.run()
            self.rollback_tasks.append(task)

    def delete_address(self):
        self.client.emergency_addresses.delete(self.current["id"])


@reg.browse_service("msteams", "emergency_addresses")
class MsTeamsEmergencyAddressBrowseSvc(BrowseSvc):

    def run(self):
        rows = []
        builder = MsTeamsEmergencyAddressModelBuilder(self.client)

        for resp in builder.get_emergency_addresses():
            model = builder.build_model(resp)
            rows.append(resp)

        return rows


@reg.export_service("msteams", "emergency_addresses")
class MsTeamsEmergencyAddressExportSvc(ExportSvc):

    def run(self):
        rows = []
        errors = []
        data_type = MsTeamsEmergencyAddress.schema()["data_type"]
        builder = MsTeamsEmergencyAddressModelBuilder(self.client)

        for resp in builder.get_emergency_addresses():
            try:
                model = builder.build_model(resp)
                rows.append(model)
            except Exception as exc:
                error = getattr(exc, "message", str(exc))
                errors.append({"name": resp.get("description", "unknown"), "error": error})

        return {data_type: {"rows": rows, "errors": []}}


class MsTeamsEmergencyAddressModelBuilder:
    """
    Shared model builder class for MS Teams Emergency Address
    Browse and Export services.
    """

    def __init__(self, client):
        self.client: MsTeamsSimpleClient = client

    def get_emergency_addresses(self):
        """Return list of emergency addresses"""
        try:
            return list(self.client.emergency_addresses.list())
        except MsTeamsServerFault:
            return []

    @staticmethod
    def build_model(resp):
        model = MsTeamsEmergencyAddress.safe_build(resp)
        return model


class AzureMapsClient(Session):
    """
    Azure Maps API client.
    """

    def __init__(self, azure_maps_api_key: str):
        super().__init__()
        self.base_url = "https://atlas.microsoft.com"
        self.headers.update(
            {
                "subscription-key": azure_maps_api_key,
            }
        )

    def send_request(self, method, url, **kwargs):
        resp = self.request(method, url, **kwargs)

        log.debug(f"Azure Maps Geocode GET Response {resp.status_code} {resp.reason}")

        self.check_response(resp)

        return resp

    def check_response(self, resp: Response):
        if resp.ok:
            return

        try:
            json = resp.json()
            # Default to common error message keys
            message = json.get("detail") or json.get("message") or json
            # Azure Maps errors are usually nested in an "error" key
            if "error" in json:
                message = json["error"].get("message") or json["error"]
        except Exception:
            message = resp.text

            if resp.text == "":
                message = "Azure Maps API unknown error."

        raise Exception(message)

    def geocode(self, query: str) -> dict:
        """
        Get geocode information for a given query.

        https://learn.microsoft.com/en-us/rest/api/maps/search/get-geocoding

        Args:
            query (str): The address to geocode.

        Returns:
            dict: The geocoded address information.
        """

        url = f"{self.base_url}/geocode"
        params = {
            "api-version": "2025-01-01",
            "top": 1,
            "query": query,
        }
        resp = self.send_request("GET", url, params=params)
        return resp.json()
