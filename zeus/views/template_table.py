from typing import List
from zeus.shared.helpers import deep_get
import logging

log = logging.getLogger(__name__)


class TemplateTableCol:
    """Represents a column in a html table."""

    def __init__(
        self,
        name,
        title="",
        path=None,
        hidden=False,
        default="",
        grid_track=None,
        detail_link=False,
        detail_data_type="",
        value_getter=None,
        sortable=True,
        searchable=True,
    ):
        """
        Args:
            name (str): Column name. Used to derive title and path if those attributes are not set.
            Should be unique within columns in a TemplateTable
            path (str): Key or attribute path used to get value from provided row object.
            hidden (bool): Signals to template that hidden prop should be set on <th> element.
            default (str): Value to use if an entry in a row is not found.
            grid_track (str, None): Optional, custom CSS grid track
            detail_link (bool): Signals to the template to render as a detail link if True
            detail_data_type (str): Data type that the detail link is requesting.
            value_getter (Callable, None): Optional custom callable to return a value from a row
        """
        self.name: str = name
        self._title: str = title
        self.default: str = default
        self.path = path or name
        self.hidden: bool = hidden
        self._sortable: bool = sortable
        self._searchable: bool = searchable
        self.value_getter = value_getter
        self.detail_link: bool = detail_link
        self.detail_data_type: str = detail_data_type
        self.grid_track = grid_track or "minmax(min-content, auto)"

    @property
    def sortable(self):
        return str(self._sortable).lower()

    @property
    def searchable(self):
        return str(self._searchable).lower()

    @property
    def title(self):
        """
        Provides the inner text of the <th> element.
        If a title argument was provided to the constructor, that value is used.
        Otherwise, replace underscores with spaces in the name attribute and use this.
        """
        if self._title:
            title = self._title
        else:
            parts = self.name.split("_")
            title = " ".join(p.title() for p in parts)
        return title

    def value(self, row):
        """
        Provides the inner text of a <td> attribute in this column
        based on the row object provided.

        By default, will use self.path to deep_get a value form the row.
        If a custom value_getter callable was provided, this is used instead.
        """
        if self.value_getter:
            return self.value_getter(row)

        return deep_get(row, self.path, default=self.default)


class TemplateTable:
    """Represents a html table."""

    def __init__(self, data_type, columns, rows=None, title=None):
        """
        Args:
            data_type (str): Tool data type this table represents
            columns (list): List of TemplateTableCol instances
            rows (list, None): List of dicts or data objects holding values for each table row
            title (str, None): Optional custom title. if not provided, it is derived form the data_type
        """
        self.data_type: str = data_type
        self.columns: List[TemplateTableCol] = columns
        self._rows: list = rows or []
        self._title: str = title

    @property
    def title(self):
        if self._title is None:
            return self.data_type.replace("_", " ").title()
        return self._title

    @property
    def rows(self):
        return self._rows

    @rows.setter
    def rows(self, rows):
        self._rows = rows


def bulk_table_columns(model) -> list[TemplateTableCol]:
    """
    Create TemplateTableCol instances for a bulk table using the fields in the
    provided data type model class.

    A TemplateTableCol is created for each field with a `wb_key` property and sets
    a custom grid_track value for the Action column and the ID column.

    Args:
        model (Type[DataTypeBase]): Data type model class

    Returns:
        columns: (list[TemplateTableCol])
    """
    id_field = model.schema()["id_field"]
    columns = [TemplateTableCol("action", grid_track="90px")]

    for name, field in model.schema()["properties"].items():
        wb_key = field.get("wb_key")

        if not wb_key or name == "action":
            continue

        if name == id_field:
            grid_track = "minmax(max-content, auto)"

        else:
            grid_track = "minmax(min-content, auto)"

        columns.append(TemplateTableCol(name=name, title=wb_key, grid_track=grid_track))

    return columns


def default_bulk_table(model, rows=None) -> TemplateTable:
    """
    Create a table for a bulk worksheet with columns matching
    model wb_keys.
    Identify the id field (name usually) and set the grid-track
    to max-content to prevent word wrapping for this column.
    """
    id_field = model.schema()["id_field"]
    data_type = model.schema()["data_type"]
    title = model.schema()["title"]

    columns = bulk_table_columns(model)

    return TemplateTable(
        data_type=data_type,
        columns=columns,
        rows=rows,
        title=title,
    )


def bulk_table(data_type, columns, rows=None, title=None) -> TemplateTable:
    """
    Helper function to create a custom bulk TemplateTable.
    Insert an action column if it does not already exist
    """
    if "action" not in [col.name for col in columns]:
        columns.insert(0, TemplateTableCol("action", grid_track="90px"))

    return TemplateTable(data_type, columns, rows, title=title)


def default_browse_table(model, rows=None) -> TemplateTable:
    """
    Create a default TemplateTable for the provided model.

    The default TemplateTable includes only required fields
    in the model.

    Args:
         model (Type[DataTypeBase]): DataTypeBase class object
         rows (list| None): List of dictionaries returned by the Browse service

    Returns:
         (TemplateTable): TemplateTable instance
    """
    data_type = model.schema()["data_type"]
    title = model.schema()["title"]

    columns = []

    for name, field in model.__fields__.items():
        if field.required and name != "action":
            columns.append(TemplateTableCol(name=name))

    if rows and all(["detail_id" in row for row in rows]):
        columns.extend(detail_columns(data_type))

    return TemplateTable(
        data_type=data_type,
        columns=columns,
        rows=rows,
        title=title,
    )


def detail_columns(detail_data_type) -> list[TemplateTableCol]:
    """
    Convenience function to return columns necessary to include
    a detail link in a browse table.

    This includes a column for the hidden detail_id value and a column
    for the detail link icon.
    """
    return [
        TemplateTableCol("detail_id", hidden=True),
        TemplateTableCol(
            "detail_link",
            title=" ",
            sortable=False,
            searchable=False,
            detail_link=True,
            detail_data_type=detail_data_type
        ),
    ]
