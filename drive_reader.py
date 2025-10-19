import io
import os
import pickle
import streamlit as st
import json
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def get_drive_service():
    creds = None
    # Intenta cargar el token desde secrets en Streamlit Cloud
    if 'STREAMLIT_CLOUD' in os.environ:
        token_json = os.environ.get('GOOGLE_TOKEN', st.secrets.get('google_drive', {}).get('token', '{}'))
        if token_json and token_json != '{}':
            creds_dict = json.loads(token_json)
            creds = Credentials(
                token=creds_dict.get('token'),
                refresh_token=creds_dict.get('refresh_token'),
                token_uri=creds_dict.get('token_uri'),
                client_id=creds_dict.get('client_id'),
                client_secret=creds_dict.get('client_secret'),
                scopes=creds_dict.get('scopes')
            )
    # Para entorno local, usa token.pickle
    if not creds or not creds.valid:
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            credentials_json = os.environ.get('GOOGLE_CREDENTIALS', '{}')
            if os.path.exists('credentials.json'):
                with open('credentials.json', 'r') as f:
                    credentials_json = f.read()
            if credentials_json and credentials_json != '{}':
                flow = InstalledAppFlow.from_client_config(json.loads(credentials_json), SCOPES)
                creds = flow.run_local_server(port=8502)  # Usa puerto 8502
                with open('token.pickle', 'wb') as token:
                    pickle.dump(creds, token)
            else:
                raise ValueError("No se encontraron credenciales válidas. Asegúrate de que 'credentials.json' esté en el directorio.")
    return build('drive', 'v3', credentials=creds)

def list_txt_in_folders(service, folder_ids):
    txt_files = {}
    for folder_id in folder_ids:
        results = service.files().list(
            q=f"'{folder_id}' in parents and mimeType='text/plain'",
            fields="files(id, name, modifiedTime)"
        ).execute()
        items = results.get('files', [])
        for item in items:
            txt_files[item['name']] = {'id': item['id'], 'modifiedTime': item['modifiedTime']}
    return txt_files

def download_txt_content(service, file_id):
    request = service.files().get_media(fileId=file_id)
    file_content = io.BytesIO()
    downloader = MediaIoBaseDownload(file_content, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    return file_content.getvalue().decode('utf-8')
