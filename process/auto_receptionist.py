import pandas as pd
from migrator.utils import find_excel_files, extract_corp_info, format_full_extension


# Key action + target structure (these values match the pattern in the example)
DEFAULT_ENGLISH_KEYS = {
    "No Entry Action": "Shared Line Group",
    "No Entry Target": "0863",
    "Key 0 Action": "Shared Line Group",
    "Key 0 Target": "0863",
    "Key 1 Action": "Auto Receptionist",
    "Key 1 Target": "0002",
    "Key 2 Action": "Call Queue",
    "Key 2 Target": "0678",
    "Key 3 Action": "Call Queue",
    "Key 3 Target": "0603",
    "Key 4 Action": "Call Queue",
    "Key 4 Target": "0698",
    "Key 5 Action": "Call Queue",
    "Key 5 Target": "0606",
    "Key 6 Action": "Call Queue",
    "Key 6 Target": "0607",
    "Key 7 Action": "Call Queue",
    "Key 7 Target": "0602",
    "Key 8 Action": "Call Queue",
    "Key 8 Target": "0609",
    "Key 9 Action": "Call Queue",
    "Key 9 Target": "0620",
    "Key * Action": "Repeat Greeting",
}

DEFAULT_SPANISH_KEYS = {
    "No Entry Action": "Shared Line Group",
    "No Entry Target": "0863",
    "Key 0 Action": "Shared Line Group",
    "Key 0 Target": "0863",
    "Key 1 Action": "",
    "Key 1 Target": "",
    "Key 2 Action": "Call Queue",
    "Key 2 Target": "0678",
    "Key 3 Action": "Call Queue",
    "Key 3 Target": "0603",
    "Key 4 Action": "Call Queue",
    "Key 4 Target": "0698",
    "Key 5 Action": "Call Queue",
    "Key 5 Target": "0606",
    "Key 6 Action": "Call Queue",
    "Key 6 Target": "0607",
    "Key 7 Action": "Call Queue",
    "Key 7 Target": "0602",
    "Key 8 Action": "Call Queue",
    "Key 8 Target": "0609",
    "Key 9 Action": "Call Queue",
    "Key 9 Target": "0620",
    "Key * Action": "Repeat Greeting",
}


DEFAULT_ENGLISH_KEYS.update({
})

DEFAULT_SPANISH_KEYS.update({
})

def build_ar_rows(corp_number: str, site_name: str) -> list[dict]:
    rows = []

    for lang, ext_suffix in [("SPANISH", "0002")]:
        row = {
            "Action": "CREATE",
            "Name": f"{site_name} - {lang}",
            "Site": site_name,  # Use the combined CORP XYZ REGION
            "Extension": "0002",  # Use processed corp number
            "Timezone": "America/Chicago",
            "Phone Numbers": "",
            "Prompt Repeat": 3,
            "Prompt Language": "es-US",
        }

        # Fill keys by rewriting corp prefix in targets
        for key, value in DEFAULT_SPANISH_KEYS.items():
            if "Target" in key and value:
                row[key] = format_full_extension(corp_number, value[-4:]) # Keep last 4 digits
            else:
                row[key] = value

        rows.append(row)

        
    # Process for English Auto Receptionist
    for lang, ext_suffix in [("ENGLISH", "0001")]:
        row = {
            "Action": "UPDATE",
            "Name": f"{site_name} - {lang}",
            "Site": site_name,  # Use the combined CORP XYZ REGION
            "Extension": format_full_extension(corp_number, ext_suffix),  # Use processed corp number
            "Timezone": "America/Chicago",
            "Phone Numbers": f"{site_name} MAIN NUMBER",
            "Prompt Repeat": 3,
            "Prompt Language": "en-US",
        }

        # Fill keys by rewriting corp prefix in targets
        for key, value in DEFAULT_ENGLISH_KEYS.items():
            if "Target" in key and value:
                row[key] = format_full_extension(corp_number, value[-4:]) # Keep last 4 digits
            else:
                row[key] = value

        rows.append(row)
        return rows




def build(input_folder: str) -> pd.DataFrame:
    all_rows = []
    for file_path in find_excel_files(input_folder):
        result = extract_corp_info(file_path)
        if not result:
            continue

        site, raw_corp_number = result  # Unpack the tuple
        site_name = f"CORP {raw_corp_number} {site.region}".strip()  # Combine CORP XYZ and REGION

        # Generate rows for the Auto Receptionist
        all_rows.extend(build_ar_rows(site.corp_number, site_name))  # Use processed corp number and combined site name

    return pd.DataFrame(all_rows)

def write(dataframe: pd.DataFrame, writer: pd.ExcelWriter, sheet_name="Auto Receptionists"):
    dataframe.to_excel(writer, sheet_name=sheet_name, index=False)