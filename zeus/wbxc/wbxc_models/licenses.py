from pydantic import Field, validator, BaseModel, root_validator
from zeus import registry as reg
from zeus.shared import data_type_models as dm
from .shared import validate_extension, validate_phone_numbers, ASSIGNABLE_WEBEX_LICENSE_TYPES, WEBEX_CALLING_LICENSE_TYPES


class WbxcUserLicense(BaseModel):
    idx: int = Field(description="Column Index #")
    license: dm.OneOfStr(
        values=ASSIGNABLE_WEBEX_LICENSE_TYPES,
        required=True,
    ) = Field(description="Calling License")
    subscription: str = Field(description="Subscription")
    operation: dm.OneOfStr(values=("add", "remove")) = Field(description="Operation")


@reg.data_type("wbxc", "licenses")
class WbxcLicense(dm.DataTypeBase):
    action: dm.OneOfStr(("UPDATE", "IGNORE"), required=True) = Field(
        wb_key="Action",
        doc_notes="Only supports 'UPDATE' as operation is specified on individual license",
    )

    user_email: str = Field(
        wb_key="Email Address",
        doc_required="Yes",
        doc_value="Valid email address",
        test_value="testuser@xyz.com",
    )

    licenses: list[WbxcUserLicense] = Field(
        default=[],
        doc_required="Yes",
        doc_key="Calling License 1",
        doc_value=f"On of {','.join(f'`{lic}`' for lic in ASSIGNABLE_WEBEX_LICENSE_TYPES)}",
    )

    calling_phone_number: str = Field(
        default="",
        wb_key="Calling Phone Number",
        doc_required="No",
        doc_value="Phone number to assign user. Only required for 'add' on a Webex Calling license.",
    )

    calling_extension: str = Field(
        default="",
        wb_key="Calling Extension",
        doc_required="No",
        doc_notes="Extension to assign user. Only required for 'add' on a Webex Calling license.",
    )

    calling_location: str = Field(
        default="",
        wb_key="Calling Location",
        doc_required="No",
        doc_value="The name of an existing Webex location. Only required for 'add' on a Webex Calling license and "
        "Calling Phone Number not provided.",
    )

    @root_validator
    def validate_extension_or_phone_number_for_calling_license(cls, values):
        """
        Ensure calling_extension or calling_phone_number are set if a Webex Calling
        license is included in a CREATE or UPDATE action.
        """
        def includes_calling_license():
            for entry in values.get("licenses") or []:
                if entry.license in WEBEX_CALLING_LICENSE_TYPES:
                    return True
            return False

        action = values.get("action", "")
        license_names = [entry.license for entry in values.get("licenses") or []]
        extension = values.get("calling_extension")
        phone_number = values.get("calling_phone_number")

        if all([
            action == "UPDATE",
            includes_calling_license(),
            not extension,
            not phone_number
        ]):
            raise ValueError(
                "Add or removal of a Webex Calling license requires "
                "Calling Extension or Calling Phone Number to be provided"
            )

        return values

    @validator("calling_phone_number")
    def validate_license_phone_number(cls, v):
        return validate_phone_numbers(v)

    @validator("calling_extension")
    def validate_license_extension(cls, v):
        return validate_extension(v)

    @validator("calling_location", always=True)
    def validate_location(cls, v, values, field):
        """Location is required if only Calling Extension is provided"""
        if (values["calling_extension"] and not v) and not values["calling_phone_number"]:
            raise ValueError(
                "Calling Location required when only Calling Extension is provided"
            )
        return v

    @classmethod
    def model_doc(cls):
        """
        Class method to modify and extend the base documentation model. This method overrides
        the base implementation to add additional fields specific to the operation. It inserts
        the new operation information in the documentation, ensuring its inclusion
        at a specific position if applicable.

        Args:
            cls:
                The class parameter automatically passed to a class method.

        Returns:
            dict:
                A modified documentation dictionary object that includes the additional
                operation field.

        Raises:
            Exception:
                Raised if there is any error during an attempt to locate an existing entry
                or manipulate the documentation list.
        """
        doc = super().model_doc()
        subscription_doc = dm.DataTypeFieldDoc(
            doc_name="Subscription 1",
            doc_required="No",
            doc_value="Subscription to use license from. If not provided, first license returned from API "
                      "will be used.",
            field_type="String",
        )
        operation_doc = dm.DataTypeFieldDoc(
            doc_name="Operation 1",
            doc_required="No",
            doc_value="Operation to perform on license",
            field_type="OneOfStr",
        )
        # Insert subscription and operation entry right after the license entry
        try:
            idx = [d.doc_name for d in doc.doc_fields].index("Calling License 1")
            doc.doc_fields.insert(idx + 1, subscription_doc)
            doc.doc_fields.insert(idx + 2, operation_doc)
        except Exception:
            doc.doc_fields.append(subscription_doc)
            doc.doc_fields.append(operation_doc)
        return doc

    def to_wb(self) -> dict:
        """
        Converts the current object and its associated licenses into a dictionary representation
        suitable for workbook processing.

        This method utilizes the superclass conversion method to initialize a dictionary with
        base attributes. It then iterates over the associated licenses, adding each license's
        details as a dictionary entry. Licenses are sorted by their 'idx' attribute before being
        added to ensure consistent ordering in the resulting dictionary.

        Returns:
            dict: A dictionary containing the object's base attributes along with the license
            details, each indexed and formatted appropriately.
        """
        row = super().to_wb()
        for cur_license in sorted(self.licenses, key=lambda x: x.idx):
            row[f"Calling License {cur_license.idx}"] = cur_license.license
            row[f"Operation {cur_license.idx}"] = cur_license.operation
        return row

    class Config:
        title = "Licenses"
        schema_extra = {
            "data_type": "licenses",
            "id_field": "user_email",
            "supports": {
                "browse": False,
                "export": False,
                "bulk": True,
                "upload": True,
                "help_doc": True,
            },
        }
