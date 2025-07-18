import logging
from typing import Callable

log = logging.getLogger(__name__)


class Registry:
    """
    Base Registry class.

    Provides a simple mechanism for Views and Services to find tool-related resources based
    on one or more labels (data type, for instance).

    The tool-related resources register with a Registry when defined using a decorator
    that includes the tool and one or more labels that, together, can be used by
    consumers to uniquely identify the needed resource.

    Example:
        # register a function in one module
        @Registry.register('five9', 'a', 'b')
        def five9_a_b_resource():
            ...

        # another module needs the five9 function with this label
        func = Registry.get('five9', 'a', 'b')
        func()

    Registered resources are stored in the `__items__` dictionary class attribute.
    A nested dictionary is created for each tool with the labels used to create a key
    to store the resource. This ensures the same labels can be used by across tools.

    A separate Registry subclass can be defined for each resource type.
    """
    __items__ = {}

    @classmethod
    def _key(cls, *labels) -> str:
        """
        Create a key from the provided labels to uniquely identify the
        resource. The key will be lower-case to provide case-insensitive
        lookups
        """
        return f".".join(str(label).lower() for label in labels)

    @classmethod
    def register(cls, tool, *labels):
        """
        Add an object to the registry for using the provided tool
        and labels. Intended to be used as a decorator around
        the resource to add.

        ```
        @Registry.register('tool', 'label1', 'label2')
        def resource():
            ...
        ```

        Args:
            tool (str): five9, zoom, etc.
            *labels: One or more labels used to create a unique key
        """
        tool = str(tool).lower()
        tool_items = cls.__items__.setdefault(tool, {})
        key = cls._key(*labels)

        def wrapper(wrapped):
            tool_items[key] = wrapped
            return wrapped

        return wrapper

    @classmethod
    def get(cls, tool, *labels):
        """
        Return the resource from the registry matching the provided tool
        and labels.

        If the resource is not found, raise a LookupError

        Args:
            tool (str): five9, zoom, etc.
            *labels: One or more labels used to create a unique key
        """
        tool = str(tool).lower()
        tool_items = cls.__items__.setdefault(tool, {})
        key = cls._key(*labels)

        if key not in tool_items:
            raise LookupError(f"Item of key: {key} not found in {tool} registry")

        return tool_items[key]


class TableRegistry(Registry):
    """
    Registry for table-building functions.

    Allows Views to discover the appropriate table builder
    based on the tool, operation and data type.

    Use the `browse_table` and `bulk_table` decorators to register
    the table functions using the appropriate tool and data type:

    Example:

    ```
    @browse_table('five9', 'skills')
    def browse_skill_table(rows=None):
        ...
    ```
    """
    __items__ = {}


def browse_table(tool, data_type_name):
    return TableRegistry.register(tool, "browse", data_type_name)


def bulk_table(tool, data_type_name):
    return TableRegistry.register(tool, "bulk", data_type_name)


def detail_table(tool, data_type_name):
    return TableRegistry.register(tool, "detail", data_type_name)


def get_browse_table(tool, data_type_name):
    return TableRegistry.get(tool, "browse", data_type_name)


def get_bulk_table(tool, data_type_name):
    return TableRegistry.get(tool, "bulk", data_type_name)


def get_detail_table(tool, data_type_name):
    return TableRegistry.get(tool, "detail", data_type_name)


class DataTypeRegistry(Registry):
    """
    Registry of data type models by tool and data type.

    Allows Views and Services to discover data types and
    get their associated models.

    Data types are registered by applying the `data_type` decorator
    with the tool and data_type value to the model.

    Example:

    ```
    @data_type("five9", "skills")
    class Five9Skill(DataTypeModel):
        ...
    ```
    """
    __items__ = {}

    @classmethod
    def get_data_types(cls, tool) -> dict:
        """Returns a dictionary of data_types and models for the tool"""
        return cls.__items__.get(tool, {})


def data_type(tool, data_type_name):
    return DataTypeRegistry.register(tool, data_type_name)


def get_data_type(tool, data_type_name):
    return DataTypeRegistry.get(tool, data_type_name)


def get_data_types(tool, supports=None) -> dict:
    """
    Return models for the provided tool.
    Filter these by those that support a specific operation
    if the supports argument is provided

    Args:
        tool (str): five9, zoom, etc.
        supports (str|None): export, bulk, browse, detail

    Returns:
        (dict): data type name as key, model as value
    """
    def is_supported(model, value):
        value = str(value.lower())
        supported_actions = model.schema()["supports"]
        return supported_actions.get(value, False)

    data_types = DataTypeRegistry.get_data_types(tool)

    if supports:
        data_types = {
            k: v for k, v in data_types.items()
            if is_supported(v, supports)
        }

    return data_types


class SvcRegistry(Registry):
    """
    Registry of Services by tool operation and data type.

    Allows the SvcClient to determine the correct Service class
    for a service request

    Service are registered by applying the `data_type` decorator
    with the tool and necessary labels to the Service class.

    Example:

    ```
    @browse_svc('five9', 'skills')
    class Five9SkillBrowseSvc(BrowseSvc):
        ...

    @bulk_svc('five9', 'skills', 'create')
    class Five9SkillCreateSvc(BulkSvc):
        ...
    ```
    """
    __items__ = {}

    @classmethod
    def get_service(cls, tool, operation, *labels) -> Callable:
        return cls.get(tool, operation, *labels)

    @classmethod
    def register_service(cls, tool, operation, *labels) -> Callable:
        return cls.register(tool, operation, *labels)


def browse_service(tool, data_type_name):
    return SvcRegistry.register(tool, "browse", data_type_name)


def bulk_service(tool, data_type_name, action):
    return SvcRegistry.register(tool, "bulk", data_type_name, action)


def export_service(tool, data_type_name):
    return SvcRegistry.register(tool, "export", data_type_name)


def detail_service(tool, data_type_name):
    return SvcRegistry.register(tool, "detail", data_type_name)


def upload_task(tool, data_type_name):
    return SvcRegistry.register(tool, "upload", data_type_name)


def get_browse_service(tool, data_type_name):
    return SvcRegistry.get(tool, "browse", data_type_name)


def get_bulk_service(tool, data_type_name, action):
    return SvcRegistry.get(tool, "bulk", data_type_name, action)


def get_export_service(tool, data_type_name):
    return SvcRegistry.get(tool, "export", data_type_name)


def get_detail_service(tool, data_type_name):
    return SvcRegistry.get(tool, "detail", data_type_name)


def get_upload_task(tool, data_type_name):
    return SvcRegistry.get(tool, "upload", data_type_name)
