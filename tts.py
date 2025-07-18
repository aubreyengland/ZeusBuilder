#!/usr/bin/env python3
import os
import requests
import pandas as pd
import argparse
from dotenv import load_dotenv
from base64 import b64encode

# -----------------------------
# LOAD ENV VARS
# -----------------------------
load_dotenv()

CLIENT_ID = os.getenv("ZOOM_CLIENT_ID")
CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET")
ACCOUNT_ID = os.getenv("ZOOM_ACCOUNT_ID")
USER_EMAIL = os.getenv("USER_EMAIL")
ZOOM_BASE_URL = "https://api.zoom.us/v2"
INPUT_FOLDER = "tts_input"

# -----------------------------
# GET ACCESS TOKEN (S2S)
# -----------------------------
def get_access_token():
    url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={ACCOUNT_ID}"
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_auth = b64encode(auth_str.encode()).decode()

    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(url, headers=headers)

    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception(f"Failed to get access token: {response.status_code} {response.text}")

# -----------------------------
# RESOLVE USER ID
# -----------------------------
def resolve_user_id(token, email):
    url = f"{ZOOM_BASE_URL}/users/{email}"
    headers = {
        "Authorization": f"Bearer {token}",
    }
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()["id"]
    else:
        raise Exception(f"Failed to resolve user ID for {email}: {response.status_code} {response.text}")

# -----------------------------
# VERIFY USER IS ZOOM PHONE USER
# -----------------------------
def verify_user_is_phone_user(token, user_id):
    url = f"{ZOOM_BASE_URL}/phone/users/{user_id}"
    headers = {
        "Authorization": f"Bearer {token}",
    }
    print(f"🔍 Verifying Zoom Phone status for user_id: {user_id}...")
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        print("User is a Zoom Phone user.")
    elif response.status_code == 404:
        print(f"User {user_id} is not a Zoom Phone user or does not exist.")
        exit(1)
    else:
        print(f"Failed to verify Zoom Phone status: {response.status_code} {response.text}")
        exit(1)

# -----------------------------
# EXPORT AUDIO PROMPTS
# -----------------------------
def list_audio_prompts(token, user_id):
    url = f"{ZOOM_BASE_URL}/phone/users/{user_id}/audios"
    headers = {
        "Authorization": f"Bearer {token}",
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Failed to fetch audio prompts: {response.status_code} {response.text}")
        return []

    data = response.json()
    audio_prompts = data.get("audios", [])
    return audio_prompts

def export_audio_prompts_to_excel(token, output_file, user_id):
    prompts = list_audio_prompts(token, user_id)
    if not prompts:
        print("No audio prompts found or failed to retrieve.")
        return

    records = []
    for prompt in prompts:
        print(prompt)
        records.append({
            "Audio Name": prompt.get("audio_name"),
            "Audio ID": prompt.get("id"),
        })

    df = pd.DataFrame(records)
    df.to_excel(output_file, index=False)
    print(f"Audio prompts exported to {output_file}")

# -----------------------------
# UPLOAD AUDIO PROMPTS
# -----------------------------
def upload_audio_prompt(token, user_id, audio_name, text, voice_language, voice_accent):
    url = f"{ZOOM_BASE_URL}/phone/users/{user_id}/audios"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "audio_name": audio_name,
        "text": text,
        "voice_language": voice_language,
        "voice_accent": voice_accent,
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 201:
        resp_json = response.json()
        audio_id = resp_json.get("id")
        print(f"Uploaded: {audio_name} (Audio ID: {audio_id})")
        append_to_excel_log(audio_name, audio_id, "Success")
        return resp_json
    else:
        print(f"❌ Failed to upload '{audio_name}': {response.status_code} {response.text}")
        append_to_excel_log(audio_name, "", f"Failed: {response.status_code}")
        return None

def append_to_excel_log(audio_name, audio_id, status):
    log_file = "upload_log.xlsx"
    record = {
        "Audio Name": audio_name,
        "Audio ID": audio_id,
        "Status": status
    }
    if os.path.exists(log_file):
        df_existing = pd.read_excel(log_file)
        df_new = pd.DataFrame([record])
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_combined = pd.DataFrame([record])
    df_combined.to_excel(log_file, index=False)

def process_folder_and_upload(token, folder_path, user_id):
    for filename in os.listdir(folder_path):
        if not filename.lower().endswith(".txt"):
            continue

        file_path = os.path.join(folder_path, filename)

        if "ENGLISH" in filename.upper():
            voice_language = "en-US"
            voice_accent = "Danielle-Female"
        elif "SPANISH" in filename.upper():
            voice_language = "es-US"
            voice_accent = "Lupe-Female"
        else:
            print(f"Skipping file (unknown language): {filename}")
            continue

        with open(file_path, "r", encoding="utf-8") as f:
            text_content = f.read().strip()

        audio_name = os.path.splitext(filename)[0]
        upload_audio_prompt(token, user_id, audio_name, text_content, voice_language, voice_accent)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zoom Audio Prompts Utility with S2S Auth")
    parser.add_argument("--upload", action="store_true", help="Upload audio prompts from input folder")
    parser.add_argument("--export", metavar="OUTPUT_FILE", help="Export audio prompts to Excel file")

    args = parser.parse_args()

    try:
        token = get_access_token()
    except Exception as e:
        print(e)
        exit(1)

    if USER_EMAIL:
        try:
            user_id = resolve_user_id(token, USER_EMAIL)
        except Exception as e:
            print(e)
            print("Could not resolve user ID from email.")
            exit(1)
    else:
        print("USER_EMAIL environment variable not set.")
        exit(1)

    verify_user_is_phone_user(token, user_id)

    if args.upload:
        print("🚀 Uploading audio prompts...")
        process_folder_and_upload(token, INPUT_FOLDER, user_id)

    if args.export:
        output_file = args.export
        print(f"📄 Exporting audio prompts to {output_file}...")
        export_audio_prompts_to_excel(token, output_file, user_id)

    if not args.upload and not args.export:
        print("Please specify --upload or --export <filename.xlsx>")