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

def extract_zoom_menu_targets(file_path: str) -> dict:
    try:
        cf = pd.read_excel(file_path, sheet_name="CALL FLOW", header=None)
        menu_row = cf[cf.apply(lambda row: row.astype(str).str.contains("MENU SCRIPT", case=False).any(), axis=1)]
        if menu_row.empty:
            return {}

        row_idx = menu_row.index[0]

        menu_text = cf.iloc[row_idx, 2]
        if pd.isna(menu_text):
            return {}

        lines = str(menu_text).splitlines()

        targets = {}

        for line in lines:
            line = line.strip()
            if not line or '(' not in line or ')' not in line:
                continue
            # Extract key digit (before dot)
            key_digit_part = line.split('.')[0].strip()
            if not key_digit_part.isdigit():
                continue
            # Extract target inside parentheses
            target_part = line.split('(')[-1].split(')')[0].strip().zfill(4)
            targets[f"Key {key_digit_part} Target"] = target_part

        if not targets:
            print(f"⚠️ No valid targets extracted from {file_path}")

        return targets

    except Exception as e:
        print(f"⚠️ Error extracting zoom menu targets from {file_path}: {e}")
        return {}

def build_ar_rows(corp_number: str, site_name: str, file_path: str) -> list[dict]:
    rows = []

    # Try to extract Zoom Menu targets
    extracted_targets = extract_zoom_menu_targets(file_path)

    # Spanish
    row = {
        "Action": "CREATE",
        "Name": f"{site_name} - SPANISH",
        "Site": site_name,
        "Extension": "0002",
        "Audio File": f"{site_name} SPANISH",
        "Timezone": "America/Chicago",
        "Phone Numbers": "",
        "Prompt Repeat": 3,
        "Prompt Language": "es-US",
    }

    for key, value in DEFAULT_SPANISH_KEYS.items():
        if key in ["No Entry Action", "No Entry Target"]:
            if key == "No Entry Target":
                row[key] = format_full_extension(corp_number, value[-3:])
            else:
                row[key] = value
        elif "Target" in key:
            if key in extracted_targets:
                target_val = extracted_targets[key]
                row[key] = format_full_extension(corp_number, target_val[-3:]) if target_val else ""
            else:
                row[key] = ""
            if row[key] == "":
                action_key = key.replace("Target", "Action")
                row[action_key] = ""
        else:
            row[key] = value
    rows.append(row)

    # English
    row = {
        "Action": "UPDATE",
        "Name": f"{site_name} - ENGLISH",
        "Site": site_name,
        "Extension": format_full_extension(corp_number, "001"),
        "Audio File": f"{site_name} ENGLISH",
        "Timezone": "America/Chicago",
        "Phone Numbers": f"{site_name} MAIN NUMBER",
        "Prompt Repeat": 3,
        "Prompt Language": "en-US",
    }

    # If "Jump to Spanish Day AA" is present, set Key 1 Action/Target accordingly for English keys only
    try:
        cf = pd.read_excel(file_path, sheet_name="CALL FLOW", header=None)
        menu_row = cf[cf.apply(lambda row: row.astype(str).str.contains("MENU SCRIPT", case=False).any(), axis=1)]
        if not menu_row.empty:
            row_idx = menu_row.index[0]
            menu_text = cf.iloc[row_idx, 2]
            if not pd.isna(menu_text):
                lines = str(menu_text).splitlines()
                if any("Jump to Spanish Day AA" in line for line in lines):
                    extracted_targets["Key 1 Action"] = "Auto Receptionist"
                    extracted_targets["Key 1 Target"] = "0002"
    except Exception:
        pass

    for key, value in DEFAULT_ENGLISH_KEYS.items():
        if key in ["No Entry Action", "No Entry Target"]:
            if key == "No Entry Target":
                row[key] = format_full_extension(corp_number, value[-3:])
            else:
                row[key] = value
        elif "Target" in key:
            if key in extracted_targets:
                target_val = extracted_targets[key]
                row[key] = format_full_extension(corp_number, target_val[-3:]) if target_val else ""
            else:
                row[key] = ""
            if row[key] == "":
                action_key = key.replace("Target", "Action")
                row[action_key] = ""
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
        all_rows.extend(build_ar_rows(site.corp_number, site_name, file_path))  # Use processed corp number and combined site name

    return pd.DataFrame(all_rows)

def write(dataframe: pd.DataFrame, writer: pd.ExcelWriter, sheet_name="Auto Receptionists"):
    dataframe.to_excel(writer, sheet_name=sheet_name, index=False)