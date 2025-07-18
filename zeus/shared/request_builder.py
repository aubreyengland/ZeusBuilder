from .helpers import deep_get
from zeus.shared.data_type_models import DataTypeBase

_NOT_SET = object()
NULL_VALUES = ("", None, [], {}, _NOT_SET)


class RequestField:
    """
    Represents an entry in a payload dictionary.
    The key is `self.name`.
    The value is determined when the instance is called
    based on the provided data arguments.
    """

    def __init__(self, name, alias=None):
        """
        Args:
        name: (str): The key in the payload dictionary and acts
         as a secondary lookup attribute
        alias (str, None): Identifies the key, attribute or path to get
        the value from the provided data sources. If not provided, name is used.
        """
        self.name: str = name
        self.alias: str = alias or name
        self._null = None
        self.value = self._null
        self.null_values = NULL_VALUES
        self._request_value = _NOT_SET
        self._current_value = _NOT_SET
        self.rollback_value = self._null

    @property
    def should_include(self) -> bool:
        return True

    @property
    def is_changed(self) -> bool:
        return self._request_value != self._current_value

    def __call__(self, request_data, current_data, extra=None, backfill=True):
        """
        Determine the value for this field based on the provided data sources.
        The value will be taken from `request_data` if  a deep_get for `self.alias`
        or `self.name` returns a value.

        If a value is not found in `request_data` the same lookup process is done
        against the extra data (if provided). This is useful for passing in IDs that
        are resolved within the service/task.

        If a value is not found in `request_data` or `extra` AND `backfill` is True,
        the same lookup process will be done against the `current_data` (if provided).

        Ultimately, `self.value` is set to the value from a successful lookup or
        `self._null` is no lookup was successful.
        """
        request_data = request_data or {}
        current_data = current_data or {}
        extra = extra or {}

        self._request_value = self._lookup_value(request_data, extra)
        self._current_value = self._lookup_value(current_data)

        self._set_value(backfill)
        self._set_rollback_value()

    def _lookup_value(self, *sources):
        """
        Perform a deep_get on each source using self.alias first,
        then self.name and return the first value found.
        If a value is not found, return _NOT_SET.
        Args:
            sources (Iterable[dict|BaseModel]
        """
        for source in sources:
            for attr in (self.alias, self.name):
                value = deep_get(source, attr, default=_NOT_SET)

                if value != _NOT_SET:
                    return value

        return _NOT_SET

    def _set_value(self, backfill: bool):
        """
        Value is set in the following priority order:
        - Set to the `payload()` return value if _request_value is a RequestBuilder instance
        - Set to `_request_value` if it has a value
        - Set to `_current_value` if it has a value and `backfill` is True
        - Set to `_null`
        """
        if self._request_value != _NOT_SET:
            if isinstance(self._request_value, RequestBuilder):
                self.value = self._request_value.payload()
            else:
                self.value = self._request_value

        elif self._current_value != _NOT_SET and backfill:
            if isinstance(self._request_value, RequestBuilder):
                self.value = self._request_value.payload()
            else:
                self.value = self._current_value
        else:
            self.value = self._null

    def _set_rollback_value(self):
        """
        Value is set in the following priority order:
        - Set to the `rollback()` return value if _request_value is a RequestBuilder instance
        - Set to `_current_value` if it has a value
        - Set to `_null`
        """
        if self._current_value != _NOT_SET:
            if isinstance(self._request_value, RequestBuilder):
                self.rollback_value = self._request_value.rollback()
            else:
                self.rollback_value = self._current_value
        else:
            self.rollback_value = self._null

    def __repr__(self):
        return f"{type(self).__name__}: {self.name=}"


class RequiredField(RequestField):
    """
    Field is always included.
    If a value is not found in the provided data or defaults,
    `self.null` is used
    """

    @property
    def should_include(self):
        return True


class ValuedField(RequestField):
    """
    Field will only be included in payload if
    the resolved value is not in `self.nulls`
    """

    @property
    def should_include(self):
        if self.value in self.null_values:
            return False
        return True


class ChangedField(RequestField):
    """
    Field will only be included in payload if
    - the resolved value is not in `self.nulls` AND
    - the resolved value differs from `self._current_value`
    """

    @property
    def should_include(self):
        if self.value in self.null_values:
            return False
        if self.value == self._current_value:
            return False
        return True


class RequestBuilder:
    """
    Represents an API payload dictionary with entries based on
    the provided `RequestField`s and values from the provided
    data, current objects and kwargs.

    The `build` method constructs a dictionary for an API update
    using the provided `RequestField`s with entries included/excluded
    based on each field's `should_include` property.

    The `build_rollback` method constructs a dictionary to undo the update
    by replacing values in the update payload with values from the `self.current`
    data.
    """
    def __init__(
        self,
        fields: list[RequestField],
        data: dict | DataTypeBase,
        current: dict | None = None,
        backfill: bool = True,
        **extra,
    ):
        """
        Creates update and rollback payloads.

        Args:
            fields (list[RequestField]): List of potential payload fields
            data (dict|BaseModel): Data used to create the update payload
            current (dict|BaseModel): Data used to backfill the update payload
             create the rollback payload
            backfill (bool): Backfill payload with current_data if True
            **extra: Additional items (not included in 'data') used for the update payload
        """
        self.fields: list[RequestField] = fields
        self.data = data
        self.current = current or {}
        self.backfill = backfill
        self.extra = extra
        self.__payload__ = _NOT_SET

    def payload_is_changed(self) -> bool:
        self.payload()
        return any([f.is_changed for f in self.fields])

    def _process_fields(self):
        errors = {}
        for field in self.fields:
            try:
                field(self.data, self.current, self.extra, backfill=self.backfill)
            except ValueError as exc:
                errors[field.name] = str(exc)

        if errors:
            raise ValueError(errors)

    def payload(self) -> dict:
        """
        Return a create/update payload dictionary.

        The backfill argument determine if a value from self.current
        may be used for a payload field if a value is not found in self.data.
        """
        if self.__payload__ is _NOT_SET:
            payload = {}
            self._process_fields()

            for field in self.fields:
                if field.should_include:
                    payload[field.name] = field.value

            self.__payload__ = payload

        return self.__payload__

    def rollback(self) -> dict:
        """
        Return a dictionary to revert changes made using the payload
        back to their original values.

        The rollback dictionary will include keys from the payload
        dictionary for which a current value exists.
        This is done because, if incomplete current data is available,
        it is safer to do a partial rollback than to potentially null
        values that were not originally null.
        """
        rollback_payload = {}
        for field in self.fields:
            if field.name in self.payload():
                if field._current_value != _NOT_SET:
                    rollback_payload[field.name] = field.rollback_value

        return rollback_payload
