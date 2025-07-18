import re
import logging
from typing import List
from enum import StrEnum
from zeus import registry as reg
from zeus.shared import data_type_models as dm
from zeus.exceptions import ZeusConversionError
from pydantic import validator, Field, EmailStr

log = logging.getLogger(__name__)

LICENSE_TYPE = [
    (1, "Basic"),
    (2, "Licensed"),
    (3, "On-Premise"),  # NOT Documented
    (4, "No Meetings License"),  # NOT Documented
    (99, "None"),
]

PRONOUNS_OPTION = [
    (1, "Ask user every time they join"),
    (2, "Always display pronouns"),
    (3, "Do not display pronouns"),
]

USER_LANGUAGE = [
    ("en-US", "English"),
    ("es-ES", "Spanish"),
    ("de-DE", "Deutsch"),
    ("zh-CN", "Simplified Chinese"),
    ("zh-TW", "Traditional Chinese"),
    ("fr-FR", "French"),
    ("pt-PT", "Portuguese"),
    ("jp-JP", "Japanese"),
    ("ru-RU", "Russian"),
    ("ko-KO", "Korean"),
    ("it-IT", "Italian"),
    ("vi-VN", "Vietnamese"),
    ("pl-PL", "Polish"),
    ("tr-TR", "Turkish"),
    ("id-ID", "Indonesian"),
    ("nl-NL", "Nederlands"),
]

e164_rgx = re.compile(r"(\+[1-9]\d{1,14})")


def validate_phone_numbers(v):
    """
    Validate phone_numbers for ZoomPhoneUser and ZoomCommonArea.
    Value is one or more comma-separated E.164 numbers.
    Validator removes any extra characters inserted by excel
    """
    validated_numbers = []
    if not v:
        return v

    for item in re.split(r"\s*[,|;]\s*", v):
        if m := e164_rgx.search(item):
            validated_numbers.append(m.group(1))
        else:
            raise ValueError(f"Phone Number '{item}' is not valid in +E.164 format")

    return ",".join(validated_numbers)


@reg.data_type("zoom", "users")
class ZoomUser(dm.DataTypeBase):
    """
    ### License Types
    Zoom meeting users can be assigned one of the following license types, and one type ***only***.

    The default license (`None`) is automatically assigned to all Zoom meeting users. A value in the `License Type`
    column is only necessary to assign a different license type, other than the default.

     - `Basic`
     - `Licensed`
     - `On-Premise`
     - `No Meetings License`
     - `None`

    ### Languages
    Zoom meeting users can be assigned one of the following languages, and one language ***only***.

    The default language (`English`) is automatically assigned to all Zoom meeting users. A value in the `Language`
    column is only necessary to assign a different language, other than the default.

     - `English`
     - `Spanish`
     - `Deutsch`
     - `Simplified Chinese`
     - `Traditional Chinese`
     - `French`
     - `Portuguese`
     - `Japanese`
     - `Russian`
     - `Korean`
     - `Italian`
     - `Vietnamese`
     - `Polish`
     - `Turkish`
     - `Indonesian`
     - `Nederlands `

    ### Pronouns Options
    Zoom meeting users can be assigned one of the following pronouns options.

     - `Ask user every time they join`
     - `Always display pronouns`
     - `Do not display pronouns`
    """

    email: EmailStr = Field(
        wb_key="Email Address",
        doc_required="Yes",
        doc_value="Valid email address",
        test_value="testuser@xyz.com",
    )
    license_type: str = Field(
        wb_key="License Type",
        doc_required="Yes",
        doc_value="One of [Zoom License Types](users.md#license-types)",
    )
    first_name: str = Field(
        default="",
        wb_key="First Name",
        doc_required="No",
    )
    last_name: str = Field(
        default="",
        wb_key="Last Name",
        doc_required="No",
    )
    dept: str = Field(default="", wb_key="Department", doc_required="No")
    role: str = Field(
        default="",
        wb_key="Role",
        doc_required="No",
        doc_notes="If provided, role must exist within Zoom org.",
    )
    timezone: str = Field(
        default="",
        wb_key="Timezone",
        doc_required="No",
        doc_value="Valid timezone name. Ex: America/Eastern",
    )
    company: str = Field(default="", wb_key="Company", doc_required="No")
    job_title: str = Field(default="", wb_key="Job Title", doc_required="No")
    language: str = Field(
        default="",
        wb_key="Language",
        doc_required="No",
        doc_value="One of [Zoom Languages](users.md#languages)",
    )
    location: str = Field(default="", wb_key="Location", doc_required="No")
    manager: str = Field(default="", wb_key="Manager", doc_required="No")
    status: str = Field(default="")
    pronouns: str = Field(default="", wb_key="Pronouns", doc_required="No")
    pronouns_option: str = Field(
        default="",
        wb_key="Pronouns Option",
        doc_required="No",
        doc_value="One of [Zoom Pronouns Options](users.md#pronouns-options)",
    )

    class Config:
        title = "Users"
        schema_extra = {
            "data_type": "users",
            "id_field": "email",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }


@reg.data_type("zoom", "phone_users")
class ZoomPhoneUser(dm.DataTypeBase):
    email: EmailStr = Field(
        wb_key="Email Address",
        doc_required="Yes",
        doc_notes="Must match an existing Zoom meetings user",
        test_value="testuser@xyz.com",
    )
    extension_number: str = Field(
        wb_key="Extension",
        doc_required="Yes",
        doc_notes="Must be unique within the organization",
        test_value="77777",
    )
    phone_numbers: str = Field(
        default="",
        wb_key="Phone Numbers",
        doc_required="No",
        doc_value="Comma-separated E.164 numbers",
        doc_notes="Phone numbers must exist in the Zoom org an be unassigned",
    )
    site_name: str = Field(
        default="",
        wb_key="Site",
        doc_required="Conditional",
        doc_notes="Site is required if sites are enabled for the Zoom org",
    )
    template_name: str = Field(
        default="",
        wb_key="Template",
        doc_required="No",
        doc_value="Existing Zoom template name",
        doc_notes="Template must be in the same site as the user",
    )
    calling_plans: str = Field(
        default="",
        wb_key="Calling Plans",
        doc_required="Conditional",
        doc_value="Comma-separated [Calling Plan](calling_plans.md) names",
        doc_notes="Must have a value for `CREATE`. Leave blank for `UPDATE` to remove calling plans",
        test_value="US/CA Metered",
    )
    outbound_caller_id: str = Field(
        default="",
        wb_key="Caller ID",
        doc_required="No",
        doc_value="Outbound caller ID number in E.164 format",
        doc_notes="Must be an existing, assigned phone number in the Zoom org",
    )
    address_line1: str = Field(
        default="",
        wb_key="Address Line 1",
        doc_required="Conditional",
        doc_value="Valid street address",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
    )
    address_line2: str = Field(
        default="",
        wb_key="Address Line 2",
        doc_required="No",
        doc_value="Additional address info (ex: 8th floor)",
    )
    city: str = Field(
        default="",
        wb_key="City",
        doc_required="Conditional",
        doc_value="Valid city name",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
    )
    state_code: str = Field(
        default="",
        wb_key="State",
        doc_required="Conditional",
        doc_value="Two letter state code",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
    )
    zip: str = Field(
        default="",
        wb_key="ZIP",
        doc_required="Conditional",
        doc_value="Valid ZIP code",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
    )
    country: str = Field(
        default="",
        wb_key="Country",
        doc_required="Conditional",
        doc_value="Two letter country code (ISO-3166 format",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
    )
    voicemail_enable: dm.OptYN = Field(
        default="",
        wb_key="Voicemail Enable",
        doc_required="No",
        doc_notes="Enable or disable voicemail for the user",
    )
    policy: dm.ArbitraryDict = Field(default={}, wb_key="Policy")

    @validator("calling_plans")
    def validate_calling_plans(cls, v, values, field):
        return dm.validate_value_for_create(v, values, field)

    @validator("phone_numbers", "outbound_caller_id")
    def validate_phone_numbers(cls, v):
        return validate_phone_numbers(v)

    @property
    def calling_plans_list(self) -> list:
        """Return comma/semicolon-separated calling_plans string as list."""
        if self.calling_plans:
            return re.split(r"\s*[,|;]\s*", self.calling_plans)
        return []

    @property
    def phone_numbers_list(self) -> list:
        """Return comma/semicolon-separated phone_numbers string as list."""
        if self.phone_numbers:
            return re.split(r"\s*[,|;]\s*", self.phone_numbers)
        return []

    @property
    def emergency_address(self) -> dict:
        """Return emergency address-related fields in a dictionary"""
        return {
            "address_line1": self.address_line1,
            "address_line2": self.address_line2,
            "city": self.city,
            "country": self.country,
            "state_code": self.state_code,
            "zip": self.zip,
        }

    class Config:
        title = "Phone Users"
        schema_extra = {
            "data_type": "phone_users",
            "id_field": "email",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }


@reg.data_type("zoom", "sites")
class ZoomSite(dm.DataTypeBase):
    """
    NOTE:
    Deletion requires another Zoom site to inherit any objects associated with the deleted site.
    This must be provided as the **Transfer Site**.

    """

    name: str = Field(
        wb_key="Name",
        doc_required="Yes",
        doc_value="Up to 255 characters",
        test_value="Test Site",
    )
    new_name: str = Field(
        default="",
        wb_key="New Name",
        doc_required="No",
        doc_value="Up to 255 characters",
        doc_notes="Only applicable for `UPDATE`",
    )
    auto_receptionist: str = Field(
        default="",
        wb_key="Auto Receptionist",
        doc_required="Conditional",
        doc_value="Existing Zoom [auto-receptionist](https://support.zoom.us/hc/en-us/articles/360021121312-Managing"
                  "-Auto-Receptionists-and-Integrated-Voice-Response-IVR-) name",
        doc_notes="Required for `CREATE`, optional for `UPDATE`",
        test_value="Main Receptionist",
    )
    site_code: str = Field(
        default="",
        wb_key="Site Code",
        doc_required="Conditional",
        doc_value="Integer between 1 and 3",
        doc_notes="Required if site codes are enabled. Length of site code + Extension Length must be 6 or less.",
    )
    short_extension_length: str = Field(
        default="",
        wb_key="Extension Length",
        doc_required="Conditional",
        doc_value="Integer between 2 and 5",
        doc_notes="Required if site codes are enabled. Length of site code + Extension Length must be 6 or less.",
    )
    address_line1: str = Field(
        default="",
        wb_key="Address Line 1",
        doc_required="Conditional",
        doc_value="Valid street address",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
    )
    address_line2: str = Field(
        default="",
        wb_key="Address Line 2",
        doc_required="No",
        doc_value="Additional address info (ex: 8th floor)",
    )
    city: str = Field(
        default="",
        wb_key="City",
        doc_required="Conditional",
        doc_value="Valid city name",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
    )
    state_code: str = Field(
        default="",
        wb_key="State",
        doc_required="Conditional",
        doc_value="Two letter state code",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
    )
    zip: str = Field(
        default="",
        wb_key="ZIP",
        doc_required="Conditional",
        doc_value="Valid ZIP code",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
    )
    country: str = Field(
        default="",
        wb_key="Country",
        doc_required="Conditional",
        doc_value="Two letter country code (ISO-3166 format)",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
    )
    transfer_site_name: str = Field(
        default="",
        wb_key="Transfer Site",
        doc_required="Conditional",
        doc_value="Existing Zoom site name",
        doc_notes="Required for `DELETE`",
    )
    policy: dm.ArbitraryDict = Field(default={}, wb_key="Policy")

    @validator("auto_receptionist")
    def validate_auto_receptionist(cls, v, values, field):
        return dm.validate_value_for_create(v, values, field)

    @validator("transfer_site_name")
    def validate_transfer_site_name(cls, v, values, field):
        return dm.validate_value_for_delete(v, values, field)

    @property
    def emergency_address(self) -> dict:
        """Return emergency address-related fields in a dictionary"""
        return {
            "address_line1": self.address_line1,
            "address_line2": self.address_line2,
            "city": self.city,
            "country": self.country,
            "state_code": self.state_code,
            "zip": self.zip,
        }

    class Config:
        title = "Sites"
        schema_extra = {
            "data_type": "sites",
            "id_field": "name",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }


@reg.data_type("zoom", "emergency_locations")
class ZoomEmergencyLocation(dm.DataTypeBase):
    name: str = Field(
        wb_key="Name",
        doc_required="Yes",
        doc_value="Emergency location display name",
        test_value="Test Location",
    )
    new_name: str = Field(
        default="",
        wb_key="New Name",
        doc_required="No",
        doc_notes="Only applicable for `UPDATE` operation",
    )
    site_name: str = Field(
        default="",
        wb_key="Site",
        doc_required="Conditional",
        doc_value="Existing [Zoom Site](sites.md) name",
        doc_notes="Required for `CREATE` if sites are enabled in the Zoom org. Cannot be updated.",
    )
    parent_location_name: str = Field(
        default="",
        wb_key="Parent Location",
        doc_required="No",
        doc_value="Existing Zoom location name",
        doc_notes="Creates a sub-location beneath the parent. Only applicable for `CREATE`",
    )
    address_line1: str = Field(
        wb_key="Address Line 1",
        doc_required="Yes",
        doc_value="Valid street address",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
        test_value="123 Fake St",
    )
    address_line2: str = Field(
        default="",
        wb_key="Address Line 2",
        doc_required="No",
        doc_value="Additional address info (ex: 8th floor)",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
    )
    city: str = Field(
        wb_key="City",
        doc_required="Yes",
        doc_value="Valid city name",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
        test_value="Madison",
    )
    country: str = Field(
        wb_key="Country",
        doc_required="Yes",
        doc_value="Two letter country code (ISO-3166 format)",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
        test_value="WI",
    )
    state_code: str = Field(
        wb_key="State",
        doc_required="Yes",
        doc_value="Two letter state code",
        doc_note="Required for [Emergency Addresses](emergency_addresses.md)",
        test_value="US",
    )
    zip: str = Field(
        wb_key="ZIP",
        doc_required="Yes",
        doc_value="Valid ZIP code",
        doc_note="Required for [Emergency Addresses](emergency_addresses.md)",
        test_value="53711",
    )
    public_ip: str = Field(
        default="",
        wb_key="Public IP",
        doc_required="Conditional",
        doc_value="Valid IPv4 address with optional CIDR mask",
        doc_notes="Required for `CREATE` unless Parent Location is provided, optional for `UPDATE`",
        test_value="4.4.4.0/29",
    )
    private_ip: str = Field(
        default="",
        wb_key="Private IP",
        doc_required="No",
        doc_value="One or more comma-separated IPv4 addresses",
    )
    bssid: str = Field(
        default="",
        wb_key="BSSID",
        doc_required="No",
        doc_value="One or more comma-separated BSSIDs",
    )
    elin: str = Field(
        default="", wb_key="ELIN", doc_required="No", doc_value="E.164-formatted number"
    )
    minimum_match_criteria: dm.ReqYN = Field(
        wb_key="Strict Match",
        doc_notes="`Y` requires match on both public and private IP address, or BSSID, or network switch",
        test_value="N",
    )

    @property
    def emergency_address(self) -> dict:
        """Return emergency address-related fields in a dictionary"""
        return {
            "address_line1": self.address_line1,
            "address_line2": self.address_line2,
            "city": self.city,
            "country": self.country,
            "state_code": self.state_code,
            "zip": self.zip,
        }

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


@reg.data_type("zoom", "templates")
class ZoomTemplate(dm.DataTypeBase):
    """
    > NOTE: Due to Zoom API limitations:
    >
    > * Template deletion is not supported.
    > * Template type must be 'user'. Common area templates are not supported.

    """

    action: dm.OneOfStr(("CREATE", "UPDATE", "IGNORE"), required=True) = Field(
        wb_key="Action", doc_notes="`DELETE` not supported due to API limitation"
    )

    name: str = Field(
        wb_key="Name",
        doc_required="Yes",
        doc_value="Up to 50 characters",
        test_value="Test User Template",
    )
    type: str = Field(
        wb_key="Type",
        doc_required="Yes",
        doc_value="`user`",
        doc_notes="Common area and site types currently not supported",
        test_value="user",
    )
    site_name: str = Field(
        wb_key="Site",
        doc_required="Conditional",
        doc_value="Existing Zoom Site name",
        doc_notes="Required for `CREATE` if Sites are enabled for the org, optional for `UPDATE`",
        test_value="Test Site",
    )
    new_name: str = Field(
        default="",
        wb_key="New Name",
        doc_required="No",
        doc_notes="Only applicable for `UPDATE`",
    )
    description: str = Field(default="", wb_key="Description", doc_required="No")
    voicemail_enable: dm.OptYN = Field(
        default="",
        wb_key="Voicemail Enable",
        doc_required="No",
        doc_notes="Enable or disable voicemail",
    )
    call_forwarding_enable: dm.OptYN = Field(
        default="",
        wb_key="Call Forwarding Enable",
        doc_required="No",
        doc_notes="Enable or disable the ability to forward calls",
    )
    call_forwarding_type: str = Field(
        default="",
        wb_key="Call Forwarding Type",
        doc_required="No",
        doc_value="One of `1`, `2`, `3`, `4`",
    )
    policy: dm.ArbitraryDict = Field(default={}, wb_key="Policy")
    profile: dm.ArbitraryDict = Field(default={}, wb_key="Profile")
    user_settings: dm.ArbitraryDict = Field(default={}, wb_key="User_Settings")

    class Config:
        title = "Templates"
        schema_extra = {
            "data_type": "templates",
            "id_field": "name",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True
            },
        }


@reg.data_type("zoom", "devices")
class ZoomDevice(dm.DataTypeBase):
    """
    Zeus currently does not support:
    * Multiple assignees per device
    * Line key configuration
    * Shared line groups

    ### Device Types
    For device import to success, the **Device Type** and **Model** must match supported values.
    Examples of valid values are shown below:

    | Device Type | Example Models              |
    |-------------|-----------------------------|
    | Algo        | algo-sip-based-device       |
    | AudioCodes  | mp112, rx50                 |
    | Cisco       | cp7841, cp8851, ata-191     |
    | CyberData   | cyberdata-sip-based-device |
    | Grandstream | grp2602, grp2614, ht812     |
    | Poly        | ccx400, edge-b20, vvx250    |
    | Yealink     | cp960, w56p, w90dm          |
    | Other       | N/A                         |

    **Model** values should match those found in the model selection dropdown in the Zoom admin portal.

    """

    display_name: str = Field(
        wb_key="Name",
        doc_required="Yes",
        doc_value="Up to 255 characters",
        doc_notes="Phone display name. Does not need to be unique",
        test_value="Test Device",
    )
    mac_address: str = Field(
        wb_key="MAC Address",
        doc_required="Yes",
        doc_value="Twelve-character, Alpha-numeric",
        doc_notes="Do not include spaces or punctuation. Must be unique and valid for the device type",
        test_value="0027908022f1",
    )
    new_mac_address: str = Field(
        default="",
        wb_key="New MAC Address",
        doc_required="No",
        doc_value="Twelve-character, Alpha-numeric",
        doc_notes="Only applicable to `UPDATE` operations",
    )
    type: str = Field(
        wb_key="Type",
        doc_required="Yes",
        doc_value="Valid device type",
        doc_notes="See [Device Types](devices.md#device-types)",
        test_value="Cisco",
    )
    model: str = Field(
        default="",
        wb_key="Model",
        doc_required="Conditional",
        doc_value="Valid model for the device type",
        doc_notes="Value required unless Type is 'Other'. See [Device Types](devices.md#device-types)",
        test_value="cp7841",
    )
    template_name: str = Field(
        default="",
        wb_key="Template",
        doc_required="No",
        doc_value="Optional, Provisioning Template name",
    )
    assignee: str = Field(
        default="",
        wb_key="Assignee",
        doc_required="Conditional",
        doc_value="[Phone User email](phone_users.md) or [Common Area extension](common_areas.md)",
        doc_notes="Required for `CREATE`. If blank for `UPDATE` device will be unassigned",
    )
    sip_domain: str = Field(
        default="",
        wb_key="SIP Domain",
        doc_required="No",
        doc_value="SIP domain for third-party SIP devices",
        doc_notes="Value available for Third-Party SIP device exports when type is 'Other'",
    )
    user_name: str = Field(
        default="",
        wb_key="SIP User Name",
        doc_required="No",
        doc_value="SIP user name for third-party SIP devices",
        doc_notes="Value available for Third-Party SIP device exports when type is 'Other'",
    )
    sip_password: str = Field(
        default="",
        wb_key="SIP Password",
        doc_required="No",
        doc_value="SIP password for third-party SIP devices",
        doc_notes="Value available for Third-Party SIP device exports when type is 'Other'",
    )
    outbound_proxy: str = Field(
        default="",
        wb_key="SIP Outbound Proxy",
        doc_required="No",
        doc_value="SIP outbound proxy for third-party SIP devices",
        doc_notes="Value available for Third-Party SIP device exports when type is 'Other'",
    )
    authorization_id: str = Field(
        default="",
        wb_key="SIP Authorization ID",
        doc_required="No",
        doc_value="SIP Authorization ID for third-party SIP devices",
        doc_notes="Value available for Third-Party SIP device exports",
    )

    @validator("assignee")
    def validate_assignee(cls, v, values, field):
        """
        assignee must be provided for CREATE.
        assignee must be an email address or extension number
        """
        dm.validate_value_for_create(v, values, field)

        val = str(v)
        if any([val == "", "@" in val, re.match(r"\d+", val)]):
            return val
        else:
            raise ValueError("Assignee must be an email address or common area extension")

    class Config:
        title = "Devices"
        schema_extra = {
            "data_type": "devices",
            "id_field": "mac_address",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }


@reg.data_type("zoom", "common_areas")
class ZoomCommonArea(dm.DataTypeBase):
    display_name: str = Field(
        wb_key="Name",
        doc_required="Yes",
        doc_value="Up to 255 characters",
        doc_notes="Does not need to be unique",
        test_value="Test Common Area",
    )
    extension_number: str = Field(
        wb_key="Extension",
        doc_required="Yes",
        doc_value="3-6 digits",
        doc_notes="Must be unique with the Zoom org",
    )
    new_extension_number: str = Field(
        default="",
        wb_key="New Extension",
        doc_required="No",
        doc_value="3-6 digits",
        doc_notes="Only application to `UPDATE` operations",
    )
    phone_numbers: str = Field(
        default="",
        wb_key="Phone Numbers",
        doc_required="No",
        doc_value="Comma-separated E.164 numbers",
        doc_notes="Phone numbers must exist in the Zoom org an be unassigned",
    )
    site_name: str = Field(
        default="",
        wb_key="Site",
        doc_required="Conditional",
        doc_value="Existing Zoom site",
        doc_notes="Required for `CREATE` if sites are enabled in the org. Optional for `UPDATE`",
    )
    calling_plans: str = Field(
        wb_key="Calling Plans",
        doc_required="No",
        doc_value="Comma-separated [Calling Plan](calling_plans.md) names",
        doc_notes="Calling plan not required for `CREATE` but cannot be removed with `UPDATE`",
    )
    outbound_caller_id: str = Field(
        default="",
        wb_key="Caller ID",
        doc_required="No",
        doc_value="Outbound caller ID number in E.164 format",
        doc_notes="Must be an existing, assigned phone number in the Zoom org",
    )
    timezone: str = Field(
        default="",
        wb_key="Timezone",
        doc_required="No",
        doc_value="Valid timezone name. Ex: America/Eastern",
    )
    address_line1: str = Field(
        default="",
        wb_key="Address Line 1",
        doc_required="Conditional",
        doc_value="Valid street address",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
    )
    address_line2: str = Field(
        default="",
        wb_key="Address Line 2",
        doc_required="No",
        doc_value="Additional address info (ex: 8th floor)",
    )
    city: str = Field(
        default="",
        wb_key="City",
        doc_required="Conditional",
        doc_value="Valid city name",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
    )
    state_code: str = Field(
        default="",
        wb_key="State",
        doc_required="Conditional",
        doc_value="Two letter state code",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
    )
    country: str = Field(
        default="",
        wb_key="Country",
        doc_required="Conditional",
        doc_value="Two letter country code (ISO-3166 format)",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
    )
    zip: str = Field(
        default="",
        wb_key="ZIP",
        doc_required="Conditional",
        doc_value="Valid ZIP code",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
    )
    cost_center: str = Field(
        default="",
        wb_key="Cost Center",
        doc_required="No",
        doc_value="Cost code for billing purposes",
    )
    department: str = Field(
        default="",
        wb_key="Department",
        doc_required="No",
        doc_value="Department name for billing purposes",
    )
    block_country_code: str = Field(
        default="",
        wb_key="Block Country Code",
        doc_required="No",
        doc_value="Two letter country code (ISO-3166 format)",
    )

    @validator("phone_numbers", "outbound_caller_id")
    def validate_phone_numbers(cls, v):
        return validate_phone_numbers(v)

    @property
    def calling_plans_list(self) -> list:
        """Return comma/semicolon-separated calling_plans string as list."""
        if self.calling_plans:
            return re.split(r"\s*[,|;]\s*", self.calling_plans)
        return []

    @property
    def phone_numbers_list(self) -> list:
        """Return comma/semicolon-separated phone_numbers string as list."""
        if self.phone_numbers:
            return re.split(r"\s*[,|;]\s*", self.phone_numbers)
        return []

    @property
    def emergency_address(self) -> dict:
        """Return emergency address-related fields in a dictionary"""
        return {
            "address_line1": self.address_line1,
            "address_line2": self.address_line2,
            "city": self.city,
            "country": self.country,
            "state_code": self.state_code,
            "zip": self.zip,
        }

    class Config:
        title = "Common Areas"
        schema_extra = {
            "data_type": "common_areas",
            "id_field": "extension_number",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }


@reg.data_type("zoom", "phone_numbers")
class ZoomPhoneNumber(dm.DataTypeBase):
    number: str = Field(
        wb_key="Number",
        doc_required="Yes",
        doc_value="E.164 phone number",
        test_value="+16085551234",
    )
    type: str = Field(
        wb_key="Type",
        doc_required="Yes",
        doc_value="One of `toll`, `tollfree`",
        test_value="toll",
    )
    site_name: str = Field(
        default="",
        wb_key="Site",
        doc_required="Conditional",
        doc_value="Existing Zoom Site name",
        doc_notes="Required if Sites feature is enabled for the org",
    )
    source: str = Field(
        wb_key="Source",
        doc_required="Yes",
        doc_value="One of `internal`, `external`",
        test_value="internal",
    )
    status: str = Field(
        wb_key="Status",
        doc_required="Yes",
        doc_value="One of `available`, `pending`",
        test_value="available",
    )
    assignee: str = Field(
        default="",
        wb_key="Assignee",
        doc_value="Common area extension or phone user email for assigned numbers, empty string if unassigned",
    )
    address_line1: str = Field(
        default="",
        wb_key="Address Line 1",
        doc_required="Conditional",
        doc_value="Valid street address",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
    )
    address_line2: str = Field(
        default="",
        wb_key="Address Line 2",
        doc_required="No",
        doc_value="Additional address info (ex: 8th floor)",
    )
    city: str = Field(
        default="",
        wb_key="City",
        doc_required="Conditional",
        doc_value="Valid city name",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
    )
    state_code: str = Field(
        default="",
        wb_key="State",
        doc_required="Conditional",
        doc_value="Two letter state code",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
    )
    zip: str = Field(
        default="",
        wb_key="ZIP",
        doc_required="Conditional",
        doc_value="Valid ZIP code",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
    )
    country: str = Field(
        default="",
        wb_key="Country",
        doc_required="Conditional",
        doc_value="Two letter country code (ISO-3166 format",
        doc_notes="Required for [Emergency Addresses](emergency_addresses.md)",
    )

    @property
    def emergency_address(self) -> dict:
        """Return emergency address-related fields in a dictionary"""
        return {
            "address_line1": self.address_line1,
            "address_line2": self.address_line2,
            "city": self.city,
            "country": self.country,
            "state_code": self.state_code,
            "zip": self.zip,
        }

    class Config:
        title = "Phone Numbers"
        schema_extra = {
            "data_type": "phone_numbers",
            "id_field": "number",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": False,
                "upload": False,
                "help_doc": False,
            },
        }


@reg.data_type("zoom", "external_contacts")
class ZoomExternalContact(dm.DataTypeBase):

    name: str = Field(
        wb_key="Name",
        doc_required="Yes",
        doc_value="Up to 255 characters",
    )
    new_name: str = Field(
        default="",
        wb_key="New Name",
        doc_required="No",
        doc_notes="Only applicable for `UPDATE`",
    )
    email: str = Field(
        default="",
        wb_key="Email Address",
        doc_required="No",
        doc_value="Valid email address",
        test_value="testuser@xyz.com",
    )
    extension_number: str = Field(
        default="",
        wb_key="Extension",
        doc_required="No",
        doc_value="3-6 digits",
    )
    phone_numbers: str = Field(
        default="",
        wb_key="Phone Numbers",
        doc_required="No",
        doc_value="Comma-separated E.164 numbers",
    )
    description: str = Field(
        default="",
        wb_key="Description",
        doc_required="No",
        doc_value="Up to 255 characters",
    )
    routing_path: str = Field(
        default="",
        wb_key="Routing Path",
        doc_required="No",
        doc_value="If provided, must be `PSTN` or an existing SIP Group name",
    )
    auto_call_recorded: dm.OptYN = Field(wb_key="Auto Call Recorded")

    @validator("phone_numbers")
    def validate_phone_numbers(cls, v):
        return validate_phone_numbers(v)

    @property
    def phone_numbers_list(self) -> list:
        """Return comma/semicolon-separated phone_numbers string as list."""
        if self.phone_numbers:
            return re.split(r"\s*[,|;]\s*", self.phone_numbers)
        return []

    class Config:
        title = "External Contacts"
        schema_extra = {
            "data_type": "external_contacts",
            "id_field": "name",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }


class IvrActionEnum(StrEnum):
    @classmethod
    def from_name_or_value(cls, value):
        """
        Return an enum entry based on either the name
        or the value.

        This provides user flexibility when creating
        a worksheet. The user may enter the numeric
        enum value or the name
        """
        value = re.sub(r"\s+", "", str(value))
        if value in [str(item) for item in cls]:
            return cls(value)

        for item in cls:
            if re.match(item.name, value, re.I):  # noqa
                return item

        raise ZeusConversionError(f"Invalid Ivr Action: '{value}'")

    def wb_value(self):
        """Return the enum name as separate words for the worksheet export"""
        return re.sub("([a-z0-9])([A-Z])", r"\1 \2", self.name)


class IvrNoEntryAction(IvrActionEnum):
    Disconnect = "-1"
    User = "2"
    CommonArea = "4"
    CiscoPolyPhone = "5"  # Not supported for Bulk Ops
    AutoReceptionist = "6"
    CallQueue = "7"
    SharedLineGroup = "8"
    ContactCenter = "15"  # Not supported for Bulk Ops


class IvrMenuAction(IvrActionEnum):
    Disabled = "-1"
    User = "2"
    ZoomRoom = "3"
    CommonArea = "4"
    CiscoPolyPhone = "5"  # Not supported for Bulk Ops
    AutoReceptionist = "6"
    CallQueue = "7"
    SharedLineGroup = "8"
    ExternalContact = "9"
    PhoneNumber = "10"
    ContactCenter = "15"  # Not supported for Bulk Ops
    MeetingService = "16"  # Not supported for Bulk Ops
    MeetingServiceNumber = "17"  # Not supported for Bulk Ops
    RepeatGreeting = "21"  # star, pound only
    RootMenu = "22"  # star, pound only
    PreviousMenu = "23"  # star, pound only
    CurrentExtensionVoiceMail = "100"
    UserVoicemail = "200"
    AutoReceptionistVoicemail = "300"
    CallQueueVoicemail = "400"
    SharedLineVoicemail = "500"


POUND_STAR_ONLY_ACTIONS = (IvrMenuAction.RepeatGreeting, IvrMenuAction.RootMenu, IvrMenuAction.PreviousMenu)
UNSUPPORTED_ACTIONS = (
    IvrMenuAction.ContactCenter,
    IvrMenuAction.CiscoPolyPhone,
    IvrMenuAction.MeetingServiceNumber,
    IvrMenuAction.MeetingServiceNumber,
    IvrNoEntryAction.CiscoPolyPhone,
    IvrNoEntryAction.ContactCenter,
)


class CallHandlingAction(IvrActionEnum):
    """
    The action to take when a call is not answered:
    1 — Forward to a voicemail.
    2 — Forward to the user.
    4 — Forward to the common area.
    6 — Forward to the auto receptionist.
    7 — Forward to a call queue.
    8 — Forward to a shared line group.
    9 — Forward to an external contact.
    10 - Forward to a phone number.
    11 — Disconnect.
    12 — Play a message, then disconnect.
    13 - Forward to message.
    14 - Forward to interactive voice response (IVR).
    """

    Voicemail = "1"
    User = "2"
    CommonArea = "4"
    AutoReceptionist = "6"
    CallQueue = "7"
    SharedLineGroup = "8"
    ExternalContact = "9"
    PhoneNumber = "10"
    Disconnect = "11"
    PlayMessage = "12"
    Message = "13"
    IVR = "14"


@reg.data_type("zoom", "auto_receptionists")
class ZoomAutoReceptionist(dm.DataTypeBase):
    """
    ### Limitations
    Zeus's support for Auto Receptionists currently has the following limitations:
    - Only business hours are supported. Closed and holiday schedules are not.
    - Only the "Route to Interactive Voice Response (IVR)" route option is supported.
    - Adding/updating IVR greetings is not supported.
    - The following IVR actions are not currently supported by Zeus:
        - Contact Center
        - Cisco/Poly Phone
        - Meeting Service
        - Meeting Service Number

    ### IVR Actions
    When importing an Auto Receptionist, the IVR menu entry options (0-9,#,*) and timeout options
    can be customized. This is done by entering a supported action name (or ID) in the 'Action' workbook
    column and the target extension in the corresponding 'Target' column (for forward and send-to-voicemail actions).

    The supported actions are detailed below. Note that either the action ID number or name can be used within the
    workbook.

    #### Timeout Actions
    The following actions are supported for the Timeout Action colum (labeled 'Caller Takes No Action or Says Nothing'
    in the Zoom UI).

    | ID | Name              | Target             |
    |----|-------------------|--------------------|
    | -1 | Disconnect        | None               |
    | 2  | User              | Extension or Email |
    | 4  | Common Area       | Extension          |
    | 6  | Auto Receptionist | Extension          |
    | 7  | Call Queue        | Extension          |
    | 8  | Shared Line Group | Extension          |

    ### Menu Entry Actions
    The following actions are supported for the menu options. Either the action number or
    bolded text can be used in the workbook.

    ##### For key `0`-`9`
    | ID  | Name                        | Target             |
    |-----|-----------------------------|--------------------|
    | -1  | Disabled                    | None               |
    | 2   | User                        | Extension or Email |
    | 4   | Common Area                 | Extension          |
    | 6   | Auto Receptionist           | Extension          |
    | 7   | Call Queue                  | Extension          |
    | 8   | Shared Line Group           | Extension          |
    | 9   | External Contact            | Extension          |
    | 10  | Phone Number                | E.164 number       |
    | 100 | Current Extension Voicemail | None               |
    | 200 | User Voicemail              | Extension or Email |
    | 300 | Auto Receptionist Voicemail | Extension          |
    | 400 | Call Queue Voicemail        | Extension          |
    | 500 | Shared Line Group Voicemail | Extension          |

    ##### For keys `*`,`#`
    | ID | Name            | Target |
    |----|-----------------|--------|
    | -1 | Disabled        | None   |
    | 21 | Repeat Greeting | None   |
    | 22 | Root Menu       | None   |
    | 23 | Previous Menu   | None   |
    """
    name: str = Field(wb_key="Name", doc_required="Yes")
    site_name: str = Field(
        default="",
        wb_key="Site",
        doc_required="Conditional",
        doc_notes="Site is required if sites are enabled for the Zoom org",
    )
    extension_number: str = Field(
        default="",
        wb_key="Extension",
        doc_required="Conditional",
        doc_notes="Required for `UPDATE` or `DELETE`. If provided, Must be unique within the organization",
        test_value="77999",
    )
    timezone: str = Field(
        default="",
        wb_key="Timezone",
        doc_required="No",
        doc_value="Valid timezone name. Ex: America/Eastern",
    )
    phone_numbers: str = Field(
        default="",
        wb_key="Phone Numbers",
        doc_required="No",
        doc_value="Comma-separated E.164 numbers",
        doc_notes="Phone numbers must exist in the Zoom org an be unassigned",
    )
    audio_prompt_id: str = Field(
        default="",
        wb_key="IVR Audio Prompt ID",
        doc_required="No",
        doc_value="Existing IVR audio prompt ID",
        doc_notes="Optional for `CREATE` and `UPDATE`",
    )
    audio_prompt_repeat: str = Field(
        default="",
        wb_key="Prompt Repeat",
        doc_required="No",
        doc_value="One of 1, 2, 3",
        doc_notes="Number of times to repeat the prompt",
    )
    audio_prompt_language: str = Field(
        default="",
        wb_key="Prompt Language",
        doc_required="No",
        doc_value="One of [Zoom Languages](users.md#languages)",
    )
    no_entry_action: str = Field(
        default="",
        wb_key="No Entry Action",
        doc_required="No",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Action to take if caller enters no input",
    )
    no_entry_target: str = Field(
        default="",
        wb_key="No Entry Target",
        doc_required="Conditional",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Required if the specified action requires a target",
    )
    key_0_action: str = Field(
        default="",
        wb_key="Key 0 Action",
        doc_required="No",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Action to take if caller enters this key",
    )
    key_0_target: str = Field(
        default="",
        wb_key="Key 0 Target",
        doc_required="Conditional",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Required if the specified action requires a target",
    )
    key_1_action: str = Field(
        default="",
        wb_key="Key 1 Action",
        doc_required="No",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Action to take if caller enters this key",
    )
    key_1_target: str = Field(
        default="",
        wb_key="Key 1 Target",
        doc_required="Conditional",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Required if the specified action requires a target",
    )
    key_2_action: str = Field(
        default="",
        wb_key="Key 2 Action",
        doc_required="No",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Action to take if caller enters this key",
    )
    key_2_target: str = Field(
        default="",
        wb_key="Key 2 Target",
        doc_required="Conditional",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Required if the specified action requires a target",
    )
    key_3_action: str = Field(
        default="",
        wb_key="Key 3 Action",
        doc_required="No",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Action to take if caller enters this key",
    )
    key_3_target: str = Field(
        default="",
        wb_key="Key 3 Target",
        doc_required="Conditional",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Required if the specified action requires a target",
    )
    key_4_action: str = Field(
        default="",
        wb_key="Key 4 Action",
        doc_required="No",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Action to take if caller enters this key",
    )
    key_4_target: str = Field(
        default="",
        wb_key="Key 4 Target",
        doc_required="Conditional",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Required if the specified action requires a target",
    )
    key_5_action: str = Field(
        default="",
        wb_key="Key 5 Action",
        doc_required="No",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Action to take if caller enters this key",
    )
    key_5_target: str = Field(
        default="",
        wb_key="Key 5 Target",
        doc_required="Conditional",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Required if the specified action requires a target",
    )
    key_6_action: str = Field(
        default="",
        wb_key="Key 6 Action",
        doc_required="No",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Action to take if caller enters this key",
    )
    key_6_target: str = Field(
        default="",
        wb_key="Key 6 Target",
        doc_required="Conditional",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Required if the specified action requires a target",
    )
    key_7_action: str = Field(
        default="",
        wb_key="Key 7 Action",
        doc_required="No",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Action to take if caller enters this key",
    )
    key_7_target: str = Field(
        default="",
        wb_key="Key 7 Target",
        doc_required="Conditional",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Required if the specified action requires a target",
    )
    key_8_action: str = Field(
        default="",
        wb_key="Key 8 Action",
        doc_required="No",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Action to take if caller enters this key",
    )
    key_8_target: str = Field(
        default="",
        wb_key="Key 8 Target",
        doc_required="Conditional",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Required if the specified action requires a target",
    )
    key_9_action: str = Field(
        default="",
        wb_key="Key 9 Action",
        doc_required="No",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Action to take if caller enters this key",
    )
    key_9_target: str = Field(
        default="",
        wb_key="Key 9 Target",
        doc_required="Conditional",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Required if the specified action requires a target",
    )
    key_s_action: str = Field(
        default="",
        wb_key="Key * Action",
        doc_required="No",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Action to take if caller enters this key",
    )
    key_s_target: str = Field(
        default="",
        wb_key="Key * Target",
        doc_required="Conditional",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Required if the specified action requires a target",
    )
    key_p_action: str = Field(
        default="",
        wb_key="Key # Action",
        doc_required="No",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Action to take if caller enters this key",
    )
    key_p_target: str = Field(
        default="",
        wb_key="Key # Target",
        doc_required="Conditional",
        doc_value="See [IVR Action](auto_receptionists.md#ivr_actions)",
        doc_notes="Required if the specified action requires a target",
    )
    new_extension_number: str = Field(
        default="",
        wb_key="New Extension",
        doc_required="No",
        doc_notes="Only applicable for `UPDATE`",
    )

    @validator("no_entry_action")
    def validate_no_entry_action(cls, v, values):
        if v and values.get("action", "") in ("CREATE", "UPDATE"):
            try:
                action = IvrNoEntryAction.from_name_or_value(v)
            except Exception:
                raise ValueError(f"Invalid No Entry Action: '{v}'")

            if action in UNSUPPORTED_ACTIONS:
                raise ValueError(f"No Entry Action: '{v}' is not currently supported by Zeus")

        return v

    @validator(
        "key_0_action",
        "key_1_action",
        "key_2_action",
        "key_3_action",
        "key_4_action",
        "key_5_action",
        "key_6_action",
        "key_7_action",
        "key_8_action",
        "key_9_action",
    )
    def validate_num_menu_actions(cls, v, values, field):
        """
        Make sure menu actions for keys 0 - 9 are valid for
        CREATE/UPDATE as the error returned by the API does not
        provide enough detail for the user.

        Actions supported only for */# cannot be assigned to keys
        0 - 9. Also, actions not supported by Zeus cannot be assigned.
        """
        if v and values.get("action", "") in ("CREATE", "UPDATE"):
            name = field.name.replace("_", " ").title()
            try:
                action = IvrMenuAction.from_name_or_value(v)
            except Exception:
                raise ValueError(f"Invalid {name}: '{v}'")

            if action in POUND_STAR_ONLY_ACTIONS:
                raise ValueError(f"{name}: '{v}' is only supported for '*' and '#' keys")

            if action in UNSUPPORTED_ACTIONS:
                raise ValueError(f"{name}: '{v}' is not currently supported by Zeus")

        return v

    @validator("key_s_action", "key_p_action")
    def validate_star_pound_actions(cls, v, values, field):
        """
        Make sure menu actions for keys */# are valid for
        CREATE/UPDATE as the error returned by the API does not
        provide enough detail for the user.
        """
        if v and values.get("action", "") in ("CREATE", "UPDATE"):
            name = field.name.replace("_", " ").title()
            key = "*" if field.name == "key_s_action" else "#"
            try:
                action = IvrMenuAction.from_name_or_value(v)
            except Exception:
                name = field.name.replace("_", " ").title()
                raise ValueError(f"Invalid {name}: '{v}'")

            if action not in POUND_STAR_ONLY_ACTIONS:
                raise ValueError(f"Action '{v}' is not supported for {key} key")

        return v

    @property
    def menu_actions_list(self) -> List[dict]:
        menu_actions = []
        key_mappings = [(str(r), str(r)) for r in range(0, 10)]
        key_mappings += [("s", "*"), ("p", "#")]

        for model_key, payload_key in key_mappings:
            menu_action = {
                "key": payload_key,
                "action": getattr(self, f"key_{model_key}_action"),
                "target": getattr(self, f"key_{model_key}_target"),
            }

            menu_actions.append(menu_action)

        return menu_actions

    @validator("phone_numbers")
    def validate_phone_numbers(cls, v):
        return validate_phone_numbers(v)

    @property
    def phone_numbers_list(self) -> list:
        """Return comma/semicolon-separated phone_numbers string as list."""
        if self.phone_numbers:
            return re.split(r"\s*[,|;]\s*", self.phone_numbers)
        return []

    class Config:
        title = "Auto Receptionists"
        schema_extra = {
            "data_type": "auto_receptionists",
            "id_field": "extension_number",
            "supports": {
                "browse": True,
                "detail": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }

@reg.data_type("zoom", "alerts")
class ZoomAlert(dm.DataTypeBase):
    name: str = Field(
        wb_key="Name",
        doc_required="Yes",
        doc_value="Up to 255 characters",
        test_value="Test Alert",
    )
    module: str = Field(
        wb_key="Module",
        doc_required="Yes",
        doc_value="",
        test_value="phone",
    )
    rule_condition_type: str = Field(
        wb_key="Rule",
        doc_required="Yes",
        doc_value="One of `call`, `meeting`, `webinar`",
        test_value="call",
    )
    rule_condition_value: str = Field(
        wb_key="Condition",
        doc_required="Yes",
        doc_value="One of `greater_than`, `less_than`, `equal_to`",
        test_value="greater_than",
    )
    target_ids: str = Field(
        wb_key="Target IDs",
        doc_required="No",
        doc_value="Comma-separated extension numbers or email addresses",
    )
    time_frame_type: str = Field(
        wb_key="Time Frame Type",
        doc_required="Yes",
        doc_value="One of `time`, `date`",
        test_value="time",
    )
    time_frame_from: str = Field(
        wb_key="Time Frame From",
        doc_required="Yes",
        doc_value="Valid time frame string formatted as HH:mm:ss",
        test_value="08:00:02",
    )
    time_frame_to: str = Field(
        wb_key="Time Frame To",
        doc_required="Yes",
        doc_value="Valid time frame string formatted as HH:mm:ss",
        test_value="17:00:01",
    )
    frequency: StrEnum = Field(
        wb_key="Frequency",
        doc_required="Yes",
        doc_value="One of `once`, `daily`, `weekly`, `monthly`",
        test_value="daily",
    )
    email_recipients: str = Field(
        wb_key="Email Recipients",
        doc_required="No",
        doc_value="Comma-separated email addresses",
    )
    chat_channels: str = Field(
        wb_key="Chat Channels",
        doc_required="No",
        doc_value="Comma-separated channel names",
    )
    status: str = Field(
        wb_key="Status",
        doc_required="No",
        doc_value="One of `active`, `inactive`",
    )

    @property
    def target_ids_list(self) -> list:
        """Return comma/semicolon-separated target_ids string as list."""
        if self.target_ids:
            return re.split(r"\s*[,|;]\s*", self.target_ids)
        return []

    class Config:
        title = "Alerts"
        schema_extra = {
            "data_type": "alerts",
            "id_field": "name",
            "supports": {
                "browse": True,
                "detail": False,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }

@reg.data_type("zoom", "routing_rules")
class ZoomRoutingRule(dm.DataTypeBase):

    name: str = Field(
        wb_key="Name",
        doc_required="Yes",
        doc_value="Up to 255 characters",
        test_value="Test Routing Rule",
    )
    number_pattern: str = Field(
        wb_key="Number Pattern",
        doc_required="Yes",
        doc_value="The Perl-compatible number_pattern expression",
        test_value="+16085551234",
    )
    sip_group_id: str = Field(
        wb_key="SIP Group ID",
        doc_required="No",
        doc_value="Existing SIP Group ID",
    )
    site: str = Field(
        wb_key="Site",
        doc_required="No",
        doc_value="Existing Zoom Site",
    )
    translation: str = Field(
        wb_key="Translation",
        doc_required="No",
        doc_value="E.164 formatted replacement pattern",
    )
    rule_type: str = Field(
        wb_key="Rule Type",
        doc_required="Yes",
        doc_value="One of: Other Sites, PSTN, SIP Group",
    )

    @property
    def rule_type_fix(self) -> str:
        """Return the rule type as a string, should match to other_sites, pstn, sip_group"""
        if self.rule_type == "Other Sites":
            return "other_sites"
        elif self.rule_type == "PSTN":
            return "pstn"
        elif self.rule_type == "SIP Group":
            return "sip_group"
        else:
            raise ValueError(f"Invalid rule type: {self.rule_type}")

    class Config:
        title = "Routing Rules"
        schema_extra = {
            "data_type": "routing_rules",
            "id_field": "name",
            "supports": {
                "browse": True,
                "detail": False,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }
