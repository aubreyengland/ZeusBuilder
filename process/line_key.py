import os
import shutil
import pandas as pd
from migrator.models import StoreCommonArea
from migrator.utils import (
    find_excel_files,
    normalize_extension,
    format_full_extension,
    extract_corp_info,
    LINE_KEY_SETS,
)

REPORT_TEMPLATE_PATH = "templates/Zeus_HEB_Zoom_Line_Key_Template.xlsx"

def extract_line_key_targets(file_path: str) -> list[StoreCommonArea]:
    """
    Extract valid common area devices for line key generation.
    Excludes Zebra and Algo. Includes only Poly or 'Other' phones.
    """
    try:
        df = pd.read_excel(file_path, sheet_name="Zoom Import Sheet")
        result = extract_corp_info(file_path)
        if not result:
            return []

        site, raw_corp_number = result  # Unpack the tuple
        site_name = f"CORP {raw_corp_number} {site.region}".strip()  # Combine CORP XYZ and REGION

        valid_devices = []
        for _, row in df.iterrows():
            extension = format_full_extension(site.corp_number, row.get("Extension"))
            if not extension:
                continue

            device_type = str(row.get("Type", "")).strip().lower()
            phone_brand = str(row.get("Phone", "")).strip().lower()
            raw_name = str(row.get("First Name or", "")).strip()

            if device_type in {"algo", "zebra"}:
                continue
            if phone_brand.lower() not in {"poly", "polycom"}:
                continue

            # Remove trailing extension in name if present
            cleaned_name = raw_name
            if cleaned_name.endswith(extension):
                cleaned_name = cleaned_name[: -len(extension)].strip()

            final_name = f"{extension} {cleaned_name}".strip().upper()

            valid_devices.append(StoreCommonArea(
                corp_number=site.corp_number,
                name=final_name,
                extension=extension,
                site_name=site_name,  # Use the combined CORP XYZ REGION
            ))

        return valid_devices

    except Exception as e:
        print(f" Error extracting line key targets from {file_path}: {e}")
        return []

def get_line_key_set(device_name: str) -> list[dict]:
    name = device_name.upper()
    if "RX" in name:
        return LINE_KEY_SETS["RX"]
    elif "BOOKKEEPING" in name:
        return LINE_KEY_SETS["BUSCTR+BOOKKEEPING"]
    elif "BUS CTR" in name:
        return LINE_KEY_SETS["BUSCTR+BOOKKEEPING"]
    if "FAX" or "-W" in name:
        pass
    else:
        return LINE_KEY_SETS["DEFAULT"]

def generate_line_key_report(corp_number: str, common_areas: list, output_dir: str):
    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)
    # Build the full output path for this CORP
    report_file = os.path.join(output_dir, f"CORP_{corp_number}_Line_Keys.xlsx")
    if not os.path.exists(REPORT_TEMPLATE_PATH):
        print(f"Report template not found at: {REPORT_TEMPLATE_PATH}")
        return
    shutil.copy(REPORT_TEMPLATE_PATH, report_file)

    with pd.ExcelWriter(report_file, engine="openpyxl", mode="a", if_sheet_exists="overlay") as writer:
        sheet = "Line Keys"
        rows = []

        for ca in common_areas:
            if isinstance(ca, dict):
                extension = str(ca.get("Extension", "")).strip()
                raw_name = str(ca.get("Name", "")).strip()
                if raw_name.startswith(extension):
                    raw_name = raw_name[len(extension):].strip()
                name = raw_name
                site = str(ca.get("Site", "")).strip()
            else:
                extension = str(ca.extension).strip()
                name = str(ca.name).strip()
                if name.startswith(extension):
                    name = name[len(extension):].strip()
                site = str(ca.site_name).strip()

            short_ext = extension[-3:] if extension else ""

            if not extension or not name:
                continue

            try:
                formatted_ext = format_full_extension(corp_number, extension)
            except ValueError:
                print(f"❌ Skipping invalid extension '{extension}' for CORP {corp_number}")
                continue

            if "RX" in name.upper():
                key_set = LINE_KEY_SETS["RX"]
            elif any(k in name.upper() for k in ["BOOKKEEPING", "BUS CTR"]):
                key_set = LINE_KEY_SETS["BUSCTR+BOOKKEEPING"]
            elif not name.endswith("-W") and "fax" not in name.lower():
                key_set = LINE_KEY_SETS["DEFAULT"]
            else:
                continue

            row = {
                "Update": "TRUE",
                "Extension": formatted_ext,
                "Common Area Name": f"{short_ext} {name}".strip(),
                "Site": site,
            }

            for key in key_set:
                kn = key.get("key_number")
                if not kn:
                    continue
                row[f"Key {kn} Type"] = key.get("type", "")
                number_template = key.get("number", "")
                row[f"Key {kn} Number"] = number_template.format(corp_ext=corp_number)
                row[f"Key {kn} Alias"] = key.get("alias", "")

            rows.append(row)

        if not rows:
            print(f":( No line key rows generated for CORP {corp_number}")
            return
        df = pd.DataFrame(rows)
        if "Extension" in df.columns:
            df["Extension"] = df["Extension"].astype(str)
        df.to_excel(writer, sheet_name=sheet, index=False)

def build(input_folder: str) -> pd.DataFrame:
    rows = []
    for file_path in find_excel_files(input_folder):
        for common_area in extract_line_key_targets(file_path):
            key_set = get_line_key_set(common_area.name)

            # Compute full_ext and short_ext
            full_ext = format_full_extension(common_area.corp_number, common_area.extension)
            short_ext = full_ext[-3:]

            # Clean up the common area name to ensure it starts with short_ext
            raw_name = common_area.name
            # remove any leading original extension numbers if present
            if raw_name.startswith(common_area.extension):
                raw_name = raw_name[len(common_area.extension):].strip()
            common_area_name = f"{short_ext} {raw_name}".strip()

            row = {
                "Update": "TRUE",
                "Extension": full_ext,
                "Common Area Name": common_area_name,
                "Site": common_area.site_name,  # Already includes CORP XYZ REGION
            }

            for key in key_set:
                key_number = key.get("key_number")
                if not key_number:
                    continue
                row[f"Key {key_number} Type"] = key.get("type", "")
                number_template = key.get("number", "")
                row[f"Key {key_number} Number"] = number_template.format(corp_ext=common_area.corp_number)
                row[f"Key {key_number} Alias"] = key.get("alias", "")

            rows.append(row)

    return pd.DataFrame(rows)

def write(dataframe: pd.DataFrame, writer: pd.ExcelWriter, sheet_name="Line Keys"):
    dataframe.to_excel(writer, sheet_name=sheet_name, index=False)
