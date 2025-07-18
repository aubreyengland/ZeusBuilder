from zeus import registry as reg
from zeus.shared import data_type_models as dm
from pydantic import Field, validator, root_validator
from zeus.wbxc.wbxc_models.shared import validate_e164_phone_number

MAX_NUMBERS_PER_REQUEST = 500


@reg.data_type("wbxc", "numbers")
class WbxcNumber(dm.DataTypeBase):
    """
    ### Number Ranges
    Phone numbers can be imported individually or as a range by setting the `Phone Numbers End` value. Ranges
    are limited to {MAX_NUMBERS_PER_REQUEST} entries.
    """
    action: dm.OneOfStr(("CREATE", "UPDATE", "IGNORE"), required=True) = Field(
        wb_key="Action",
        doc_notes="Numbers cannot be deleted currently.",
    )
    phone_number_start: str = Field(
        wb_key="Phone Numbers Start",
        doc_required="Yes",
        doc_value="E.164 number",
        doc_notes=(
            "Only supported for adding DID and Toll-free numbers to non-integrated PSTN"
            "connection types such as Local Gateway (LGW) and Non-integrated CPP."
            "It should never be used for locations with integrated PSTN connection types like "
            "Cisco Calling Plans or Integrated CCP because backend data issues may occur."
            "If only Phone Numbers Start is provided on a row, it will be assumed only a single number is being added."
        ),
    )
    phone_number_end: str = Field(
        default="",
        wb_key="Phone Numbers End",
        doc_required="No",
        doc_value="E.164 number",
        doc_notes="End number is inclusive.",
    )
    extension: str = Field(
        default="",
        wb_key="Extension",
        doc_required="No",
        doc_notes="Read only field for reference only and if Phone Number is not included",
    )
    location_name: str = Field(
        wb_key="Location",
        doc_required="Yes",
        doc_value="The name of an existing Webex location.",
    )
    state: dm.OneOfStr(values=("ACTIVE", "INACTIVE"), required=False) = Field(
        default="",
        wb_key="State",
        doc_required="Yes",
        doc_notes="Numbers can only be updated from `INACTIVE` to `ACTIVE`."
    )
    owner_type: str = Field(
        default="",
        wb_key="Owner Type",
        doc_required="No",
        doc_notes="Read only field. Provides type of object number is associated with",
    )
    owner_name: str = Field(
        default="",
        wb_key="Owner Name",
        doc_required="No",
        doc_notes="Read only field. Provides name of object number is associated with",
    )

    @root_validator
    def validate_phone_number_range(cls, values):
        start_number = values.get("phone_number_start")
        end_number = values.get("phone_number_end")

        if end_number:
            if len(start_number) != len(end_number):
                raise ValueError(
                    f"Invalid number range: {start_number}-{end_number}. "
                    f"Start and end numbers must be the same length."
                )

            if start_number > end_number:
                raise ValueError(
                    f"Invalid number range: {start_number}-{end_number}. "
                    f"End number must be larger than start number."
                )

        return values

    @validator("phone_number_start")
    def validate_phone_number_start(cls, v):
        return validate_e164_phone_number(v)

    @validator("phone_number_end")
    def validate_phone_number_end(cls, v):
        if v:
            return validate_e164_phone_number(v)
        return v

    @validator("state", always=True)
    def validate_state(cls, v, values, field):
        """
        Ensure state is provided for CREATE or UPDATE.
        If the action is UPDATE, ensure the state is ACTIVE as
        it is not a supported operation to update an ACTIVE number
        to INACTIVE
        """
        dm.validate_value_for_create(v, values, field)
        dm.validate_value_for_update(v, values, field)

        action = values.get("action", "")
        if action == "UPDATE" and v == "INACTIVE":
            raise ValueError("Phone numbers cannot be inactivated")

        return v

    class Config:
        title = "Numbers"
        schema_extra = {
            "data_type": "numbers",
            "id_field": "phone_number_start",
            "supports": {
                "browse": True,
                "export": True,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }
