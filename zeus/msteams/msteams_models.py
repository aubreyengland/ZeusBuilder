import logging
from typing import List
from pydantic import BaseModel, Field, validator
from zeus import registry as reg
from zeus.shared import data_type_models as dm


log = logging.getLogger(__name__)


@reg.data_type("msteams", "emergency_addresses")
class MsTeamsEmergencyAddress(dm.DataTypeBase):
    """
    ### Geolocation
    The `latitude` and `longitude` fields are optional. If they are not provided, they will be looked up via the
    Azure Maps API using the address fields. Only lookups with a `high` confidence level will be accepted, anything
    lower will result in a geolocation error and the address will not be created.

    If you receive a geolocation error, you can try to fix the address based on the information provided in the error,
    or you can look up and manually enter the latitude and longitude values.

    ### Delete Action
    Deleting an address will also delete any locations/places, subnets, switches, ports, and WAPs assigned to it.
    Deleting will fail if the address has users, numbers, etc. assigned to it.
    """

    action: dm.OneOfStr(
        ("CREATE", "DELETE", "IGNORE"),
        required=True,
    ) = Field(  # type: ignore
        wb_key="Action",
        doc_notes=(
            "`UPDATE` not supported due to API limitation, if you need to update, delete first, then recreate. "
            "`DELETE` will fail if the address has users, numbers, etc. assigned to it."
        ),
    )
    description: str = Field(
        wb_key="Description",
        doc_required="Yes",
        doc_value="Description",
        test_value="Test HQ",
    )
    companyName: str = Field(
        wb_key="Company Name",
        doc_required="Yes",
        doc_value="Company name",
        test_value="XYZ Corp",
    )
    houseNumber: str = Field(
        wb_key="House Number",
        doc_required="Yes",
        doc_value="House number",
        test_value="123",
    )
    houseNumberSuffix: str = Field(
        wb_key="House Number Suffix",
        doc_required="No",
        doc_value="House number suffix",
        test_value="",
    )
    preDirectional: str = Field(
        wb_key="Pre Directional",
        doc_required="No",
        doc_value="Directional attribute which precedes the street name",
        test_value="",
    )
    streetName: str = Field(
        wb_key="Street Name",
        doc_required="Yes",
        doc_value="Street name",
        test_value="Main",
    )
    streetSuffix: str = Field(
        wb_key="Street Suffix",
        doc_required="No",
        doc_value="Street suffix",
        test_value="",
    )
    postDirectional: str = Field(
        wb_key="Post Directional",
        doc_required="No",
        doc_value="Directional attribute which follows the street name",
        test_value="",
    )
    cityOrTown: str = Field(
        wb_key="City",
        doc_required="Yes",
        doc_value="City or town",
        test_value="San Francisco",
    )
    cityOrTownAlias: str = Field(
        wb_key="City Alias",
        doc_required="No",
        doc_value="City or town alias",
        test_value="",
    )
    stateOrProvince: str = Field(
        wb_key="State",
        doc_required="Yes",
        doc_value="Two letter state code",
        test_value="CA",
    )
    postalOrZipCode: str = Field(
        wb_key="Zip Code",
        doc_required="Yes",
        doc_value="Postal or ZIP code",
        test_value="94105",
    )
    countyOrDistrict: str = Field(
        wb_key="County",
        doc_required="No",
        doc_value="County or district",
        test_value="",
    )
    country: str = Field(
        wb_key="Country",
        doc_required="Yes",
        doc_value="Two letter country code (ISO-3166 format)",
        test_value="US",
    )
    latitude: str = Field(
        wb_key="Latitude",
        doc_required="No",
        doc_value="Decimal degrees (38.8897)",
        doc_notes="Latitude will be looked up if blank",
        test_value="",
    )
    longitude: str = Field(
        wb_key="Longitude",
        doc_required="No",
        doc_value="Decimal degrees (-77.0089)",
        doc_notes="Longitude will be looked up if blank",
        test_value="",
    )
    elin: str = Field(
        wb_key="ELIN",
        doc_required="No",
        doc_value="Emergency Location Identification Number",
        doc_notes="This is used in Direct Routing EGW scenarios",
        test_value="",
    )
    companyId: str = Field(
        wb_key="Company Tax ID",
        doc_required="No",
        doc_value="Company tax ID",
        test_value="",
    )

    class Config:
        title = "Emergency Addresses"
        schema_extra = {
            "data_type": "emergency_addresses",
            "id_field": "description",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }


@reg.data_type("msteams", "emergency_locations")
class MsTeamsEmergencyLocation(dm.DataTypeBase):
    """
    ### Delete Action
    Deleting a location will also delete any subnets, switches, ports, and WAPs assigned to it. Deleting will fail if the address has users, numbers, etc. assigned to it.
    """

    action: dm.OneOfStr(
        ("CREATE", "UPDATE", "DELETE", "IGNORE"),
        required=True,
    ) = Field(  # type: ignore
        wb_key="Action",
        doc_notes="`DELETE` will fail if the location has users, numbers, etc. associated with it.",
    )
    addressDescription: str = Field(
        wb_key="Address Description",
        doc_required="Yes",
        doc_value="Existing Emergency Address description",
        doc_notes="",
        test_value="Test HQ",
    )
    name: str = Field(
        wb_key="Name",
        doc_required="Yes",
        doc_value="32 characters max, only letters, digits, `_`, `.`, and spaces are permitted.",
        doc_notes="Examples: 'Suite 1', 'Floor 1' or 'Room 101'",
        test_value="Floor 1",
    )
    newName: str = Field(
        wb_key="New Name",
        default="",
        doc_required="No",
        doc_value="",
        doc_notes="Only applicable to `UPDATE` operations",
    )
    elin: str = Field(
        wb_key="ELIN",
        doc_required="No",
        doc_value="Emergency Location Identification Number",
        doc_notes="This is used in Direct Routing EGW scenarios",
        test_value="",
    )
    createNetworkSite: dm.OptYN = Field(
        wb_key="Create Network Site",
        default="",
        doc_required="No",
        doc_notes="Defaults to `N`",
        test_value=False,
    )

    class Config:
        title = "Emergency Locations"
        schema_extra = {
            "data_type": "emergency_locations",
            "id_field": "name",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }


@reg.data_type("msteams", "subnets")
class MsTeamsSubnet(dm.DataTypeBase):
    action: dm.OneOfStr(
        ("CREATE", "UPDATE", "DELETE", "IGNORE"),
        required=True,
    ) = Field(  # type: ignore
        wb_key="Action",
    )
    subnet: str = Field(
        wb_key="Subnet",
        doc_required="Yes",
        doc_value="Network ID",
        doc_notes="Examples: the network ID for a client IP/mask of 10.10.10.150/25 is 10.10.10.128.",
        test_value="10.0.99.99",
    )
    description: str = Field(
        wb_key="Description",
        doc_required="Yes",
        doc_value="Subnet description",
        doc_notes="Examples: 'Floor 1 Subnet', 'VLAN 99'",
        test_value="Test Subnet",
    )
    addressDescription: str = Field(
        wb_key="Address Description",
        doc_required="Yes",
        doc_value="Existing address description",
        doc_notes="Examples: 'HQ', 'Main Office', 'CLE Branch'",
        test_value="Test HQ",
    )
    locationName: str = Field(
        wb_key="Location Name",
        doc_required="No",
        doc_value="Optional, existing location name",
        doc_notes="Examples: 'Floor 1', 'Room 101'",
        test_value="Floor 1",
    )

    class Config:
        title = "Subnets"
        schema_extra = {
            "data_type": "subnets",
            "id_field": "subnet",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }


@reg.data_type("msteams", "switches")
class MsTeamsSwitch(dm.DataTypeBase):
    action: dm.OneOfStr(
        ("CREATE", "UPDATE", "DELETE", "IGNORE"),
        required=True,
    ) = Field(  # type: ignore
        wb_key="Action",
    )
    chassisId: str = Field(
        wb_key="Chassis ID",
        doc_required="Yes",
        doc_value="MAC address of the switch",
        doc_notes="Examples: '00-00-00-00-00-99'",
        test_value="12-34-56-78-90-cd",
    )
    description: str = Field(
        wb_key="Description",
        doc_required="Yes",
        doc_value="Switch description",
        doc_notes="Examples: 'Floor 1 Switch 1'",
        test_value="Test Switch",
    )
    addressDescription: str = Field(
        wb_key="Address Description",
        doc_required="Yes",
        doc_value="Existing address description",
        doc_notes="Examples: 'HQ', 'Main Office', 'CLE Branch'",
        test_value="Test HQ",
    )
    locationName: str = Field(
        wb_key="Location Name",
        doc_required="No",
        doc_value="Optional, existing location name",
        doc_notes="Examples: 'Floor 1', 'Room 101'",
        test_value="Floor 1",
    )

    class Config:
        title = "Switches"
        schema_extra = {
            "data_type": "switches",
            "id_field": "chassisId",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }


@reg.data_type("msteams", "ports")
class MsTeamsPort(dm.DataTypeBase):
    action: dm.OneOfStr(
        ("CREATE", "UPDATE", "DELETE", "IGNORE"),
        required=True,
    ) = Field(  # type: ignore
        wb_key="Action",
    )
    port: str = Field(
        wb_key="Port",
        doc_required="Yes",
        doc_value="MAC address of the port or interface name",
        doc_notes="Examples: '00-00-00-00-00-99', 'GigabitEthernet1/0/1'",
        test_value="00-00-00-00-00-99",
    )
    description: str = Field(
        wb_key="Description",
        doc_required="Yes",
        doc_value="Port description",
        doc_notes="Examples: 'Floor 1 Switch 1 Port 1'",
        test_value="Test Port",
    )
    chassisId: str = Field(
        wb_key="Chassis ID",
        doc_required="Yes",
        doc_value="MAC address of the switch the port belongs to",
        doc_notes="Examples: '00-00-00-00-00-99'",
        test_value="12-34-56-78-90-cd",
    )
    addressDescription: str = Field(
        wb_key="Address Description",
        doc_required="Yes",
        doc_value="Existing address description",
        doc_notes="Examples: 'HQ', 'Main Office', 'CLE Branch'",
        test_value="Test HQ",
    )
    locationName: str = Field(
        wb_key="Location Name",
        doc_required="No",
        doc_value="Optional, existing location name",
        doc_notes="Examples: 'Floor 1', 'Room 101'",
        test_value="Floor 1",
    )

    class Config:
        title = "Ports"
        schema_extra = {
            "data_type": "ports",
            "id_field": "port",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }


@reg.data_type("msteams", "wireless_access_points")
class MsTeamsWirelessAccessPoint(dm.DataTypeBase):
    action: dm.OneOfStr(
        ("CREATE", "UPDATE", "DELETE", "IGNORE"),
        required=True,
    ) = Field(  # type: ignore
        wb_key="Action",
    )
    bssid: str = Field(
        wb_key="BSSID",
        doc_required="Yes",
        doc_value="MAC address of the wireless access point",
        doc_notes="BSSIDs follow the MAC address format and support up to two additional digits for wildcard matching.",
        test_value="00-00-00-00-00-99",
    )
    description: str = Field(
        wb_key="Description",
        doc_required="Yes",
        doc_value="Wireless access point description",
        doc_notes="Examples: 'Floor 1 WAP'",
        test_value="Test WAP",
    )
    addressDescription: str = Field(
        wb_key="Address Description",
        doc_required="Yes",
        doc_value="Existing address description",
        doc_notes="Examples: 'HQ', 'Main Office', 'CLE Branch'",
        test_value="Test HQ",
    )
    locationName: str = Field(
        wb_key="Location Name",
        doc_required="No",
        doc_value="Optional, existing location name",
        doc_notes="Examples: 'Floor 1', 'Room 101'",
        test_value="Floor 1",
    )

    class Config:
        title = "Wireless Access Points"
        schema_extra = {
            "data_type": "wireless_access_points",
            "id_field": "bssid",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }


@reg.data_type("msteams", "trusted_ips")
class MsTeamsTrustedIp(dm.DataTypeBase):
    action: dm.OneOfStr(
        ("CREATE", "UPDATE", "DELETE", "IGNORE"),
        required=True,
    ) = Field(  # type: ignore
        wb_key="Action",
    )
    ipAddress: str = Field(
        wb_key="IP Address",
        doc_required="Yes",
        doc_value="A unique and valid IPv4 or IPv6 address",
        doc_notes="Examples: '1.1.1.1', '10.0.0.0'",
        test_value="1.1.1.1",
    )
    networkRange: str = Field(
        wb_key="Network Range",
        doc_required="Yes",
        doc_value="IPv4 format subnet accepts maskbits from 0 to 32 inclusive. IPv6 format subnet accepts maskbits from 0 to 128 inclusive.",
        doc_notes="Examples: '24', '32', '64', '128'",
        test_value="32",
    )
    description: str = Field(
        wb_key="Description",
        doc_required="No",
        doc_value="Trusted IP description",
        doc_notes="Examples: 'North America', 'HQ IP'",
        test_value="HQ IP",
    )

    class Config:
        title = "Trusted IPs"
        schema_extra = {
            "data_type": "trusted_ips",
            "id_field": "ip_address",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }


NOTIFICATION_MODE_TYPES = ("NOTIFICATION_ONLY", "CONFERENCE_MUTED", "CONFERENCE_UNMUTED")


class MsTeamsEmergencyDialString(BaseModel):
    idx: int = Field(
        default=1, description="Holds the column number associated with this entry"
    )
    EmergencyDialString: str = Field()
    NotificationMode: dm.OneOfStr(NOTIFICATION_MODE_TYPES, required=False) = Field(  # type: ignore
        default=""
    )
    NotificationDialOutNumber: str | None = Field(default=None)
    NotificationGroup: str | None = Field(default=None)


@reg.data_type("msteams", "emergency_calling_policies")
class MsTeamsEmergencyCallingPolicy(dm.DataTypeBase):
    """
    ### Dial Strings
    To build policies with multiple dial strings, insert additional `Dial String X` columns.
    """

    action: dm.OneOfStr(
        ("CREATE", "UPDATE", "DELETE", "IGNORE"),
        required=True,
    ) = Field(  # type: ignore
        wb_key="Action",
    )
    Identity: str = Field(
        wb_key="Name",
        doc_required="Yes",
        test_value="Test Emergency Calling Policy",
    )
    Description: str = Field(
        wb_key="Description",
        default="",
        doc_required="No",
        test_value="Test Description",
    )
    EnhancedEmergencyServiceDisclaimer: str = Field(
        wb_key="Disclaimer",
        default="",
        doc_required="No",
        doc_notes="Shows a banner to remind end users to confirm their emergency location.",
        test_value="Test Disclaimer",
    )
    ExternalLocationLookupMode: dm.OptYN = Field(
        wb_key="External Location Lookup Mode",
        default="",
        doc_required="No",
        doc_notes="Defaults to `N`",
        test_value=True,
    )
    DialStrings: List[MsTeamsEmergencyDialString] = Field(
        default=[],
        doc_required="No",
        doc_key="Dial String 1",
        doc_value="Number or E.164 number",
        doc_notes="The number users dial to reach emergency services. **Examples:** '911', '9911'",
        test_value=lambda: [
            {
                "EmergencyDialString": "911",
                "NotificationMode": "NOTIFICATION_ONLY",
                "NotificationDialOutNumber": "12223334444",
                "NotificationGroup": "testuser@cdwprodev.com;testguest@cdwprodev.com",
            }
        ],
    )

    @classmethod
    def model_doc(cls):
        """Add Dial String 1 doc field object to model docs."""
        doc = super().model_doc()
        notification_mode_doc = dm.DataTypeFieldDoc(
            doc_name="Dial String 1 Notification Mode",
            doc_required="No",
            doc_value=", ".join("`" + t + "`" for t in NOTIFICATION_MODE_TYPES),
            doc_notes="Choose how you want to notify users in your organization when emergency services are called",
            field_type="str",
        )
        notification_number_doc = dm.DataTypeFieldDoc(
            doc_name="Dial String 1 Notification Number",
            doc_required="Conditional",
            doc_value="Number or E.164 number",
            doc_notes="**Required if** notification mode is `CONFERENCE_MUTED` or `CONFERENCE_UNMUTED`. **Example:** '+12223334444'",
            field_type="str",
        )
        notification_emails_doc = dm.DataTypeFieldDoc(
            doc_name="Dial String 1 Notification Emails",
            doc_required="Conditional",
            doc_value="One or more email addresses separated by semicolon.",
            doc_notes="**Required if** notification mode is `NOTIFICATION_ONLY`. **Example:** 'testuser@xyz.com;testuser2@xyz.com'",
            field_type="str",
        )
        # Insert notification mode entry right after the dial string entry
        try:
            idx = [d.doc_name for d in doc.doc_fields].index("Dial String 1")
            doc.doc_fields.insert(idx + 1, notification_mode_doc)
            doc.doc_fields.insert(idx + 2, notification_number_doc)
            doc.doc_fields.insert(idx + 3, notification_emails_doc)
        except Exception:
            doc.doc_fields.append(notification_mode_doc)
            doc.doc_fields.append(notification_number_doc)
            doc.doc_fields.append(notification_emails_doc)
        return doc

    def to_wb(self) -> dict:
        """Custom method to add `Dial String #` keys to the wb row dictionary"""
        row = super().to_wb()
        for DialString in sorted(self.DialStrings, key=lambda x: x.idx):
            row[f"Dial String {DialString.idx}"] = DialString.EmergencyDialString
            row[f"Dial String {DialString.idx} Notification Mode"] = (
                DialString.NotificationMode
            )
            row[f"Dial String {DialString.idx} Notification Number"] = (
                DialString.NotificationDialOutNumber
            )
            row[f"Dial String {DialString.idx} Notification Emails"] = (
                DialString.NotificationGroup
            )
        return row

    class Config:
        title = "Emergency Calling Policies"
        schema_extra = {
            "data_type": "emergency_calling_policies",
            "id_field": "identity",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }


class MsTeamsNetworkSiteSubnet(BaseModel):
    idx: int = Field(
        default=1, description="Holds the column number associated with this entry"
    )
    SubnetID: str = Field()
    MaskBits: str = Field()
    Description: str | None = Field(default=None)

    @validator("MaskBits")
    def validate_mask_bits(cls, v, values):
        """
        Validate MaskBits/Network Range is present in model
        because API does not return a helpful error message when missing.
        """
        if not v and values.get("SubnetID"):
            raise ValueError("Subnet Network Range is required")

        return v


@reg.data_type("msteams", "network_sites")
class MsTeamsNetworkSite(dm.DataTypeBase):
    """
    ### Network Region
    A new network region will be created if the one specified does not exist while creating or updating network sites.

    ### Subnets
    To build network sites with multiple subnets, insert additional `Subnet X` columns.

    ### Update Action
    Updating a network site will also update the subnets as defined in the worksheet. So if a subnet is not defined in the worksheet, it will be deleted from the network site.

    So be sure to run an export first to get the current subnets, then add or remove subnets in the worksheet as needed.

    ### Delete Action
    Deleting a network site will also delete any subnets assigned to it.
    """

    action: dm.OneOfStr(
        ("CREATE", "UPDATE", "DELETE", "IGNORE"),
        required=True,
    ) = Field(  # type: ignore
        wb_key="Action",
    )
    Identity: str = Field(
        wb_key="Name",
        doc_required="Yes",
        test_value="Test Network Site",
    )
    Description: str = Field(
        wb_key="Description",
        default="",
        doc_required="No",
        test_value="Test Description",
    )
    NetworkRegionID: str = Field(
        wb_key="Network Region",
        default="",
        doc_required="No",
        doc_notes="A new network region will be created if it does not exist",
        test_value="Test Network Region",
    )
    EnableLocationBasedRouting: dm.OptYN = Field(
        wb_key="Location Based Routing",
        default="",
        doc_required="No",
        doc_notes="Defaults to `N`",
        test_value=True,
    )
    NetworkRoamingPolicy: str = Field(
        wb_key="Network Roaming Policy",
        default="",
        doc_required="No",
        doc_notes="Defaults to `Global (Org-wide default)`",
        test_value="Test Network Roaming Policy",
    )
    EmergencyCallingPolicy: str = Field(
        wb_key="Emergency Calling Policy",
        default="",
        doc_required="No",
        doc_notes="Defaults to `Global (Org-wide default)`",
        test_value="Test Emergency Calling Policy",
    )
    EmergencyCallRoutingPolicy: str = Field(
        wb_key="Emergency Call Routing Policy",
        default="",
        doc_required="No",
        doc_notes="Defaults to `Global (Org-wide default)`",
        test_value="Test Emergency Call Routing Policy",
    )

    Subnets: List[MsTeamsNetworkSiteSubnet] = Field(
        default=[],
        doc_required="No",
        doc_key="Subnet 1",
        doc_value="Network ID",
        doc_notes="The network ID for a client IP/mask of 10.10.10.150/25 is 10.10.10.128. **Example:** '10.10.10.128'",
        test_value=lambda: [
            {
                "SubnetID": "10.0.99.0",
                "MaskBits": "24",
                "Description": "24",
            }
        ],
    )

    @classmethod
    def model_doc(cls):
        """Add Subnet 1 doc field object to model docs."""
        doc = super().model_doc()
        network_range_doc = dm.DataTypeFieldDoc(
            doc_name="Subnet 1 Network Range",
            doc_required="Conditional",
            doc_value="A number >= 0 and <= 32 for IPV4 or >= 0 and <= 128 for IPV6.",
            doc_notes="**Required if** Subnet 1 is populated",
            field_type="str",
        )
        description_doc = dm.DataTypeFieldDoc(
            doc_name="Subnet 1 Description",
            doc_required="No",
            field_type="str",
        )
        # Insert notification mode entry right after the Subnet entry
        try:
            idx = [d.doc_name for d in doc.doc_fields].index("Subnet 1")
            doc.doc_fields.insert(idx + 1, network_range_doc)
            doc.doc_fields.insert(idx + 2, description_doc)
        except Exception:
            doc.doc_fields.append(network_range_doc)
            doc.doc_fields.append(description_doc)
        return doc

    def to_wb(self) -> dict:
        """Custom method to add `Subnet #` keys to the wb row dictionary"""
        row = super().to_wb()
        for Subnet in sorted(self.Subnets, key=lambda x: x.idx):
            row[f"Subnet {Subnet.idx}"] = Subnet.SubnetID
            row[f"Subnet {Subnet.idx} Network Range"] = Subnet.MaskBits
            row[f"Subnet {Subnet.idx} Description"] = Subnet.Description
        return row

    class Config:
        title = "Network Sites"
        schema_extra = {
            "data_type": "network_sites",
            "id_field": "identity",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }
