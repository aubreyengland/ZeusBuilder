# process/shared_line_group.py
import pandas as pd
from migrator.models import StoreSharedLineGroup
from migrator.utils import find_excel_files, extract_corp_info, format_full_extension
from migrator.utils import normalize_extension

def extract_shared_line_group(file_path: str) -> StoreSharedLineGroup | None:
    try:
        df = pd.read_excel(file_path, sheet_name="Zoom Import Sheet")
        result = extract_corp_info(file_path)
        if not result:
            return None

        site, raw_corp_number, _ = result  # Unpack the tuple
        site_name = f"CORP {raw_corp_number} {site.region}".strip() 
        
        
        if not site:
            return None

        # Explicit match list (all lowercase for comparison)
        valid_names = {
            "bookkeeping 1",
            "bookkeeping 2",
            "bus ctr 1",
            "bus ctr 2",
            "bus ctr 3",
            "bus ctr 4",
        }
        
            

        # Filter rows where "First Name" matches any from the list
        df["First Name Normalized"] = df["First Name or"].astype(str).str.lower().str.strip()
        filtered = df[df["First Name Normalized"].isin(valid_names)]

        extensions = []
        for _, row in filtered.iterrows():
            ext = normalize_extension(row.get("Extension"))
            if ext.isdigit() and len(ext) == 3:
                extensions.append(format_full_extension(site.corp_number, ext))

        members = ",".join(extensions)

        if not members:
            return None

        return StoreSharedLineGroup(
            corp_number=site.corp_number,
            name="SERVICE SHARED LINE",
            extension="863",
            members=members,
            site_name=site_name,
        )

    except Exception as e:
        print(f"❌ Error processing SLG from {file_path}: {e}")
        return None


def build(input_folder: str) -> pd.DataFrame:
    rows = []
    for file_path in find_excel_files(input_folder):
        slg = extract_shared_line_group(file_path)
        if not slg:
            continue
        site = extract_corp_info(file_path)
        if not site:
            continue

        rows.append({
            "Name": slg.name,
            "Site Name": slg.site_name,
            "Extension Number": "863", 
            "Phone Number": "",
            "Primary Number": "",
            "Members": slg.members,
            "Department": f"CORP {slg.corp_number} SERVICE",
            "Cost Center": f"CORP {slg.corp_number}",
            "Shared Line Group Status": "Active",
            "Audio Prompt Language": "en-US",
            "Private Calls": "Off"
        })
        
        # RX Shared Line Group
        df = pd.read_excel(file_path, sheet_name="Zoom Import Sheet")
        df["First Name Normalized"] = df["First Name or"].astype(str).str.lower().str.strip()
        rx_filtered = df[df["First Name Normalized"].str.contains("rx", na=False)]

        if not rx_filtered.empty:
            rx_extensions = []
            for _, row in rx_filtered.iterrows():
                ext = normalize_extension(row.get("Extension"))
                if ext.isdigit() and len(ext) == 3:
                    rx_extensions.append(format_full_extension(slg.corp_number, ext))

            rx_members = ",".join(rx_extensions)
            if rx_members:
                rows.append({
                    "Name": "RX SHARED LINE",
                    "Site Name": slg.site_name,
                    "Extension Number": "525",
                    "Phone Number": "",
                    "Primary Number": "",
                    "Members": rx_members,
                    "Department": f"CORP {slg.corp_number} RX",
                    "Cost Center": f"CORP {slg.corp_number}",
                    "Shared Line Group Status": "Active",
                    "Audio Prompt Language": "en-US",
                    "Private Calls": "Off"
                })
    return pd.DataFrame(rows)


def write(dataframe: pd.DataFrame, writer: pd.ExcelWriter, sheet_name="Shared Line Groups"):
    dataframe.to_excel(writer, sheet_name=sheet_name, index=False)