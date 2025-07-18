import re
from copy import deepcopy
from pydantic import Field, BaseModel, root_validator
from zeus import registry as reg
from zeus.shared import data_type_models as dm


class WbxcDeviceEnhancedMultiCastDestination(BaseModel):
    idx: int = Field(description="enhanced multicast destination index")
    destination: str = Field(
        wb_key="Enhanced Multicast {IDX} Destination",
        doc_required="Yes",
        doc_value="IP address:port. Ex: 239.0.0.1:8080",
    )
    xmlapp: dm.OptYN = Field(
        wb_key="Enhanced Multicast {IDX} XMLApp",
        doc_required="No",
    )
    timer: str = Field(
        wb_key="Enhanced Multicast {IDX} Timer",
        default="",
        doc_required="No",
        doc_value="Time in seconds to display the message on screen",
    )

    def to_wb(self):
        wb_row = {}
        idx = self.idx
        for wb_key, field in self.indexed_wb_keys(idx).items():
            key = wb_key.format(IDX=idx)
            value = getattr(self, field.name)
            wb_row[key] = dm.to_wb_str(value)

        return wb_row

    @classmethod
    def indexed_wb_keys(cls, idx: int) -> dict:
        """
        Return a dictionary with wb_keys using the provided idx integer
        as keys and the associated field as values
        """
        field_by_indexed_wb_key = {}
        for field in cls.__fields__.values():
            wb_key = field.field_info.extra.get("wb_key")

            if wb_key:
                field_by_indexed_wb_key[wb_key.format(IDX=idx)] = field

        return field_by_indexed_wb_key

    @classmethod
    def model_doc_fields(cls):
        """Generate doc fields for the help page and worksheet template using Line index: 1"""
        doc_idx = "1"
        doc_fields = []

        for field_name, schema in cls.schema()["properties"].items():
            field = cls.__fields__[field_name]
            doc_name = ""

            if schema.get("wb_key"):
                doc_name = schema["wb_key"].format(IDX=doc_idx)

            if not doc_name or schema.get("doc_ignore"):
                continue

            field_schema = deepcopy(schema)
            field_schema["doc_key"] = doc_name

            doc_field = dm.DataTypeFieldDoc.from_data_type_field(field, field_schema)

            doc_fields.append(doc_field)

        return doc_fields


@reg.data_type("wbxc", "device_settings")
class WbxcDeviceSettings(dm.DataTypeBase):
    """
    ### Device Settings Support
    Device settings can be customized for MPP phone models (68XX, 78XX, 88XX) and ATA 191/192.

    ATAs only support a subset of device settings.

    ### Enhanced Multicast
    To add one or more Enhanced Multicast Destinations, set Enhanced Multicast Enabled to `Y` and
    define one or more destinations using the `Enhanced Multicast X...` columns.

    Duplicate these columns and increment the index number to add multiple destinations.

    To remove any existing Enhanced Multicast Destinations, set Enhanced Multicast Enabled to `N`.

    Be aware of the following when defining destinations:
    * Up to ten enhanced multicast destinations can be added to an MPP device.
    * Each destination must include a unique multicast address:port combination. For example, '239.0.0.1:8080'.
    * Port must be even numbers.
    * If XMLApp is set `Y` for multicast destination, the Enhanced Multicast URL must be provided.
    * Any existing destinations are replaced by those in the worksheet.
    """
    action: dm.OneOfStr(("UPDATE", "IGNORE"), required=True) = Field(
        wb_key="Action",
    )
    mac: str = Field(
        wb_key="MAC Address",
        doc_required="Yes",
        doc_value="MAC address of existing device",
    )
    custom_enabled: dm.OptYN = Field(
        wb_key="Use Custom Settings",
        default="",
        doc_required="No",
    )
    pnac_enabled: dm.OptYN = Field(
        wb_key="8021x",
        default="",
        doc_required="No",
        doc_notes="MPP only"
    )
    active_call_focus: dm.OptYN = Field(
        wb_key="Active Call Focus",
        default="",
        doc_required="No",
        doc_notes="MPP only"
    )
    calls_per_line: str = Field(
        wb_key="Calls Per Line",
        default="",
        doc_required="No",
        doc_value="Between 1 and 10",
        doc_notes="MPP only"
    )
    cdp_enabled: dm.OptYN = Field(
        wb_key="CDP",
        default="",
        doc_required="No",
    )
    lldp_enabled: dm.OptYN = Field(
        wb_key="LLDP",
        default="",
        doc_required="No",
    )
    dnd_enabled: dm.OptYN = Field(
        wb_key="DND",
        default="",
        doc_required="No",
        doc_notes="MPP only"
    )
    ice_enabled: dm.OptYN = Field(
        wb_key="ICE",
        default="",
        doc_required="No",
        doc_notes="MPP only"
    )
    monitor_list_enabled: dm.OptYN = Field(
        wb_key="Monitor List",
        default="",
        doc_required="No",
        doc_notes="MPP only"
    )
    web_access: dm.OptYN = Field(
        wb_key="Web Access",
        default="",
        doc_required="No",
    )
    enhanced_mcast_enabled: dm.OptYN = Field(
        wb_key="Enhanced Multicast Enabled",
        default="",
        doc_required="Conditional",
        doc_notes="MPP only. Must be 'Y' to customize Enhanced Multicast URL or destinations. Set to 'N' to remove any existing Enhanced Multicast Destinations"
    )
    enhanced_mcast_url: str = Field(
        wb_key="Enhanced Multicast URL",
        default="",
        doc_required="Conditional",
        doc_notes="MPP only. Must be provided if a XMLApp destinations are provided"
    )
    enhanced_mcast_destinations: list[WbxcDeviceEnhancedMultiCastDestination] = []

    @classmethod
    def model_doc(cls):
        """Add Enhanced Multicast Destinations 1 doc field object to model docs."""
        doc = super().model_doc()
        line_doc_fields = WbxcDeviceEnhancedMultiCastDestination.model_doc_fields()
        doc.doc_fields.extend(line_doc_fields)
        return doc

    def to_wb(self) -> dict:
        """Custom method to add `Skill #` keys to the wb row dictionary"""
        row = super().to_wb()
        for item in sorted(self.enhanced_mcast_destinations, key=lambda x: x.idx):
            row.update(item.to_wb())
        return row

    @root_validator()
    def validate_enhanced_multicast(cls, values):
        """
        Check the enhanced multicast destinations for requirements
        not enforced by the API but that cause the configuration to be invalid
        1. If xmlapp is 'Y' for any entries, a xml_url must be set
        3. Destinations must be unique
        """
        if values.get("action") != "UPDATE":
            return values

        destinations = values.get("enhanced_mcast_destinations")
        if not destinations:
            return values

        if any([dest.xmlapp == "Y" for dest in destinations]):
            if not values.get("enhanced_mcast_url"):
                raise ValueError("Enhanced Multicast URL is required for XMLApp destinations")

        hosts = []
        for item in destinations:

            check_enhanced_multicast_host(item.destination)

            if item.destination in hosts:
                raise ValueError(f"Duplicate Enhanced Multicast Destination: {item.destination}")

            hosts.append(item.destination)

        return values

    class Config:
        title = "Device Settings"
        schema_extra = {
            "data_type": "device_settings",
            "id_field": "mac_address",
            "supports": {
                "browse": False,
                "export": True,
                "bulk": True,
                "upload": True,
                "detail": False,
                "help_doc": True,
            },
        }


def check_enhanced_multicast_host(host: str):
    """
    Check that the multicast host value is in the format: x.x.x.x:y
    and that the port is an even number.
    """
    m = re.match(r"(?:22[4-9]|23[0-9])\.\d+\.\d+\.\d+:(\d+)", str(host))
    if not m:
        raise ValueError(f"Enhanced Multicast destination: {host} is invalid. Must be formatted as Mcast Address:Port")

    port = int(m.group(1))
    if divmod(port, 2)[1] != 0:
        raise ValueError(f"Enhanced Multicast destination: {host} is invalid. Port must be an even number.")
