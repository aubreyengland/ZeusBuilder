from zeus import registry
from zeus.shared.helpers import ensure_all_rows_include_all_columns


class ExportPostProcessor:

    def __init__(self, tool, export_data):
        self.tool: str = tool
        self.export_data: dict[str, dict] = export_data
        self.wb_data: dict[str, list[dict]] = {}

    def run(self):
        """
        Process the results of the export jobs and prepare for
        workbook creation
        """
        self.process_export_data()
        self.convert_for_wb()
        self.add_errors_sheet()
        self.add_missing_columns()
        return self.wb_data

    def process_export_data(self):
        """Allows processing of export data after all export jobs have completed."""
        pass

    def convert_for_wb(self):
        """
        Convert data type models returned by the export jobs into
        dictionaries with the expected worksheet column headers.

        If an export contains no data, create a blank row so the worksheet
        will have the expected headers.
        """

        for data_type, exported_items in self.export_data.items():
            model = registry.get_data_type(self.tool, data_type)
            sheetname = model.schema()["title"]
            export_rows = exported_items.get("rows")

            if not export_rows:
                self.wb_data[sheetname] = [{d.doc_name: "" for d in model.model_doc().doc_fields}]
            else:
                self.wb_data[sheetname] = [item.to_wb() for item in export_rows]

    def add_missing_columns(self):
        for sheetname, rows in self.wb_data.items():
            self.wb_data[sheetname] = ensure_all_rows_include_all_columns(rows)

    def add_errors_sheet(self):
        """
        Convert data type models returned by the export jobs into
        dictionaries with the expected worksheet column headers.

        If an export contains no data, create a blank row so the worksheet
        will have the expected headers.
        """
        error_rows = []
        for data_type, exported_items in self.export_data.items():
            export_errors = exported_items.get("errors") or []

            for error_item in export_errors:

                row = {"type": data_type}
                row.update(error_item)
                error_rows.append(row)

        if error_rows:
            self.wb_data["Export Errors"] = error_rows



