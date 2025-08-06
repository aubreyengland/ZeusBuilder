# process/alerts.py
import pandas as pd
from migrator.models import StoreData
from migrator.utils import find_excel_files, resolve_region, extract_corp_info

def build(input_folder: str, alert_emails: list[str]) -> pd.DataFrame:
    rows = []

    for file_path in find_excel_files(input_folder):
        site, _, _ = extract_corp_info(file_path)
        if not site:
            continue

        rows.append({
            "Action": "CREATE",
            "Name": f"{site.name} 911 ALERT",
            "Site": site.name,
            # "Module": "Emergency Services Management",
            # "Rule": "Emergency Call Alert",
            # "Condition": "Critical",
            # "Time Frame Type": "all_day",
            # "Frequency": "daily",
            # "Time Frame From": "00:00:00",
            # "Time Frame To": "00:00:00",
            "Email Recipients": ",".join(alert_emails),
            # "Chat Channels": "",
            "Status": "active",       
        })

    return pd.DataFrame(rows)



def write(dataframe: pd.DataFrame, writer: pd.ExcelWriter, sheet_name="Alerts"):
    dataframe.to_excel(writer, sheet_name=sheet_name, index=False)