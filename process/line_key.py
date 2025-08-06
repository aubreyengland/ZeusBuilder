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

        site, raw_corp_number, common_name = result  # Unpack the tuple
        site_name = f"CORP {raw_corp_number} {site.region}".strip()  # Combine CORP XYZ and REGION

        retrieved_common_name = common_name.upper().strip() if common_name else ":( COMMON NAME NOT FOUND!!! :("

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
                site_name=site_name,
                common_name=retrieved_common_name
            ))

        return valid_devices

    except Exception as e:
        print(f" Error extracting line key targets from {file_path}: {e}")
        return []


def get_line_key_set(device_name: str, retrieved_common_name: str) -> list[dict]:
    name = device_name.upper()
    common_name = retrieved_common_name.upper()
    if "CENTRAL MARKET" in common_name:
        return LINE_KEY_SETS["CENTRAL_MARKET_DEFAULT"]
    elif "BASE OPS" in name:
        return LINE_KEY_SETS["BASEOPS+INFODESK"]
    elif "INFORMATION DESK" in name:
        return LINE_KEY_SETS["BASEOPS+INFODESK"]
    elif "RX" in name:
        return LINE_KEY_SETS["RX"]
    elif "BOOKKEEPING" in name:
        return LINE_KEY_SETS["BUSCTR+BOOKKEEPING"]
    elif "BUS CTR" in name:
        return LINE_KEY_SETS["BUSCTR+BOOKKEEPING"]
    if "FAX" or "-W" in name:
        pass
    else:
        return LINE_KEY_SETS["CENTRAL_MARKET_DEFAULT"]

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
            # Extract and format extension and raw name, using corp number derived from each row's site
            raw_extension = str(ca.get("Extension", "") if isinstance(ca, dict) else ca.extension).strip()
            raw_site = str(ca.get("Site", "") if isinstance(ca, dict) else ca.site_name).strip()
            # Extract the corp number from the row's site (assumes format "CORP XYZ ...")
            try:
                row_corp = raw_site.split()[1]
            except (IndexError, TypeError):
                row_corp = corp_number
            extension = format_full_extension(row_corp, raw_extension)
            raw_name = str(ca.get("Name", "") if isinstance(ca, dict) else ca.name).strip()
            site = raw_site

            short_ext = extension[-3:] if extension else ""
            if not extension or not raw_name:
                continue

            # Derive descriptive name (drop any leading short_ext or numeric prefix)
            if raw_name.startswith(short_ext):
                desc = raw_name[len(short_ext):].strip()
            elif " " in raw_name:
                desc = raw_name.split(" ", 1)[1].strip()
            else:
                desc = raw_name

            upper_desc = desc.upper()
            # skip FAX, PAGE, PROMPT entries, any REG entries, or those ending with "-W"
            if any(keyword in upper_desc for keyword in ["FAX", "PAGE", "PROMPT"]) or upper_desc.startswith("REG") or upper_desc.endswith("-W"):
                continue

            # Determine the appropriate line key set
            if "CENTRAL MARKET" in ((ca.get("Common Name", "") if isinstance(ca, dict) else ca.common_name).upper().strip()):
                key_set = LINE_KEY_SETS["CENTRAL_MARKET_DEFAULT"]
            elif "RX" in upper_desc:
                key_set = LINE_KEY_SETS["RX"]
            elif any(k in upper_desc for k in ["BOOKKEEPING", "BUS CTR"]):
                key_set = LINE_KEY_SETS["BUSCTR+BOOKKEEPING"]
            elif "BASE OPS" in upper_desc:
                key_set = LINE_KEY_SETS["BASEOPS+INFODESK"]
            elif "INFORMATION DESK" in upper_desc:
                key_set = LINE_KEY_SETS["BASEOPS+INFODESK"]
            else:
                key_set = LINE_KEY_SETS["CENTRAL_MARKET_DEFAULT"]

            # Build the row dictionary
            row = {
                "Update": "TRUE",
                "Extension": extension,
                "Common Area Name": f"{short_ext} {desc}".strip(),
                "Site": site,
            }
            for key in key_set:
                kn = key.get("key_number")
                if not kn:
                    continue
                row[f"Key {kn} Type"] = key.get("type", "")
                row[f"Key {kn} Number"] = key.get("number", "").format(corp_ext=row_corp, extension=short_ext)
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
            key_set = get_line_key_set(common_area.name, common_area.common_name)

            # Use extension as-is (avoid double-formatting)
            full_ext = common_area.extension
            short_ext = full_ext[-3:] if full_ext else ""

            # Clean up the common area name to ensure it starts with short_ext, and avoid double short_ext
            raw_name = common_area.name
            if raw_name.startswith(full_ext):
                raw_name = raw_name[len(full_ext):].strip()
            name_part = raw_name
            if name_part.startswith(short_ext):
                name_part = name_part[len(short_ext):].strip()
            common_area_name = f"{short_ext} {name_part}".strip()

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
                row[f"Key {key_number} Number"] = number_template.format(corp_ext=common_area.corp_number, extension=short_ext)
                row[f"Key {key_number} Alias"] = key.get("alias", "")

            rows.append(row)

    return pd.DataFrame(rows)

def write(dataframe: pd.DataFrame, writer: pd.ExcelWriter, sheet_name="Line Keys"):
    dataframe.to_excel(writer, sheet_name=sheet_name, index=False)
