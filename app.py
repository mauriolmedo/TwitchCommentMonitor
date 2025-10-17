import streamlit as st
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
from drive_reader import get_drive_service, list_txt_in_folders, download_txt_content

# Configuración para móvil
st.set_page_config(layout="centered", page_title="Mauri Stats", page_icon=":bar_chart:")

# Estilos CSS para tarjetas personalizadas
st.markdown("""
    <style>
    .card {
        background-color: #F5F5F5;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .card-header {
        display: flex;
        align-items: center;
        margin-bottom: 8px;
    }
    .card-title {
        font-size: 18px;
        font-weight: bold;
        color: #1A1A1A;
        margin-left: 8px;
    }
    .card-label {
        font-size: 14px;
        color: #666666;
        margin-bottom: 4px;
    }
    .card-value {
        font-size: 24px;
        font-weight: bold;
        color: #6200EA;
        margin-bottom: 8px;
    }
    .card-time {
        font-size: 16px;
        color: #333333;
    }
    .recent-indicator {
        width: 10px;
        height: 10px;
        background-color: #00FF00;
        border-radius: 50%;
        display: inline-block;
        margin-left: 8px;
    }
    .profile-pic {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        object-fit: cover;
    }
    </style>
""", unsafe_allow_html=True)

st.title("Mauri Stats")

# Auto-refresh cada 5 segundos
st_autorefresh(interval=5000, key="refresh")

@st.cache_data(ttl=5)
def load_all_stats(folder_ids):
    service = get_drive_service()
    txt_files = list_txt_in_folders(service, folder_ids)
    all_stats = {}
    for name, info in txt_files.items():
        content = download_txt_content(service, info['id'])
        stats = parse_twitch_stats(content)
        all_stats[name] = {
            'rows_added': stats.get('rows_added', '0'),
            'modified_time': info['modifiedTime']
        }
    return all_stats

def parse_twitch_stats(content):
    stats = {}
    for line in content.split('\n'):
        if line.startswith('Filas añadidas en las últimas 24 horas:'):
            stats['rows_added'] = line.split(':')[1].strip()
    return stats

def time_since_modified(modified_time):
    if not modified_time:
        return 'N/A'
    mod_time = datetime.strptime(modified_time, "%Y-%m-%dT%H:%M:%S.%fZ")
    now = datetime.utcnow()
    diff = now - mod_time
    seconds = diff.total_seconds()
    if seconds < 60:
        return f"{int(seconds)} segundos"
    elif seconds < 3600:
        return f"{int(seconds // 60)} minutos"
    elif seconds < 86400:
        return f"{int(seconds // 3600)} horas"
    else:
        return f"{int(seconds // 86400)} días"

# ID de la carpeta proporcionada
folder_ids = ['1dyiWAKVi7ewteVclbqoTFmyblnl6R9xI']
stats_data = load_all_stats(folder_ids)

# Mostrar tarjetas
for channel, stats in stats_data.items():
    is_recent = (datetime.utcnow() - datetime.strptime(stats['modified_time'], "%Y-%m-%dT%H:%M:%S.%fZ")).total_seconds() < 300
    st.markdown(f"""
        <div class="card">
            <div class="card-header">
                <img src="https://static-cdn.jtvnw.net/jtv_user_pictures/f301e0c2-9710-45c8-becb-eb42954bfa32-profile_image-70x70.png" class="profile-pic">
                <div class="card-title">Mauri{' <span class="recent-indicator"></span>' if is_recent else ''}</div>
            </div>
            <div class="card-label">Filas añadidas (24h)</div>
            <div class="card-value">{stats['rows_added']}</div>
            <div class="card-label">Última actualización</div>
            <div class="card-time">{time_since_modified(stats['modified_time'])}</div>
        </div>
    """, unsafe_allow_html=True)