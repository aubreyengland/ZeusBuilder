import re
import logging
from copy import deepcopy
from pydantic.fields import ModelField
from typing import TYPE_CHECKING, Type
from pydantic import BaseModel, Field, ValidationError
from zeus.exceptions import ZeusConversionError, extract_first_validation_error

log = logging.getLogger(__name__)

UNSET_VALS = ("", None, {}, [])


class OneOfStrField(str):
    """
    Custom Pydantic string field type that limits values to those in the `values` attribute.
    An empty string is also allowed if the `required` attribute is False.

    The validator is case-insensitive but will convert the value to the expected case upon a match.

    Using this field will automatically set the doc schema attributes but these can be
    overridden on model if necessary.

    Example:
    >>> class DataTypeObj(DataTypeBase):
    ...     required: OneOfStr(('A', 'B'), required=True)
    ...     optional: OneOfStr(('A', 'B'), required=False) = Field(default="")
    ...
    >>> DataTypeObj(action='CREATE', required='a')
    DataTypeObj(action='CREATE', required='A', optional='')

    NOTES:
    The preference is to NOT do this type of validation in the data type models because it will cause
    export/browse requests to fail if unexpected/new values are returned. This should only be used
    if validation is necessary in the model because the API error on an invalid value does not indicate
    the cause of the error.

    Use the `OneOfStr` helper function to define these fields in models as this allows
    the values and required params to be passed.

    If setting `required=False` you must provide a default in the Field (as shown above).
    """

    values = ()
    required = True

    @classmethod
    def __modify_schema__(cls, field_schema):
        doc_required, test_value = ("Yes", cls.values[0]) if cls.required else ("No", "")
        field_schema.update(
            doc_required=doc_required,
            doc_value=",".join(f"`{v}`" for v in cls.values),
            test_value=test_value,
        )

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value):
        """
        Check if value is in the the supported cls.values iterable
        by doing a case-insensitive comparison. If a match is
        found, return the matching value from cls.values.
        If no match is found, raise a ValueError
        """
        if not cls.required and value in ("", None):
            return ""

        for_validation = {v.lower(): v for v in cls.values}
        if str(value.lower()) in for_validation:
            return for_validation[str(value).lower()]

        err_values = ",".join(f"'{v}'" for v in cls.values)
        if not cls.required:
            err_values += " or empty string"

        raise ValueError(f"Must be one of {err_values}")


def OneOfStr(values: tuple, required: bool = True):
    """Helper function to create OneOfStrField object with provided class attributes"""
    namespace = dict(values=values, required=required)
    return type("OneOfStr", (OneOfStrField,), namespace)


if TYPE_CHECKING:
    ArbitraryDict = dict
else:

    class ArbitraryDict(dict):
        """
        Dictionary Pydantic field type used to represent dictionaries
        of arbitrary depth within a provisioning workbook column.

        The provisioning workbook represents nested dictionaries with columns
        of period-separated paths for each value.

        Example:
            ```{'vm': {'enabled': True}}``` appears as column `Policy.vm.enabled`

        This field stores the value in the workbook format.

        The validator will:
         - Convert a nested dictionary to one-level dict with dotted-path keys (if necessary)
         - Convert values to the wb string format

        The __to_payload__ method:
         - Converts the workbook reprentation to a nested dictionary
         - Converts wb boolean values to True, False
         - Drops keys with unset values, if `drop_unset=True`

        The __to_wb__ method:
         - Checks if the field as a `wb_key` field attribute. If so:
         - Adds the field value to the row dictionary

        The __from_wb__ method:
         - Checks if the field has a `wb_key` field attribute. If so:
         - Collects all keys from the row dict that begin with the field name for the field value

        Example:
        >>> class DataTypeObj(DataTypeBase):
        ...     policy: ArbitraryDict = Field(wb_key="Policy", default={})
        ...
        >>> policy = {'vm': {'enabled': True}}
        >>> DataTypeObj(action="CREATE", policy=policy)
        DataTypeObj(action='CREATE', policy={'Policy.vm.enabled': 'Y'})
        """

        @classmethod
        def __modify_schema__(cls, field_schema):
            # Do not include in data type table by default as the worksheets
            # will not have a single column of this name
            field_schema.update(type="object", doc_ignore=True)

        @classmethod
        def __get_validators__(cls):
            yield cls.validate

        @classmethod
        def validate(cls, value, values, config, field) -> dict:
            """
            Convert the value to a single-level dictionary that
            can be represented in a table or spreadsheet.

            If value is not a dictionary, raise ValueError to trigger
            a validation failure.

            If the value keys are already in the workbook format,
            (as they will be if model is created using `from_wb`
            method), return the value unmodified.

            Otherwise, convert the value dict to the workbook
            format.
            """
            if not isinstance(value, dict):
                raise ValueError("Value must be type: dictionary")

            key_prefix = field.field_info.extra.get("wb_key") or field.name
            if all([re.match(fr"^{key_prefix}\..+", key, re.I) for key in value]):
                return value

            return arbitrary_dict_to_wb_converter(value, [key_prefix])

        @classmethod
        def __to_payload__(
                cls, field: ModelField, model_obj: dict, payload: dict, drop_unset: bool
        ) -> None:
            """
            Convert the value of this ArbitraryDict field for an API payload
            and add the converted value to the payload.

            If the conversion process returns an empty dict, the drop_unset param
            determines if it is added to the payload or not.

            Args:
                field (ModelField): Pydantic ModelField
                model_obj (dict): Dictionary from model.dict() method
                payload (dict): Dictionary holding converted items for the payload
                drop_unset (bool): Do not add empty dict to payload if True
            """
            converted_dict = arbitrary_dict_to_payload_converter(model_obj[field.name])
            converted_dict_and_values = arbitrary_dict_payload_value_converter(
                converted_dict, drop_unset
            )

            if converted_dict_and_values:
                payload.update(converted_dict_and_values)
            elif not drop_unset:
                payload[field.name] = {}

        @classmethod
        def __from_wb__(cls, field: ModelField, model_obj: dict, wb_row: dict) -> None:
            """
            Determine if the provided field should get its value from wb_row and
            if so, convert all associated items in the provided wb_row into a single
            nested dictionary for use as the value for this field in the created model.

            The field value should come from wb_row if the `wb_key` field property is set.

            Any keys in wb_row that being with the field name (followed by a period)
            are used to build the converted value.

            Raise ZeusConversionError if wb_key is set and the field is required
            but wb_row has no associated items

            Args:
                field (ModelField): Pydantic ArbitraryDict ModelField instance
                model_obj (dict): Data for the model constructor pulled from wb_row
                wb_row (dict): Dictionary for a provisioning workbook row
            """

            wb_key = field.field_info.extra.get("wb_key")
            if not wb_key:
                return

            arbitrary_dict_items = {
                key: wb_row[key] for key in wb_row if re.match(fr"^{wb_key}\..+", key, re.I)
            }

            if arbitrary_dict_items:
                model_obj[field.name] = arbitrary_dict_items

            elif field.required:
                raise ZeusConversionError(error=f"Required column '{wb_key}' not found")

        @classmethod
        def __to_wb__(cls, field: ModelField, model: "DataTypeBase", wb_row: dict) -> None:
            """
            Determine if the provided field should supply a value for a workbook row
            and if so, add the value for this field in the provided model to the
            wb_row dict.

            The presence of the wb_key field property indicates that the field
            should provide a value for the workbook row.

            If wb_key is found, the field value is added as-is since any conversion
            would have been done upon model creation through this field's validator.

            Args:
                field (ModelField): Pydantic ModelField
                model (DataTypeBase): Model instance being converted
                wb_row (dict): Dictionary holding converted items for the workbook
            """
            wb_key = field.field_info.extra.get("wb_key")
            if wb_key:
                value = getattr(model, field.name)
                wb_row.update(value)

if TYPE_CHECKING:
    OptYN = str
    ReqYN = str
else:

    class OptYN(OneOfStrField):
        """
        Custom Pydantic field type to represent boolean values in the workbook format.
        This is a `OneOfStrField` with values hard-coded and a modified validator to
        convert booleans (and other common bool values) to 'Y' or 'N'.
        An empty string is also supported.

        This field stores the value as 'Y', 'N' or ''.

        The `__to_payload__` method:
         - Converts the 'Y'/'N' value to True/False
         - Converts '' to None if `drop_unset=False`
         - Drops the field from the payload if value is '' and `drop_unset=True`

        NOTE: `default=""` must be specified in the Field definition when using the field type
        """

        values = ("Y", "N")
        required = False

        @classmethod
        def validate(cls, v):
            if str(v).lower() in ("y", "yes", "true", "t"):
                return "Y"
            if str(v).lower() in ("n", "no", "false", "f"):
                return "N"
            if str(v).lower() in ("", "none"):
                return ""

            raise ValueError("Must be one of 'Y','N' or empty string")

        @classmethod
        def __to_payload__(
                cls, field: ModelField, model_obj: dict, payload: dict, drop_unset: bool
        ):
            if drop_unset and model_obj[field.name] in UNSET_VALS:
                return
            payload[field.name] = yn_to_bool(model_obj[field.name])


    class ReqYN(OneOfStrField):
        """
        Custom Pydantic field type to represent boolean values in the workbook format.
        This is a `OneOfStrField` with values hard-coded and a modified validator to
        convert booleans (and other common bool values) to 'Y' or 'N'.

        This field stores the value as 'Y', 'N'

        The `__to_payload__` method:
         - Converts the 'Y'/'N' value to True/False
        """

        values = ("Y", "N")
        required = True

        @classmethod
        def validate(cls, v):
            if str(v).lower() in ("y", "yes", "true", "t"):
                return "Y"
            if str(v).lower() in ("n", "no", "false", "f"):
                return "N"

            raise ValueError("Must be one of 'Y','N'")

        @classmethod
        def __to_payload__(
                cls, field: ModelField, model_obj: dict, payload: dict, drop_unset
        ):
            if drop_unset and model_obj[field.name] in UNSET_VALS:
                return
            payload[field.name] = yn_to_bool(model_obj[field.name])


class DataTypeBase(BaseModel):
    action: OneOfStr(("CREATE", "UPDATE", "DELETE", "IGNORE"), required=True) = Field(
        wb_key="Action"
    )

    @classmethod
    def safe_build(cls, obj: dict = None, **kwargs):
        """
        Use the provided API response object to create a model
        instance, attempting to avoid validation errors due to
        unexpected or missing values.

        Keys in the provided obj dict that match field names are
        provided to the model constructor with the value converted
        to the workbook representation. This includes:
         - None values are converted to empty strings
         - Boolean values are converted to 'Y'/'N'
         - Other values are passed as-is.
         - action value of "IGNORE" added if not provided

        Required fields not found in the provided obj will be
        set to 'NOTFOUND' to avoid a validation error. Note that
        any a ValidationError may still occur if a model validator
        exists for that field.

        Returns:
            (DataTypeBase) DataTypeBase Instance populated from the row values
        """
        obj = deepcopy(obj or {})
        obj.update(kwargs)

        safe_obj = {}
        model_schema: dict = cls.schema()["properties"]

        for field_name, field in cls.__fields__.items():
            if field_name in obj:
                safe_obj[field_name] = to_wb_str(obj[field_name])
                continue

            if field_name == "action":
                safe_obj["action"] = "IGNORE"
                continue

            if field.required:
                log.warning(
                    f"No value provided for {cls.__name__}.{field_name}. Will use 'NOTFOUND'."
                )
                safe_obj[field_name] = "NOTFOUND"

        return cls.parse_obj(safe_obj)

    @classmethod
    def from_wb(cls, row: dict):
        """
        Create a model instance using the provided workbook row dictionary.

        Items in the row dictionary are mapped to model fields using the
        'wb_key' value in the model field metadata.

        for each field in the model:
         - Check if the field type has a `__from_wb__` class method
         - If so, call this method and allow it to add a value to the model dict
         - If not, call `default_from_wb_converter` and allow it to add a value to the model dict

        Args:
            row (dict): Dict from a row in a provisioning workbook

        Returns:
            (DataTypeBase) DataTypeBase Instance populated from the row values
        """
        obj = {}
        try:
            for field_name, field in cls.__fields__.items():
                converter = getattr(field.type_, "__from_wb__", default_from_wb_converter)
                converter(field, obj, row)

            return cls.parse_obj(obj)

        except ZeusConversionError:
            raise
        except ValidationError as exc:
            raise ZeusConversionError(error=extract_first_validation_error(exc))
        except Exception as exc:
            raise ZeusConversionError(error=str(exc))

    @classmethod
    def model_doc(cls) -> "DataTypeDoc":
        return DataTypeDoc.from_data_type_model(cls)

    def to_wb(self) -> dict:
        """
        Create a dictionary formatted for writing as a row to a provisioning
        worksheet from this model instance

        Model fields are mapped to worksheet columns using the 'wb_key' value in the model field metadata.

        for each field in the model:
         - Check if the field type has a `__to_wb__` class method
         - If so, call this method and allow it to add a value to the row dict
         - If not, call `default_to_wb_converter` and allow it to add a value to the row dict

        Returns:
            wb_row (dict): Dictionary formatted as a worksheet row
        """
        wb_row = {}

        try:
            for field in self.__fields__.values():
                converter = getattr(field.type_, "__to_wb__", default_to_wb_converter)
                converter(field, self, wb_row)

            return wb_row

        except Exception as exc:
            raise ZeusConversionError(error=f"{type(exc).__name__}: {exc}")

    def to_payload(self, *, drop_unset=False, include=None, exclude=None) -> dict:
        """
        Convert the model to a dictionary suitable for use in an API request.

        Starts by using the built-in `model.dict()` method to convert the model to dictionary and,
        potentially, drop keys based on the `include` and `exclude` params

        Then uses the custom `__to_payload__` method from custom field types or
        the `default_to_payload_converter` function to get the value.

        """
        if exclude:
            exclude = set(exclude)
        else:
            exclude = set()
        # always exclude action column
        exclude.add("action")

        payload = {}
        model_obj = self.dict(include=include, exclude=exclude)

        for field in self.__fields__.values():
            if field.name not in model_obj:
                continue

            converter = getattr(field.type_, "__to_payload__", default_to_payload_converter)
            converter(field, model_obj, payload, drop_unset)

        return payload


def arbitrary_dict_to_wb_converter(obj: dict, combo_key: list = None) -> dict:
    """
     Convert the provided dictionary to the provisioning workbook format

     The keys in hierarchies in the provided dict are joined into a single key/value pair
     to be presented in a tabular fashion.

     The values are converted to strings using the `to_wb_str` function.

     Nest dicts and nested lists of dicts are supported.
     Lists of lists are not supported. The string-rep of the inner lists will be used as the values.

    Examples:
    >>> # noinspection PyShadowingNames
    >>> obj = {'policy': {'voicemail': {'enable': True, 'video': False}, 'encrypt': True}}
    >>> arbitrary_dict_to_wb_converter(obj)
    {'policy.voicemail.enable': 'Y', 'policy.voicemail.video': 'N', 'policy.encrypt': 'Y'}

    >>> # noinspection PyShadowingNames
    >>> # List of dictionaries example
    >>> obj = {'policy': {'custom_hours': [ {'from': '09:00', 'to': '18:00'}, {'from': '09:00', 'to': '18:00'}, ]}}
    >>> arbitrary_dict_to_wb_converter(obj)
    {'policy.custom_hours.0.from': '09:00', 'policy.custom_hours.0.to': '18:00', 'policy.custom_hours.1.from': '09:00',
     'policy.custom_hours.1.to': '18:00'}


     Args:
         obj (dict): Dictionary input for ArbitraryDict field
         combo_key (list): List of keys in the hierarchy currently being converted (used for recursive calls)

     Returns:
         for_wb (dict): Single-level dictionary ready for workbook inclusion
    """
    for_wb = {}
    combo_key = combo_key or []

    for key, value in obj.items():
        combo_key.append(key)

        if isinstance(value, dict):
            # On child dict, call self with the current combo_key and
            # merge return value into for_wb
            res = arbitrary_dict_to_wb_converter(value, combo_key)
            for_wb.update(res)

        elif isinstance(value, list):
            # On list value, enumerate each item adding the index to the combo key
            for idx, item in enumerate(value):

                if isinstance(item, dict):
                    # If item is dict, add index to combo_key, call self and merge
                    # return value into for_wb
                    combo_key.append(str(idx))
                    for_wb.update(arbitrary_dict_to_wb_converter(item, combo_key))

                    # Remove index from combo_key before going to next item
                    combo_key.pop(-1)
                else:
                    # If item is not a dict, add item to for_wb with index in key
                    key = ".".join(combo_key) + f".{idx}"
                    for_wb[key] = to_wb_str(item)

        else:
            # Assume value is a simple type (str, int, bool). Convert value for wb,
            # join combo key and add to for_wb
            for_wb[".".join(combo_key)] = to_wb_str(value)

        # Remove most significant item from combo_key before starting loop again
        combo_key.pop(-1)

    return for_wb


def arbitrary_dict_to_payload_converter(obj: dict, converted: dict = None) -> dict:
    """
    Convert the provided arbitrary dict field value from the provisioning workbook format of
    key/string value pairs back to the original nested dictionaries.

    Examples:
    >>> # noinspection PyShadowingNames
    >>> obj = {"Policy.voicemail.enable": "Y", "Policy.voicemail.video": "N", "Policy.encrypt": "Y"}
    >>> arbitrary_dict_to_payload_converter(obj)
    {'policy': {'voicemail': {'enable': 'Y', 'video': 'N'}, 'encrypt': 'Y'}}

    >>> # noinspection PyShadowingNames
    >>> # List of dictionaries example
    >>> obj = {'policy.custom_hours.0.from': '09:00', 'policy.custom_hours.0.to': '18:00',
    'policy.custom_hours.1.from': '09:00', 'policy.custom_hours.1.to': '18:00'}
    >>> arbitrary_dict_to_payload_converter(obj)
    {'policy': {'custom_hours': [{'from': '09:00', 'to': '18:00'}, {'from': '09:00', 'to': '18:00'}]}}

     Args:
         obj (dict): ArbitraryDict field value
         converted (dict, None): Dictionary of converted items (used for recursive calls)

     Returns:
         converted (dict): Dictionary ready for payload
    """
    converted = {} if converted is None else converted

    for single_or_combo_key, val in obj.items():
        key, *nested_keys = str(single_or_combo_key).lower().split(".")

        if not nested_keys:
            # If key already exists the wb either has duplicate columns or inconsistent levels in a common path
            if key in converted:
                raise ValueError(f"'{key}' already set to '{converted[key]}'")

            # No nested_keys means the value for this key is a simple type.
            converted[key] = val
            continue

        if re.match(r"^\d+$", nested_keys[0]):
            # If first nested key is numeric, treat as index in a list
            converted.setdefault(key, [])

            index = int(nested_keys[0])

            if len(nested_keys) == 1:
                # If no additional keys after list index, make a list of strings
                # obj[key].insert(index, convert_wb_bool_for_model(val))
                converted[key].insert(index, val)

            else:
                # List items will be dicts. Get (or create) the dict at this index
                # and use in recursive call
                try:
                    obj_for_index = converted[key][index]
                except IndexError:
                    obj_for_index = {}
                    converted[key].append(obj_for_index)

                # recurse with index value removed from combo key
                combo_key = ".".join(nested_keys[1:])
                arbitrary_dict_to_payload_converter({combo_key: val}, obj_for_index)
            continue

        # Non-numeric nested keys remaining means child object is a dict
        converted.setdefault(key, {})

        # If key already exists with a simple value. There is a mistake in the wb
        # such as including both 'Policy.SMS' column and 'Policy.SMS.Subdict' columns
        if not isinstance(converted[key], dict):
            raise ValueError(f"'{single_or_combo_key}' path overlaps with '{key}'")

        combo_key = ".".join(nested_keys)
        nested = arbitrary_dict_to_payload_converter({combo_key: val}, converted[key])
        converted[key].update(nested)

    return converted


def arbitrary_dict_payload_value_converter(obj: dict, drop_unset: bool) -> dict:
    """
    Recursively convert boolean values in the provided obj dictionary
    from the workbook string format to True, False, None

    If `drop_unset` is True and a value is in `UNSET_VAL` do not add it to the return value

    Examples:
    >>> o = {'top' :{'L1': {'enable': 'Y'}, 'L2': {'enable': ''}}}
    >>> arbitrary_dict_payload_value_converter(o, False)
    {'top': {'L1': {'enable': True}, 'L2': {'enable': None}}}

    >>> o = {'top' :{'L1': {'enable': 'Y'}, 'L2': {'enable': ''}}}
    >>> arbitrary_dict_payload_value_converter(o, True)
    {'top': {'L1': {'enable': True}}}

    Args:
         obj (dict): dictionary with workbook string values
         drop_unset (bool): If True, do not add keys with values in `UNSET_VALS`

    Returns:
        converted (dict): source dictionary with values converted
    """
    converted = {}
    for key, val in obj.items():
        if isinstance(val, dict):
            val = arbitrary_dict_payload_value_converter(val, drop_unset)

        elif isinstance(val, list):
            # List items may be strings or dicts. If dicts, make recursive call
            val = [
                yn_to_bool(v)
                if not isinstance(v, dict)
                else arbitrary_dict_payload_value_converter(v, drop_unset)
                for v in val
            ]

        if val in UNSET_VALS and drop_unset:
            continue

        converted[key] = yn_to_bool(val)

    return converted


def default_from_wb_converter(field: ModelField, model_obj: dict, wb_row: dict) -> None:
    """
    Determine if the provided field should get its value from wb_row and
    if so, add the field name key to the model_obj dict using the corresponding
    value from wb_row

    If the `wb_key` field property is set and this key exists in wb_row, then
    then the value of wb_row[wb_key] is used.

    If `wb_key` is not, look for field.name in wb_row, and use that value if
    found. This case is used by Five9User to populate the permissions field
    from the wb_row['permissions'] key added by the Upload service. It is handled
    in the default converter in anticipation of that pattern being used by future
    data types.

    If the field is not required (it has a default value), then nothing is added
    to model_obj for this field.

    If the field is required, a ZeusConversionError is raised and provides
    the missing workbook column in the error message.

    Args:
        field (ModelField): Pydantic ArbitraryDict ModelField instance
        model_obj (dict): Data for the model constructor pulled from wb_row
        wb_row (dict): Dictionary for a provisioning workbook row

    """
    wb_key = field.field_info.extra.get("wb_key")

    if wb_key and wb_key in wb_row:
        model_obj[field.name] = to_wb_str(wb_row[wb_key])

    elif field.name in wb_row:
        model_obj[field.name] = to_wb_str(wb_row[field.name])

    elif field.required:
        col = wb_key or field.name
        raise ZeusConversionError(error=f"Required column '{col}' not found")


def default_to_wb_converter(field: ModelField, model: DataTypeBase, wb_row: dict) -> None:
    """
    Determine if the provided field should supply a value for a workbook row
    and, if so, add the value for this field in the provided model to the
    wb_row dict.

    The presence of the wb_key field property indicates that the field
    should provide a value for the workbook row.

    If wb_key is found, add this key to wb_row with the value for this
    field in the provided model.

    Args:
        field (ModelField): Pydantic ModelField
        model (DataTypeBase): Model instance being converted
        wb_row (dict): Dictionary holding converted items for the workbook
    """
    wb_key = field.field_info.extra.get("wb_key")

    if wb_key:
        value = getattr(model, field.name)
        wb_row[wb_key] = to_wb_str(value)


def default_to_payload_converter(
        field: ModelField, model_obj: dict, payload: dict, drop_unset: bool
) -> None:
    """
    Default conversion function for DataTypeBase.to_payload method.

    Adds the value for the field from model_obj to the payload dict unless
    drop_unset is True and the value is in UNSET_VALS

    This function is called only if:
    - Determination to add this field to the payload has been made
    - No specific converter for the field type exists

    Args:
        field (ModelField): Pydantic ModelField
        model_obj (dict): Dictionary from model.dict() method
        payload (dict): Dictionary holding converted items for the payload
        drop_unset (bool): If True, do not add an empty value to the payload
    """
    if drop_unset and model_obj[field.name] in UNSET_VALS:
        return

    payload[field.name] = model_obj[field.name]


def to_wb_str(value):
    """
    Convert simple values to the string representation used
    by data type models and in  the provisioning workbooks.
    - If value is None, return empty string.
    - If value is an int or float, return the string rep
    - If value is True, return "Y" as default representation for bool true in workbook
    - If value is False, return "N" as default representation for bool false in workbook
    - Otherwise return the value unmodified
    """
    if value is None:
        return ""
    if str(value).lower() in ("y", "true"):
        return "Y"
    if str(value).lower() in ("n", "false"):
        return "N"
    if isinstance(value, (int, float)):
        return str(value)

    return value


def yn_to_bool(v: str):
    """
    Convert the data type model/workbook string representation
    for boolean values to the boolean type for use in
    request payloads.
    - String 'y' -> True
    - String 'n' -> False
    - String '' -> None
    Otherwise, return the value unmodified
    """
    if str(v).lower() == "y":
        return True
    if str(v).lower() == "n":
        return False
    if str(v).lower() == "":
        return None
    return v


def validate_for_action(action, v, values, field: Field):
    if values.get("action", "").upper() == action and not v:
        col = field.field_info.extra.get("wb_key") or field.name
        raise ValueError(f"{col} is required for {action} operation.")
    return v


def validate_value_for_create(v, values, field):
    return validate_for_action("CREATE", v, values, field)


def validate_value_for_update(v, values, field):
    return validate_for_action("UPDATE", v, values, field)


def validate_value_for_delete(v, values, field):
    return validate_for_action("DELETE", v, values, field)


class DataTypeFieldDoc(BaseModel):
    """
    Holds help documentation information for a DataTypeModel field
    """
    doc_name: str
    doc_required: str = ""
    doc_value: str = ""
    doc_notes: str = ""
    field_type: str
    one_of_values: tuple = ()

    @classmethod
    def from_data_type_field(cls, field: Field, field_schema: dict):
        doc_name = field_schema.get("doc_key") or field_schema.get("wb_key")

        field_type_name = field.type_.__name__

        if "oneof" in field_type_name.lower():
            one_of_values = tuple(field.type_.values)
        else:
            one_of_values = ()

        return cls(
            doc_name=doc_name,
            doc_required=field_schema.get("doc_required", ""),
            doc_value=field_schema.get("doc_value", ""),
            doc_notes=field_schema.get("doc_notes", ""),
            field_type=field_type_name,
            one_of_values=one_of_values,
        )


class DataTypeDoc(BaseModel):
    """
    Holds help documentation information for a data type.
    This information originates from the DataTypeModel metadata
    """
    model: Type[DataTypeBase]
    data_type: str
    title: str
    description: str = ""
    doc_template: str = ""
    bulk_actions: list[str] = Field(default=[])
    doc_fields: list[DataTypeFieldDoc] = Field(default=[])
    doc_extra: dict = Field(default={})

    @classmethod
    def from_data_type_model(cls, model: Type[DataTypeBase]):
        doc_fields = []
        actions = []
        model_schema = model.schema()

        for field_name, field_schema in model_schema["properties"].items():
            field = model.__fields__[field_name]

            doc_name = field_schema.get("doc_key") or field_schema.get("wb_key")
            if not doc_name or field_schema.get("doc_ignore"):
                continue

            if field_name == "action":
                actions = [
                    value for value in
                    field.type_.values
                    if value != "IGNORE"
                ]

            doc_fields.append(DataTypeFieldDoc.from_data_type_field(field, field_schema))

        return DataTypeDoc(
            model=model,
            data_type=model_schema["data_type"],
            title=model_schema["title"],
            bulk_actions=actions,
            doc_fields=doc_fields,
            doc_template=model_schema.get("doc_template", ""),
            doc_extra=model_schema.get("doc_extra") or {},
            description=model_schema.get("description", ""),
        )
