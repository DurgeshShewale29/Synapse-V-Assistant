import streamlit as st
import requests, json, time, datetime, os
import pandas as pd
import urllib.parse
import re
from streamlit_mic_recorder import mic_recorder
from streamlit_geolocation import streamlit_geolocation
from geopy.geocoders import ArcGIS 
from geopy.distance import geodesic

# --- CONFIGURATION ---
BASE_URL = "https://your-backend-service-name.onrender.com"
BASE_URL = "https://synapse-v-assistant.onrender.com"
NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
WEATHER_API_KEY = st.secrets["WEATHER_API_KEY"]
HISTORY_FILE = "synapse_history.json"

st.set_page_config(page_title="Synapse-V Assistant", layout="wide", page_icon="🎙️")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #E0E0E0; }
    [data-testid="stSidebar"] { background-color: #161B22; border-right: 1px solid #30363D; }
    [data-testid="stChatMessage"] { background-color: #1c2128; border-radius: 15px; margin-bottom: 10px; border: 1px solid #30363D; }
    .stButton>button { border-radius: 8px; font-weight: 600; transition: all 0.3s ease; }
    .stButton>button:hover { border-color: #58a6ff; color: #58a6ff; transform: translateY(-1px); }
    h1, h2, h3 { font-family: 'Inter', sans-serif; font-weight: 700; letter-spacing: -0.5px; }
    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-thumb { background: #30363d; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

def check_backend():
    try:
        requests.get(f"{BASE_URL}/list_files", timeout=1)
        return True
    except: return False

india_data = {
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Nashik", "Aurangabad", "Thane"],
    "Karnataka": ["Bengaluru", "Mysore", "Hubballi", "Mangalore", "Belgaum"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Salem", "Trichy"],
    "Delhi": ["New Delhi", "North Delhi", "South Delhi", "West Delhi", "East Delhi"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar"],
    "Uttar Pradesh": ["Lucknow", "Kanpur", "Varanasi", "Agra", "Meerut", "Prayagraj"],
    "West Bengal": ["Kolkata", "Howrah", "Durgapur", "Siliguri", "Asansol"],
    "Telangana": ["Hyderabad", "Warangal", "Nizamabad", "Khammam"],
    "Kerala": ["Thiruvananthapuram", "Kochi", "Kozhikode", "Thrissur"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Kota", "Udaipur", "Bikaner"]
}

def load_persistent_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, dict) and "history" in data:
                    return data["history"], data.get("pinned", [])
                return data, []
        except: return {}, []
    return {}, []

def save_persistent_history(history, pinned):
    with open(HISTORY_FILE, "w") as f:
        json.dump({"history": history, "pinned": pinned}, f, indent=4)

if "chat_history" not in st.session_state or "pinned_chats" not in st.session_state:
    hist, pinned = load_persistent_history()
    st.session_state.chat_history = hist
    st.session_state.pinned_chats = pinned

if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = f"Chat {datetime.datetime.now().strftime('%d %b %I:%M %p')}"
if "chat_thread" not in st.session_state:
    st.session_state.chat_thread = []
if "show_camera" not in st.session_state: st.session_state.show_camera = False
if "show_file_uploader" not in st.session_state: st.session_state.show_file_uploader = False

@st.dialog("Rename Session")
def rename_dialog(old_name):
    new_name = st.text_input("Enter new session name", value=old_name)
    if st.button("Save Name", use_container_width=True):
        if new_name and new_name != old_name:
            st.session_state.chat_history[new_name] = st.session_state.chat_history.pop(old_name)
            if old_name in st.session_state.pinned_chats:
                idx = st.session_state.pinned_chats.index(old_name)
                st.session_state.pinned_chats[idx] = new_name
            if st.session_state.current_session_id == old_name:
                st.session_state.current_session_id = new_name
            save_persistent_history(st.session_state.chat_history, st.session_state.pinned_chats)
            st.rerun()

def get_geo_details(lat, lon):
    try:
        geolocator = ArcGIS()
        location = geolocator.reverse(f"{lat}, {lon}", timeout=10)
        addr = location.raw.get('address', {})
        city = addr.get('City') or addr.get('Subregion') or "Pune"
        state = addr.get('Region') or "Maharashtra"
        return city, state
    except: return "Pune", "Maharashtra"

def render_map_view(lat, lon):
    map_df = pd.DataFrame({'lat': [lat], 'lon': [lon]})
    st.sidebar.map(map_df, zoom=11, use_container_width=True)

def find_nearby_emergency(lat, lon, service_type="hospital"):
    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = f"""[out:json];(node["amenity"="{service_type}"](around:10000, {lat}, {lon});way["amenity"="{service_type}"](around:10000, {lat}, {lon}););out center;"""
    try:
        res = requests.get(overpass_url, params={'data': overpass_query}, timeout=10).json()
        results = []
        for e in res.get('elements', []):
            e_lat, e_lon = e.get('lat') or e.get('center', {}).get('lat'), e.get('lon') or e.get('center', {}).get('lon')
            if e_lat and e_lon:
                name = e.get('tags', {}).get('name', "Unnamed Facility")
                dist_km = geodesic((lat, lon), (e_lat, e_lon)).km
                results.append({"name": name, "distance": dist_km, "lat": e_lat, "lon": e_lon})
        return sorted(results, key=lambda x: x['distance'])[:3]
    except: return []

def render_emergency_ui(lat, lon):
    st.error("🆘 Emergency Assistance")
    def display_results(results):
        if not results: st.write("No facilities found.")
        for r in results:
            dist_str = f"{r['distance']*1000:.0f}m" if r['distance'] < 1 else f"{r['distance']:.2f}km"
            st.markdown(f"• **{r['name']}** ({dist_str})  \n[➔ Navigate](https://www.google.com/maps?q={r['lat']},{r['lon']})")
    c1, c2 = st.columns(2)
    if c1.button("🏥 Hospitals", key="sos_h", use_container_width=True): display_results(find_nearby_emergency(lat, lon, "hospital"))
    if c2.button("🚔 Police", key="sos_p", use_container_width=True): display_results(find_nearby_emergency(lat, lon, "police"))

def render_local_cards(location):
    st.markdown(f"### 🌟 Insights for {location}")
    # Weather Card
    w_url = f"http://api.openweathermap.org/data/2.5/weather?q={location},IN&appid={WEATHER_API_KEY}&units=metric"
    try:
        w_res = requests.get(w_url, timeout=5).json()
        if w_res.get("main"):
            with st.container(border=True):
                col1, col2 = st.columns([1, 2])
                icon = w_res['weather'][0]['icon']
                col1.image(f"http://openweathermap.org/img/wn/{icon}@2x.png")
                col2.metric("Temp", f"{w_res['main']['temp']}°C", w_res['weather'][0]['description'].title())
    except: st.warning("Weather unavailable.")

    # --- UPDATED TIMES OF INDIA NEWS LOGIC ---
    # Using multiple domains and sorting by date to ensure recent Pune news is found
    n_url = (
        f"https://newsapi.org/v2/everything?"
        f"q={location}&"
        f"domains=indiatimes.com,timesofindia.indiatimes.com&"
        f"language=en&"
        f"sortBy=publishedAt&"
        f"pageSize=5&"
        f"apiKey={NEWS_API_KEY}"
    )
    try:
        n_res = requests.get(n_url, timeout=5).json()
        articles = n_res.get("articles", [])
        
        # Fallback: Search for Pune News generally if strict domain filter fails
        if not articles:
            fallback_url = f"https://newsapi.org/v2/everything?q={location}+news&sortBy=publishedAt&apiKey={NEWS_API_KEY}&pageSize=10&language=en"
            fallback_res = requests.get(fallback_url, timeout=5).json()
            # Filter results that are from Times of India sources
            articles = [a for a in fallback_res.get("articles", []) if "Times of India" in a['source']['name'] or "TOI" in a['title']][:5]

        if articles:
            with st.container(border=True):
                st.subheader("📰 Times of India")
                st.caption(f"Top updates for {location}")
                for art in articles:
                    if art['title'] and art['url']:
                        st.markdown(f"• **[{art['title']}]({art['url']})**")
        else:
            st.info(f"No specific TOI news for {location} right now.")
    except: st.warning("News service unreachable.")

def run_streaming_chat(user_text, lang, fast, noise, image_file, doc_file, low_light, persona, location, auto_speak, voice_name):
    st.session_state.chat_thread.append({"role": "user", "content": user_text})
    with st.chat_message("assistant"):
        resp_container = st.empty()
        full_txt = ""
        hist = [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat_thread[-6:]]
        files = {}
        if image_file: files["image"] = (image_file.name, image_file.getvalue(), "image/jpeg")
        if doc_file: files["document"] = (doc_file.name, doc_file.getvalue(), "application/octet-stream")
        
        data = {"text": user_text, "lang": lang, "history": json.dumps(hist), "fast": str(fast).lower(), "low_light": str(low_light).lower(), "persona": persona, "location": location}
        try:
            with requests.post(f"{BASE_URL}/stream_process", data=data, files=files if files else None, stream=True) as r:
                for chunk in r.iter_content(None, decode_unicode=True):
                    full_txt += chunk
                    resp_container.markdown(full_txt + "▌")
            resp_container.markdown(full_txt)
            st.session_state.chat_thread.append({"role": "assistant", "content": full_txt})
            st.session_state.chat_history[st.session_state.current_session_id] = st.session_state.chat_thread
            save_persistent_history(st.session_state.chat_history, st.session_state.pinned_chats)
            
            if auto_speak:
                v_res = requests.post(f"{BASE_URL}/get_audio", data={"text": full_txt, "lang": lang, "voice": voice_name}).json()
                if v_res.get("audio_url"):
                    st.audio(f"{BASE_URL}/listen/{v_res['audio_url']}", autoplay=True)
        except: st.error("AI Backend Offline.")

# --- SIDEBAR ---
with st.sidebar:
    st.title("📂 Your Chat")
    if st.button("➕ New Session", use_container_width=True, type="primary"):
        st.session_state.chat_thread = []
        st.session_state.current_session_id = f"Chat {datetime.datetime.now().strftime('%d %b %I:%M %p')}"
        st.rerun()

    st.divider()
    search_q = st.text_input("🔍 Search History", placeholder="Find a chat...")
    all_sessions = list(st.session_state.chat_history.keys())[::-1]
    if search_q: all_sessions = [s for s in all_sessions if search_q.lower() in s.lower()]

    pinned = [s for s in all_sessions if s in st.session_state.pinned_chats]
    unpinned = [s for s in all_sessions if s not in st.session_state.pinned_chats]

    def render_chat_item(sid, is_pinned=False):
        col_btn, col_menu = st.columns([5, 1])
        with col_btn:
            is_active = (st.session_state.current_session_id == sid)
            label = f"📌 {sid}" if is_pinned else f"💬 {sid}"
            if st.button(label, key=f"btn_{sid}", use_container_width=True, type="secondary" if not is_active else "primary"):
                st.session_state.chat_thread = st.session_state.chat_history[sid]
                st.session_state.current_session_id = sid
                st.rerun()
        with col_menu:
            with st.popover("⋮"):
                if st.button("📍 Unpin" if is_pinned else "📌 Pin Chat", key=f"p_{sid}", use_container_width=True):
                    if is_pinned: st.session_state.pinned_chats.remove(sid)
                    else: st.session_state.pinned_chats.append(sid)
                    save_persistent_history(st.session_state.chat_history, st.session_state.pinned_chats)
                    st.rerun()
                if st.button("✏️ Rename", key=f"ren_{sid}", use_container_width=True): rename_dialog(sid)
                chat_data = json.dumps(st.session_state.chat_history[sid], indent=2)
                st.download_button("📥 Download", data=chat_data, file_name=f"{sid}.json", key=f"dl_{sid}", use_container_width=True)
                if st.button("🗑️ Delete", key=f"del_{sid}", use_container_width=True):
                    del st.session_state.chat_history[sid]
                    save_persistent_history(st.session_state.chat_history, st.session_state.pinned_chats)
                    st.rerun()

    if pinned:
        st.caption("PINNED")
        for sid in pinned: render_chat_item(sid, is_pinned=True)
    if unpinned:
        st.caption("RECENT")
        for sid in unpinned: render_chat_item(sid, is_pinned=False)

    st.divider()
    st.subheader("📁 Server File Explorer")
    if check_backend():
        try:
            f_res = requests.get(f"{BASE_URL}/list_files").json()
            
            with st.expander("🖼️ Images", expanded=False):
                imgs = f_res.get('images', [])
                for f in imgs:
                    c_info, c_del = st.columns([4, 1])
                    c_info.caption(f"**{f['name']}** ({f['size']})")
                    if c_del.button("🗑️", key=f"del_img_{f['name']}"):
                        requests.delete(f"{BASE_URL}/delete_file/{f['name']}")
                        st.rerun()

            with st.expander("📄 Documents", expanded=True):
                docs = f_res.get('documents', [])
                for f in docs:
                    c_info, c_del = st.columns([4, 1])
                    c_info.caption(f"**{f['name']}** ({f['size']})")
                    if c_del.button("🗑️", key=f"del_doc_{f['name']}"):
                        requests.delete(f"{BASE_URL}/delete_file/{f['name']}")
                        st.rerun()
        except: st.caption("Explorer issue.")

    st.header("⚙️ Settings")
    selected_persona = st.selectbox("AI Personality", ["Default", "Professional", "Friendly", "Candid", "Quirky", "Nerdy"])
    voice_choice = st.selectbox("Assistant Voice", ["Zira", "David", "Default"])
    auto_speak = st.toggle("🔊 Auto-Speak Response", value=True)
    auto_loc = st.toggle("Auto-Detect (GPS)", value=False)
    
    final_location = "Unknown"
    
    if auto_loc:
        pos = streamlit_geolocation()
        if pos.get("latitude"):
            lat, lon = pos["latitude"], pos["longitude"]
            city, state = get_geo_details(lat, lon)
            final_location = city
            st.success(f"📍 {final_location}")
            render_map_view(lat, lon)
            render_emergency_ui(lat, lon)
    else:
        s_state = st.selectbox("Select State", ["Choose State"] + sorted(list(india_data.keys())))
        if s_state != "Choose State":
            s_city = st.selectbox(f"City", ["📍 State-wide"] + sorted(india_data[s_state]))
            final_location = s_city if s_city != "📍 State-wide" else s_state
            
            if final_location != "Unknown":
                try:
                    geolocator = ArcGIS()
                    loc_obj = geolocator.geocode(f"{final_location}, {s_state}, India")
                    if loc_obj:
                        render_map_view(loc_obj.latitude, loc_obj.longitude)
                except: pass

    if final_location != "Unknown": render_local_cards(final_location)

# --- MAIN UI ---
if not check_backend():
    st.error("⚠️ **Backend Offline**")
    st.stop()

st.title("🎙️ Synapse-V")
lang_code = "hi" if st.radio("Language:", ["English", "Hindi"], horizontal=True, label_visibility="collapsed") == "Hindi" else "en"
c1, c2, c3 = st.columns(3)
fast, noise, low = c1.toggle("⚡ Fast"), c2.toggle("🔇 Noise"), c3.toggle("💡 Light")

for m in st.session_state.chat_thread:
    with st.chat_message(m["role"]): st.write(m["content"])

captured_image, uploaded_action_file = None, None
if st.session_state.show_camera:
    captured_image = st.camera_input("Snapshot")
if st.session_state.show_file_uploader:
    uploaded_action_file = st.file_uploader("Upload file", type=["png", "jpg", "jpeg", "webp", "txt", "pdf", "docx", "csv", "xlsx", "zip", "7z", "py", "java", "js"])

st.divider()
b1, b2, b3, _ = st.columns([1, 1, 4, 4])
with b1:
    if st.button("📷", use_container_width=True): 
        st.session_state.show_camera = not st.session_state.show_camera
        st.rerun()
with b2:
    if st.button("➕", use_container_width=True):
        st.session_state.show_file_uploader = not st.session_state.show_file_uploader
        st.rerun()
with b3:
    audio_data = mic_recorder(start_prompt="🎤 Record", stop_prompt="🛑 Stop", key='recorder')

if prompt := st.chat_input("Ask Synapse-V..."):
    img_to_send = captured_image
    doc_to_send = uploaded_action_file
    
    if uploaded_action_file:
        ext = os.path.splitext(uploaded_action_file.name)[1].lower()
        if ext in ['.png', '.jpg', '.jpeg', '.webp']:
            img_to_send = uploaded_action_file
            doc_to_send = None 
            
    run_streaming_chat(prompt, lang_code, fast, noise, img_to_send, doc_to_send, low, selected_persona, final_location, auto_speak, voice_choice)

if audio_data and st.button("🚀 Send Voice Command"):
    try:
        v_res = requests.post(f"{BASE_URL}/process_voice", files={"audio": audio_data['bytes']}, data={"lang": lang_code, "noise": str(noise).lower()}).json()
        if v_res.get("text"):
            run_streaming_chat(v_res["text"], lang_code, fast, noise, captured_image, uploaded_action_file, low, selected_persona, final_location, auto_speak, voice_choice)
    except: st.error("Voice failed.")
