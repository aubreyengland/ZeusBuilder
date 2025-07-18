from pydantic import Field, validator
from zeus import registry as reg
from zeus.shared import data_type_models as dm
from zeus.wbxc.wbxc_models.shared import PREFERRED_LANGUAGES


@reg.data_type("wbxc", "locations")
class WbxcLocation(dm.DataTypeBase):
    action: dm.OneOfStr(("CREATE", "UPDATE", "IGNORE"), required=True) = Field(
        wb_key="Action",
        doc_notes="Locations cannot be deleted.",
    )
    name: str = Field(
        wb_key="Name",
        doc_required="Yes",
        doc_value="The name of the location.",
        test_value="CDW",
    )
    new_name: str = Field(
        default="",
        wb_key="New Name",
        doc_required="No",
        doc_notes="Only applicable for `UPDATE` operation",
    )
    address1: str = Field(
        default="",
        wb_key="Address 1",
        doc_required="Conditional",
        doc_value="First line of the address",
        doc_notes="Required for `CREATE`.",
    )
    address2: str = Field(
        default="",
        wb_key="Address 2",
        doc_required="Optional",
        doc_value="Second (optional) line of the address. 'REMOVE' to clear.",
        doc_notes="Optional for `CREATE` or `UPDATE`.",
    )
    city: str = Field(
        default="",
        wb_key="City",
        doc_required="Conditional",
        doc_value="City name",
        doc_notes="Required for `CREATE`."
    )
    state: str = Field(
        default="",
        wb_key="State",
        doc_required="Conditional",
        doc_value="State name",
        doc_notes="Required for `CREATE`."
    )
    postalCode: str = Field(
        default="",
        wb_key="Zip Code",
        doc_required="Conditional",
        doc_value="Postal code (AKA - Zip code)",
        doc_notes="Required for `CREATE`."
    )
    country: str = Field(
        default="",
        wb_key="Country",
        doc_required="Conditional",
        doc_value="ISO-3166 2-Letter Country Code.",
        doc_notes="Required for `CREATE`."
    )
    timeZone: str = Field(
        default="",
        wb_key="Time Zone",
        doc_required="Conditional",
        doc_value="Time zone associated with this location",
        doc_notes="Required for `CREATE`.",
    )
    preferredLanguage: str = Field(
        default="",
        wb_key="Email Language",
        doc_required="Conditional",
        doc_value="Default email language",
        doc_notes="Required for `CREATE` action."
    )
    latitude: str = Field(
        default="",
        wb_key="Latitude",
        doc_required="No",
        doc_value="Decimal degrees 41.878981",

    )
    longitude: str = Field(
        default="",
        wb_key="Longitude",
        doc_required="No",
        doc_value="decimal degrees -87.643572",
    )
    notes: str = Field(
        default="",
        wb_key="Notes",
        doc_required="No",
        doc_value="Location notes.",
    )
    calling_enabled: dm.OptYN = Field(
        default="",
        description="Non-workbook field used by Browse Service to indicate calling status in browse table."
    )

    @validator("address1", "city", "state", "postalCode", "country", always=True)
    def validate_address_for_create(cls, v, values, field):
        return dm.validate_value_for_create(v, values, field)

    @validator("timeZone", always=True)
    def validate_time_zone_for_create(cls, v, values, field):
        return dm.validate_value_for_create(v, values, field)

    @validator("preferredLanguage", always=True)
    def validate_preferredLanguage(cls, v, values, field):
        """
        Verify preferredLanguage is present for a CREATE action and
        is one of the supported values, if present for CREATE or UPDATE
        """
        dm.validate_value_for_create(v, values, field)
        if v and values.get("action", "") in ("CREATE", "UPDATE"):
            lang = str(v).lower()
            for code in PREFERRED_LANGUAGES:
                if lang == code.lower():
                    return code
            raise ValueError(f"Email Language: '{v}' is invalid")

        return v

    class Config:
        title = "Locations"
        schema_extra = {
            "data_type": "locations",
            "id_field": "name",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }