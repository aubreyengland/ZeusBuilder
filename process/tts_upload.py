import requests
import os

# use the Zoom assets library API to upload the generated TTS file.

#get the user ID from the .env file

def get_user_id_from_usernamee(): 
    """
    Retrieve the user ID from the Zoom API using the username.

    :return: User ID.
    """
    access_token = os.getenv("ZOOM_S2S_ACCESS_TOKEN")
    if not access_token:
        raise ValueError("Access token is not set in the environment variables.")
    url = "https://api.zoom.us/v2/users/me"
    
def retrieve_user_id(access_token: str) -> str:
    """
    Retrieve the user ID from the Zoom API.

    :param access_token: OAuth2 access token for authentication.
    :return: User ID.
    """
    url = "https://api.zoom.us/v2/users/me"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        user_data = response.json()
        return user_data["id"]
    else:
        raise Exception(f"Failed to retrieve user ID. Status code: {response.status_code}")
    
def load_tts_file_content(file_path: str) -> str:
    """
    Load the content of a TTS file.

    :param file_path: Path to the TTS file.
    :return: Content of the TTS file.
    """ 
    # file path is formated like outpit/CORP_XYZ_TTS_Prompts
    
    file_path = os.path.abspath(file_path)
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"TTS file not found at {file_path}")

    with open(file_path, "r", encoding="utf-8") as file:
        return file.read().strip()
    eng_tts_file_content = load_tts_file_content(os.path.join(file_path, f"CORP {corp_number}-ENGLISH.txt"))
    span_tts_file_content = load_tts_file_content(os.path.join(file_path, f"CORP {corp_number}-SPANISH.txt"))
    

def build_tts_payload(file_path: str, ) -> dict:
    """
    Build the payload for the TTS file upload.

    :param file_path: Path to the TTS file.
    :return: Payload dictionary.
    """
    file_name = os.path.basename(file_path)
    
    eng_payload = {
        "audio_name": file_name,
        "text": eng_tts_file_content,
        "file_size": os.path.getsize(file_path),
    } 
    esp_payload = {
        "audio_name": file_name,
        "text": span_tts_file_content,
        "file_size": os.path.getsize(file_path),
    }
    

def upload_tts_file(file_path: str, asset_id: str, access_token: str) -> None:
    """
    Upload a TTS file to the Zoom assets library.

    :param file_path: Path to the TTS file to upload.
    :param asset_id: The ID of the asset in the Zoom assets library.
    :param access_token: OAuth2 access token for authentication.
    """
    url = f"https://api.zoom.us/v2/asset/{asset_id}/upload"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    files = {"file": open(file_path, "rb")}

    response = requests.post(url, headers=headers, files=files)

    if response.status_code == 200:
        print(f"Successfully uploaded {file_path} to Zoom assets library.")
    else:
        print(f"Failed to upload {file_path}. Status code: {response.status_code}")
        print(f"Response: {response.text}")