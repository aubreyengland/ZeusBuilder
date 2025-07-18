from pydantic import BaseModel, validator
from zeus.exceptions import ZeusConversionError
from zeus.wbxc.wbxc_models.shared import EXT_MIN, EXT_MAX


class WbxcMonitor(BaseModel):
    column_id: str = ""
    number: str = ""
    location_name: str = ""

    @validator("number", always=True)
    def validate_number(cls, v, values):
        column_id = values.get("column_id", "")

        if not v:
            return v

        v = v.lstrip("\\")
        if v.startswith("+"):
            return v

        if EXT_MIN <= len(v) <= EXT_MAX:
            return v

        raise ZeusConversionError(
            f"'Monitored Number {column_id}' Invalid format. Must be +E.164 or an extension ({EXT_MIN}-{EXT_MAX} digits)."
        )

    @validator("location_name", always=True)
    def validate_location_name(cls, v, values):
        number = values.get("number", "")
        column_id = values.get("column_id", "")

        if EXT_MIN <= len(number) <= EXT_MAX and not v:
            raise ZeusConversionError(
                f"'Monitored Location {column_id}' cannot be empty when using extensions."
            )

        return v