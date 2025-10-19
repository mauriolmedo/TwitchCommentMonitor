import streamlit as st
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import requests
import os
import json
import pendulum
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
from dotenv import load_dotenv
import re

# Load environment variables from .env file
load_dotenv()

# Google Drive API setup
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def get_drive_service():
    creds = None
    token_path = 'token.pickle'
    # Load from secrets in Streamlit Cloud
    if 'STREAMLIT_CLOUD' in os.environ:
        try:
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
        except Exception as e:
            st.error(f"Error loading Google Drive credentials from secrets: {e}")

    # Load from token.pickle locally
    if not creds or not creds.valid:
        if os.path.exists(token_path):
            try:
                with open(token_path, 'rb') as token:
                    creds = pickle.load(token)
                print("Loaded token.pickle successfully")  # Console log
            except Exception as e:
                print(f"Error loading token.pickle: {e}")
                st.warning("Failed to load Google Drive credentials. Please re-authenticate.")

    # Refresh credentials if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
            print("Refreshed Google Drive token successfully")  # Console log
        except Exception as e:
            print(f"Error refreshing Google Drive token: {e}")
            st.warning("Failed to refresh Google Drive credentials. Please re-authenticate.")
            creds = None

    # Run OAuth flow if no valid credentials
    if not creds or not creds.valid:
        credentials_json = os.environ.get('GOOGLE_CREDENTIALS', '{}')
        if os.path.exists('credentials.json'):
            with open('credentials.json', 'r') as f:
                credentials_json = f.read()
        if credentials_json and credentials_json != '{}':
            try:
                flow = InstalledAppFlow.from_client_config(json.loads(credentials_json), SCOPES)
                creds = flow.run_local_server(port=0)  # Dynamic port
                with open(token_path, 'wb') as token:
                    pickle.dump(creds, token)
                print("Created new token.pickle after authorization")  # Console log
            except Exception as e:
                st.error(f"Failed to authenticate with Google Drive: {e}")
                return None
        else:
            st.error("No valid Google Drive credentials found. Ensure 'credentials.json' is present or GOOGLE_CREDENTIALS is set.")
            return None

    return build('drive', 'v3', credentials=creds)

def list_txt_in_folders(service, folder_ids):
    txt_files = {}
    for folder_id in folder_ids:
        try:
            results = service.files().list(
                q=f"'{folder_id}' in parents and mimeType='text/plain'",
                fields="files(id, name, modifiedTime)"
            ).execute()
            items = results.get('files', [])
            if not items:
                st.warning(f"No text files found in folder ID {folder_id}. Please check the folder contents.")
            else:
                print(f"Found {len(items)} text files in folder ID {folder_id}: {[item['name'] for item in items]}")  # Console log
            for item in items:
                txt_files[item['name']] = {'id': item['id'], 'modifiedTime': item['modifiedTime']}
        except Exception as e:
            st.warning(f"Error accessing folder {folder_id}: {e}")
    return txt_files

def download_txt_content(service, file_id):
    try:
        request = service.files().get_media(fileId=file_id)
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        content = file_content.getvalue().decode('utf-8')
        print(f"Downloaded file content (first 50 chars): {content[:50]}...")  # Console log
        return content
    except Exception as e:
        st.warning(f"Error downloading file {file_id}: {e}")
        return ""

# Streamlit configuration
st.set_page_config(
    layout="centered",
    page_title="Monitoreo de Canales",
    page_icon="favicon.png"  # Use favicon.png in the same directory
)

# CSS styles
st.markdown("""
    <style>
    .card {
        background-color: #1A1A1A;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 8px;
        box-shadow: 0 2px 6px rgba(255,255,255,0.1);
        border: 1px solid #FFFFFF;
        position: relative;
    }
    .card-header {
        display: flex;
        align-items: center;
        justify-content: flex-start;
        margin-bottom: 6px;
    }
    .card-title {
        font-size: 16px;
        font-weight: bold;
        color: #F5F5F5;
        margin-left: 4px;
    }
    .card-label {
        font-size: 12px;
        color: #F5F5F5;
        margin-bottom: 2px;
    }
    .card-value {
        font-size: 18px;
        font-weight: bold;
        color: #BB86FC;
        margin-bottom: 4px;
    }
    .card-time {
        font-size: 14px;
        color: #F5F5F5;
    }
    .recent-indicator {
        width: 8px;
        height: 8px;
        background-color: #00FF00;
        border-radius: 50%;
        display: inline-block;
        position: absolute;
        bottom: 6px;
        right: 6px;
    }
    .recent-label {
        font-size: 10px;
        color: #F5F5F5;
        position: absolute;
        bottom: 4px;
        right: 16px;
    }
    .live-indicator {
        color: #FF5555;
        font-weight: bold;
    }
    .offline-indicator {
        color: #BBBBBB;
    }
    .profile-pic {
        width: 28px;
        height: 28px;
        border-radius: 50%;
        object-fit: cover;
    }
    .status-container {
        display: flex;
        align-items: center;
        margin-left: 6px;
    }
    .status-label {
        font-size: 14px;
        color: #F5F5F5;
        margin-right: 2px;
    }
    .status-value {
        font-size: 14px;
        font-weight: bold;
        line-height: 1;
        margin-top: -2px;
        margin-bottom: 4px;
    }
    .viewers-label {
        font-size: 14px;
        color: #F5F5F5;
        margin-right: 0px;
    }
    .viewers-value {
        font-size: 14px;
        font-weight: bold;
        color: #BB86FC;
        margin-left: 0px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("")

# Auto-refresh every 5 seconds
st_autorefresh(interval=5000, key="refresh")

# Initialize last refresh time
if 'last_refresh_time' not in st.session_state:
    st.session_state.last_refresh_time = datetime.now()
st.session_state.last_refresh_time = datetime.now()

# Load Twitch credentials safely
def load_twitch_credentials():
    try:
        twitch_secrets = st.secrets.get('twitch', {})
    except Exception:
        twitch_secrets = {}
    client_id = os.environ.get('TWITCH_CLIENT_ID', twitch_secrets.get('client_id', ''))
    client_secret = os.environ.get('TWITCH_CLIENT_SECRET', twitch_secrets.get('client_secret', ''))
    return client_id, client_secret

TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET = load_twitch_credentials()

@st.cache_data(ttl=2700)
def get_twitch_token():
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        st.error("Twitch credentials not configured. Set TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET in .env or environment variables.")
        return None
    url = "https://id.twitch.tv/oauth2/token"
    data = {
        'client_id': TWITCH_CLIENT_ID,
        'client_secret': TWITCH_CLIENT_SECRET,
        'grant_type': 'client_credentials'
    }
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        return response.json().get('access_token')
    except requests.RequestException as e:
        st.error(f"Error authenticating with Twitch: {e}")
        return None

@st.cache_data(ttl=30)
def get_stream_info(channel_name):
    token = get_twitch_token()
    if not token:
        return False, "Error authenticating"
    url = "https://api.twitch.tv/helix/streams"
    headers = {'Client-Id': TWITCH_CLIENT_ID, 'Authorization': f'Bearer {token}'}
    params = {'user_login': channel_name.lower()}
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        streams = data.get('data', [])
        if streams:
            stream = streams[0]
            return stream['type'] == 'live', stream.get('viewer_count', 0)
        return False, 0
    except requests.RequestException as e:
        return False, f"Error querying stream: {e}"

@st.cache_data(ttl=3600)
def get_user_info(channel_name):
    token = get_twitch_token()
    if not token:
        return None
    url = "https://api.twitch.tv/helix/users"
    headers = {'Client-Id': TWITCH_CLIENT_ID, 'Authorization': f'Bearer {token}'}
    params = {'login': channel_name.lower()}
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        return data['data'][0]['profile_image_url'] if data['data'] else None
    except requests.RequestException as e:
        st.warning(f"Error fetching user info for {channel_name}: {e}")
        return None

@st.cache_data(ttl=60)
def load_all_stats(folder_ids, _cache_buster=None):
    try:
        service = get_drive_service()
        if not service:
            st.error("Failed to initialize Google Drive service")
            return {}
        txt_files = list_txt_in_folders(service, folder_ids)
        if not txt_files:
            st.warning("No text files found in the specified Google Drive folders. Please check the folder contents.")
        all_stats = {}
        for name, info in txt_files.items():
            try:
                content = download_txt_content(service, info['id'])
                stats = parse_twitch_stats(content)
                all_stats[name] = {
                    'rows_added': stats.get('rows_added', '0'),
                    'modified_time': info['modifiedTime']
                }
            except Exception as e:
                st.warning(f"Unable to load file {name}: {e}")
                all_stats[name] = {'rows_added': '0', 'modified_time': None}
        return all_stats
    except Exception as e:
        st.error(f"Error loading statistics: {e}")
        return {}

def parse_twitch_stats(content):
    stats = {'rows_added': '0'}
    if not content:
        st.warning("Empty file content")
        return stats
    try:
        for line in content.split('\n'):
            if line.startswith('Filas añadidas en las últimas 24 horas:'):
                stats['rows_added'] = line.split(':')[1].strip()
                print(f"Parsed rows_added: {stats['rows_added']} from 'Filas añadidas'")  # Console log
                return stats
        # Fallback: Try parsing "Total de filas en la base"
        match = re.search(r'Total de filas en la base\s*(?:de datos)?:\s*(\d+)', content, re.IGNORECASE)
        if match:
            stats['rows_added'] = match.group(1)
            print(f"Parsed rows_added: {stats['rows_added']} from 'Total de filas'")  # Console log
        else:
            st.warning(f"No valid comment data found in file content: {content[:50]}...")
    except IndexError:
        st.warning(f"Invalid file format for statistics: {content[:50]}...")
    return stats

def time_since_modified(modified_time):
    if not modified_time:
        return 'N/A'
    try:
        mod_time = pendulum.parse(modified_time)
        now = pendulum.now('UTC')
        diff = now - mod_time
        seconds = diff.total_seconds()
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}min"
        elif seconds < 86400:
            return f"{int(seconds // 3600)}h"
        else:
            return f"{int(seconds // 86400)}d"
    except (ValueError, TypeError):
        return "N/A"

def is_file_recent(modified_time):
    try:
        mod_time = pendulum.parse(modified_time)
        return (pendulum.now('UTC') - mod_time).total_seconds() < 300  # 5 minutes
    except (ValueError, TypeError):
        return False

# Calculate time since last refresh
current_time = datetime.now()
time_diff = (current_time - st.session_state.last_refresh_time).total_seconds()
time_display = f"{int(time_diff)}s" if time_diff < 60 else f"{int(time_diff // 60)}min"

# Configuration
folder_ids = json.loads(os.environ.get('FOLDER_IDS', '["1h_M91sLP2o4CIAV32qf8DAmh8kaNdy20"]'))
channels = ['mauri']

# Load stats with cache buster
cache_buster = str(datetime.now().timestamp())
with st.spinner("Cargando estadísticas..."):
    stats_data = load_all_stats(folder_ids, cache_buster)

# Render cards
for channel in channels:
    is_live, viewers = get_stream_info(channel)
    profile_image = get_user_info(channel) or "https://static-cdn.jtvnw.net/jtv_user_pictures/f301e0c2-9710-45c8-becb-eb42954bfa32-profile_image-70x70.png"
    # Try to get stats for mauri.txt or database_stats.txt
    stats = stats_data.get(f"{channel}.txt", stats_data.get('database_stats.txt', {'rows_added': '0', 'modified_time': None}))
    is_recent = is_file_recent(stats['modified_time'])
    live_status = "En vivo" if is_live else "Offline"
    live_class = "live-indicator" if is_live else "offline-indicator"
    viewers_display = viewers if isinstance(viewers, int) else viewers

    st.markdown(f"""
        <div class="card">
            <div class="card-header">
                <img src="{profile_image}" class="profile-pic">
                <div class="card-title">{channel.capitalize()}</div>
                <div class="status-container">
                    <div class="status-label"><span class="status-value {live_class}">{live_status}</span></div>
                    <br><div class="viewers-label"> :) Espectadores:<br></div>
                    <div class="viewers-value">. Hay {viewers_display}</div>
                </div>
            </div>
            {'' if not is_recent else f'<span class="recent-indicator"></span><span class="recent-label">{time_display}</span>'}
            <div class="card-label">Comentarios (24h)</div>
            <div class="card-value">{stats['rows_added']}</div>
            <div class="card-label">Ultimo comentario</div>
            <div class="card-time">Hace: {time_since_modified(stats['modified_time'])}</div>
        </div>
    """, unsafe_allow_html=True)
