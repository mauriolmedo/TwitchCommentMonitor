import io
import pickle
import os
import streamlit as st
import json
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def get_drive_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            credentials_json = (
                os.environ.get('GOOGLE_CREDENTIALS') or
                st.secrets.get('google_drive', {}).get('credentials', '{}')
            )
            flow = InstalledAppFlow.from_client_config(json.loads(credentials_json), SCOPES)
            try:
                # Intenta usar navegador local (ideal cuando corres el script en tu PC)
                creds = flow.run_local_server(port=0)
            except Exception:
                # Si no hay navegador disponible (por ejemplo, en Streamlit Cloud)
                creds = flow.run_console()
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
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
            txt_files[item['name']] = {
                'id': item['id'],
                'modifiedTime': item['modifiedTime']
            }
    return txt_files

def download_txt_content(service, file_id):
    try:
        request = service.files().get_media(fileId=file_id)
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        return file_content.getvalue().decode('utf-8')
    except Exception as e:
        st.error(f"Error al descargar el archivo: {e}")
        return None
