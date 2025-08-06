import os
import pandas as pd
from migrator.models import StoreCallQueue
from migrator.utils import find_excel_files, normalize_extension, extract_corp_info, format_full_extension, extract_rx_number


def extract_call_queues(file_path: str) -> list[StoreCallQueue]:
    try:
        df = pd.read_excel(file_path, sheet_name="Zoom CQs")
        result = extract_corp_info(file_path)
        if not result:
            return []
        site, raw_corp_number, _ = result  # Unpack the tuple
        corp_number = raw_corp_number.zfill(3)
        site_name = f"CORP {corp_number} {site.region}".strip()

        # Initialize list to store call queues
        call_queues = []

        for _, row in df.iterrows():
            # Normalize extension
            ext_suffix = normalize_extension(row.get("Extentsion", ""))
            if pd.isna(ext_suffix):
                continue

            extension = format_full_extension(corp_number, ext_suffix)
            if not extension:
                continue

            three_digit_extension = str(int(float(ext_suffix))).zfill(3)

            # Normalize Hunt Group name (remove " HG", uppercase, prepend extension)
            hunt_group_name = str(row.get("Hunt Group", "")).strip().upper()
            if hunt_group_name.endswith(" HG"):
                hunt_group_name = hunt_group_name[:-3].strip()
            normalized_name = f"{ext_suffix} {hunt_group_name} CQ"

            # Normalize members
            raw_members_raw = row.get("Members", "")
            if pd.isna(raw_members_raw) or not str(raw_members_raw).strip():
                members_final = ""
            else:
                raw_members = str(raw_members_raw).replace(",", " ")
                normalized_members = []
                for ext in raw_members.split():
                    ext = ext.strip()
                    if ext.isdigit() and len(ext) == 3:
                        formatted_ext = format_full_extension(corp_number, ext)
                        if formatted_ext.startswith("0"):
                            formatted_ext = "9" + formatted_ext[1:]
                        normalized_members.append(formatted_ext)
                    elif ext.isdigit() and len(ext) == 7:
                        normalized_members.append(ext)
                    else:
                        normalized_members.append(ext)
                members_final = ",".join(normalized_members).strip()

            cq = StoreCallQueue(
                corp_number=corp_number,
                site_name=site_name,  # Use the combined CORP XYZ REGION
                name=normalized_name,
                extension=three_digit_extension,
                members=members_final,
            )
            call_queues.append(cq)

        return call_queues

    except Exception as e:
        print(f"❌ Error extracting call queues from {file_path}: {e}")
        return []


def build(input_folder: str) -> pd.DataFrame:
    all_rows = []

    for file_path in find_excel_files(input_folder):
        rx_number = extract_rx_number(file_path)
        for cq in extract_call_queues(file_path):
            
            department = cq.site_name
            if "RX" in cq.name.upper():
                department += " RX"
            elif "E-STORE" in cq.name.upper():
                department += " E-STORE"

            phone_numbers_value = rx_number if cq.extension == "605" and rx_number else ""

            all_rows.append({
                "Name": cq.name,
                "Site Name": cq.site_name,  # Use the combined CORP XYZ REGION
                "Extension": cq.extension,
                "Phone Numbers": phone_numbers_value,
                "Members": cq.members,
                "Department": department,  # Use the combined CORP XYZ REGION
                "Cost Center": cq.site_name,  # Use the combined CORP XYZ REGION
                "Status": "Active",
                "Audio Prompt Language": "en-US",
                "Set Business Hours": "On",
            })

    return pd.DataFrame(all_rows)

def write(dataframe: pd.DataFrame, writer: pd.ExcelWriter, sheet_name="Call Queues"):
    dataframe.to_excel(writer, sheet_name=sheet_name, index=False)