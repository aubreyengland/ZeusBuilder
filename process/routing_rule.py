# process/alerts.py
import pandas as pd
from migrator.utils import extract_corp_info
from migrator.utils import find_excel_files

def build(input_folder: str) -> pd.DataFrame:
    rows = []

    for file_path in find_excel_files(input_folder):
        result = extract_corp_info(file_path)
        if not result:
            continue
        store, raw_corp_number = result
        full_corp_number = raw_corp_number.zfill(3)
        site_name = f"CORP {full_corp_number} {store.region}".strip()

        rows.append({
            "Action": "CREATE",
            "Name": "3-DIGIT EXTEN TO 7 DIGIT EXTN",
            "Site": site_name,
            "Number Pattern": r"^([0-8])(\d{2})$",
            "Translation": f"{raw_corp_number}0$1$2",
            "SIP Group ID": "",
            "Rule Type": "Other Sites",
        })

    return pd.DataFrame(rows)


def write(dataframe: pd.DataFrame, writer: pd.ExcelWriter, sheet_name="Routing Rules"):
    dataframe.to_excel(writer, sheet_name=sheet_name, index=False)