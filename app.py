import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
import cloudinary.api
import cloudinary.utils
import hashlib
import requests
import io
import json
import time
from datetime import datetime, timedelta

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="Web Monitoring IC Bali", 
    layout="wide", 
    page_icon="🏢"
)

# --- 2. KONFIGURASI GLOBAL ---
USER_DB_PATH = "Config/users_area.json"       
LOG_DB_PATH = "Config/activity_log_area.json" 

# --- 3. CSS & TEMA ---
def atur_tema():
    if 'current_theme' not in st.session_state:
        st.session_state['current_theme'] = "Dark" 

    st.markdown("""
        <style>
            [data-testid="stToolbar"] {visibility: hidden; display: none !important;}
            [data-testid="stDecoration"] {visibility: hidden; display: none !important;}
            footer {visibility: hidden; display: none;}
            .main .block-container {padding-top: 2rem;}
            [data-testid="stSidebarCollapsedControl"] {display: none;}
        </style>
    """, unsafe_allow_html=True)

    tema = st.session_state['current_theme']
    
    if tema == "Dark":
        st.markdown("""
        <style>
            .stApp { background-color: #0E1117; color: #FFFFFF; }
            h1, h2, h3, h4, h5, h6, p, span, div, label, .stMarkdown { color: #FFFFFF !important; }
            div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {
                background-color: #FFFFFF !important; border: 1px solid #ccc !important;
            }
            div[data-baseweb="select"] span { color: #000000 !important; -webkit-text-fill-color: #000000 !important; }
            div[data-baseweb="input"] input { color: #000000 !important; -webkit-text-fill-color: #000000 !important; caret-color: #000 !important; }
            ul[data-baseweb="menu"] { background-color: #FFFFFF !important; }
            li[role="option"] span { color: #000000 !important; }
            .stRadio label { color: #FFFFFF !important; }
            .stDataFrame { filter: invert(0); }
        </style>
        """, unsafe_allow_html=True)
    elif tema == "Light":
        st.markdown("""
        <style>
            .stApp {background-color: #FFFFFF; color: #000000;}
            h1, h2, h3, h4, h5, h6, p, span, div, label, .stMarkdown {color: #000000 !important;}
        </style>
        """, unsafe_allow_html=True)

terapkan_css = atur_tema
terapkan_css()

# --- 4. CONFIG DATA ---
ADMIN_CONFIG = {
    "AREA_INTRANSIT": {"username": "admin_rep", "password": "123456", "folder": "Area/Intransit", "label": "Area - Intransit/Proforma"},
    "AREA_NKL": {"username": "admin_nkl", "password": "123456", "folder": "Area/NKL", "label": "Area - NKL"},
    "AREA_RUSAK": {"username": "admin_rusak", "password": "123456", "folder": "Area/BarangRusak", "label": "Area - Barang Rusak"},
    "INTERNAL_REP": {"username": "admin_rep", "password": "123456", "folder": "InternalIC/Reporting", "label": "Internal IC - Reporting"},
    "INTERNAL_NKL": {"username": "admin_nkl", "password": "123456", "folder": "InternalIC/NKL", "label": "Internal IC - NKL"},
    "INTERNAL_RUSAK": {"username": "admin_rusak", "password": "123456", "folder": "InternalIC/BarangRusak", "label": "Internal IC - Barang Rusak"},
    "DC_DATA": {"username": "admin_dc", "password": "123456", "folder": "DC/General", "label": "DC - Data Utama"}
}

DATA_CONTACT = {
    "AREA_NKL": [("Putu IC", "087850110155"), ("Priyadi IC", "087761390987")],
    "AREA_INTRANSIT": [("Muklis IC", "081934327289"), ("Proforma - Ari IC", "081353446516"), ("NRB - Yani IC", "087760346299"), ("BPB/TAT - Tulasi IC", "081805347302")],
    "AREA_RUSAK": [("Putu IC", "087850110155"), ("Dwi IC", "083114444424"), ("Gean IC", "087725860048")]
}

VIEWER_CREDENTIALS = {
    "INTERNAL_IC": {"user": "ic_bli", "pass": "123456"},
    "DC": {"user": "ic_dc", "pass": "123456"}
}

# --- 5. SYSTEM FUNCTIONS ---
def init_cloudinary():
    if "cloudinary" not in st.secrets:
        st.error("⚠️ Kunci Cloudinary belum dipasang!")
        st.stop()
    cloudinary.config(
        cloud_name=st.secrets["cloudinary"]["cloud_name"],
        api_key=st.secrets["cloudinary"]["api_key"],
        api_secret=st.secrets["cloudinary"]["api_secret"],
        secure=True
    )

@st.cache_data(ttl=600, show_spinner=False) 
def get_all_files_cached():
    try:
        raw = cloudinary.api.resources(resource_type="raw", type="upload", max_results=500)
        return raw.get('resources', [])
    except:
        return []

def upload_file(file_upload, folder_path):
    public_id_path = f"{folder_path}/{file_upload.name}"
    res = cloudinary.uploader.upload(file_upload, resource_type="raw", public_id=public_id_path, overwrite=True)
    return res

def upload_image_error(image_file):
    res = cloudinary.uploader.upload(image_file, folder="ReportError", resource_type="image")
    return res

def hapus_file(public_id):
    try:
        cloudinary.api.delete_resources([public_id], resource_type="raw", type="upload")
        return True
    except:
        return False

# --- FUNGSI DATABASE (SOLUSI FRESH DATA) ---

def get_json_fresh(public_id):
    """
    Mengambil file JSON (User/Log) dengan memaksa Cloudinary memberikan versi terbaru.
    Menghindari Cache yang membuat data telat update.
    """
    try:
        # Minta detail resource via API untuk dapat URL Ber-versi (v1234...)
        resource = cloudinary.api.resource(public_id, resource_type="raw")
        url = resource.get('secure_url')
        
        if url:
            # Tambahkan timestamp random agar request HTTP benar-benar baru
            url_no_cache = f"{url}?t={int(time.time())}"
            resp = requests.get(url_no_cache)
            if resp.status_code == 200:
                return resp.json()
        return {}
    except:
        # Jika file belum ada
        return {}

def upload_json_to_cloud(data_dict, public_id):
    json_data = json.dumps(data_dict)
    cloudinary.uploader.upload(
        io.BytesIO(json_data.encode('utf-8')), 
        resource_type="raw", 
        public_id=public_id,
        overwrite=True
    )

def catat_login_activity(username):
    """Mencatat login dengan aman (Download Fresh -> Update -> Upload)"""
    try:
        # 1. Download Log Paling Baru (Anti-Cache)
        log_data = get_json_fresh(LOG_DB_PATH)
        
        # 2. Update Data
        now = datetime.utcnow() + timedelta(hours=8) # WITA
        tanggal_str = now.strftime("%Y-%m-%d")
        
        if tanggal_str not in log_data:
            log_data[tanggal_str] = {}
        
        if username not in log_data[tanggal_str]:
            log_data[tanggal_str][username] = 0
            
        log_data[tanggal_str][username] += 1
        
        # 3. Upload Balik
        upload_json_to_cloud(log_data, LOG_DB_PATH)
    except Exception as e:
        print(f"Gagal mencatat log: {e}")

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# --- EXCEL FUNCTIONS ---
@st.cache_data(ttl=600, show_spinner=False)
def load_excel_data(url, sheet_name, header_row, force_text=False):
    try:
        response = requests.get(url)
        file_content = io.BytesIO(response.content)
        row_idx = header_row - 1 if header_row > 0 else 0
        if force_text:
            df = pd.read_excel(file_content, sheet_name=sheet_name, header=row_idx, dtype=str).fillna("")
        else:
            df = pd.read_excel(file_content, sheet_name=sheet_name, header=row_idx)
        df.columns = df.columns.astype(str)
        return df
    except:
        return None

@st.cache_data(ttl=600, show_spinner=False)
def get_sheet_names(url):
    try:
        response = requests.get(url)
        return pd.ExcelFile(io.BytesIO(response.content)).sheet_names
    except:
        return []

def format_ribuan_indo(nilai):
    try:
        if float(nilai) % 1 != 0:
            val = "{:,.2f}".format(float(nilai)) 
        else:
            val = "{:,.0f}".format(float(nilai))
        translation = val.maketrans({",": ".", ".": ","})
        return val.translate(translation)
    except:
        return nilai

# --- UI COMPONENTS ---
def tampilkan_kontak(divisi_key):
    if not divisi_key: return
    kontak = DATA_CONTACT.get(divisi_key, [])
    if kontak:
        judul = divisi_key.replace("AREA_", "Divisi ").replace("_", " ")
        with st.expander(f"📞 Contact Person (CP) - {judul}"):
            cols = st.columns(4)
            for i, (nama, telp) in enumerate(kontak):
                wa = "62" + telp[1:] if telp.startswith("0") else telp
                cols[i%4].info(f"**{nama}**\n[{telp}](https://wa.me/{wa})")

def proses_tampilkan_excel(url, key_unik):
    sheets = get_sheet_names(url)
    if sheets:
        c1, c2 = st.columns(2)
        sh = c1.selectbox("Sheet:", sheets, key=f"sh_{key_unik}")
        hd = c2.number_input("Header:", 1, key=f"hd_{key_unik}")
        c3, c4 = st.columns([2, 1])
        src = c3.text_input("Cari:", key=f"src_{key_unik}")
        fmt = c4.checkbox("Jaga Semua Teks (No HP/NIK)", key=f"fmt_{key_unik}")
        
        with st.spinner("Loading Data..."): 
            df_raw = load_excel_data(url, sh, hd, fmt)
        
        if df_raw is not None:
            if src:
                try:
                    mask = df_raw.astype(str).apply(lambda x: x.str.contains(src, case=False, na=False)).any(axis=1)
                    df_raw = df_raw[mask]
                except: pass

            df_display = df_raw.copy()

            if not fmt:
                num_cols = df_display.select_dtypes(include=['float64', 'int64']).columns.tolist()
                kw_raw_code = ['prdcd', 'plu', 'barcode', 'kode', 'id', 'nik', 'no', 'nomor']

                for col in num_cols:
                    try:
                        col_str = str(col).lower()
                        if any(k in col_str for k in kw_raw_code):
                            df_display[col] = df_display[col].astype(str).str.replace(r'\.0$', '', regex=True)
                        elif pd.api.types.is_numeric_dtype(df_display[col]):
                            df_display[col] = df_display[col].apply(format_ribuan_indo)
                    except: continue

            st.write("")
            with st.expander("📏 Pengaturan Tampilan Tabel"):
                col_fz, col_mode, col_h = st.columns(3)
                with col_fz:
                    pilihan_kolom = ["Tidak Ada"] + df_display.columns.tolist()
                    freeze_col = st.selectbox("❄️ Freeze Kolom Kiri:", pilihan_kolom, key=f"fz_{key_unik}")
                with col_mode:
                    st.write("↔️ Mode Lebar")
                    use_full_width = st.checkbox("Fit Screen", value=False, key=f"fw_{key_unik}")
                with col_h:
                    table_height = st.slider("↕️ Tinggi (px):", 200, 1000, 500, 50, key=f"th_{key_unik}")
            
            if freeze_col != "Tidak Ada":
                df_display = df_display.set_index(freeze_col)

            st.dataframe(df_display, use_container_width=use_full_width, height=table_height)
            
            csv = df_raw.to_csv(index=False).encode('utf-8')
            col_info, col_dl = st.columns([3, 1])
            with col_info: st.caption(f"Total: {len(df_raw)} Baris")
            with col_dl:
                st.download_button("📥 Download CSV", csv, f"Data_Export_{sh}.csv", "text/csv", key=f"dl_{key_unik}")
        else: st.warning("⚠️ Gagal membaca data. Cek Header.")

def tampilkan_viewer(judul_tab, folder_target, semua_files, kode_kontak=None):
    tampilkan_kontak(kode_kontak)
    prefix = folder_target + "/"
    files_filtered = [f for f in semua_files if f['public_id'].startswith(prefix) and f['public_id'].endswith('.xlsx')]
    
    if not files_filtered:
        st.info(f"📭 Data Kosong: {folder_target}")
        return

    dict_files = {f['public_id'].replace(prefix, ""): f['secure_url'] for f in files_filtered}
    unik = f"std_{folder_target}"
    pilih = st.selectbox(f"Pilih File {judul_tab}:", list(dict_files.keys()), key=f"sel_{unik}")
    if pilih: proses_tampilkan_excel(dict_files[pilih], unik)

def tampilkan_viewer_area_rusak(folder_target, semua_files, kode_kontak=None):
    tampilkan_kontak(kode_kontak)
    st.markdown("### ⚠️ Area - Barang Rusak")
    kat = st.radio("Filter:", ["Semua Data", "Say Bread", "Mr Bread", "Fried Chicken", "Onigiri", "DRY"], horizontal=True)
    st.divider()

    prefix = folder_target + "/"
    files_in = [f for f in semua_files if f['public_id'].startswith(prefix) and f['public_id'].endswith('.xlsx')]
    
    if kat == "Semua Data": ff = files_in
    elif kat == "Say Bread": ff = [f for f in files_in if "say bread" in f['public_id'].lower()]
    elif kat == "Mr Bread": ff = [f for f in files_in if "mr bread" in f['public_id'].lower()]
    elif kat == "Fried Chicken": ff = [f for f in files_in if "fried chicken" in f['public_id'].lower()]
    elif kat == "Onigiri": ff = [f for f in files_in if "onigiri" in f['public_id'].lower()]
    elif kat == "DRY": ff = [f for f in files_in if "dry" in f['public_id'].lower()]
    else: ff = []

    if not ff:
        st.warning(f"File '{kat}' tidak ditemukan.")
        return

    dict_files = {f['public_id'].replace(prefix, ""): f['secure_url'] for f in ff}
    unik = "area_rusak_special"
    pilih = st.selectbox(f"Pilih File ({kat}):", list(dict_files.keys()), key=f"sel_{unik}")
    if pilih: proses_tampilkan_excel(dict_files[pilih], unik)

# --- MAIN APP ---
def main():
    # Session State Init
    if 'auth_internal' not in st.session_state: st.session_state['auth_internal'] = False
    if 'auth_dc' not in st.session_state: st.session_state['auth_dc'] = False
    if 'auth_area' not in st.session_state: st.session_state['auth_area'] = False
    if 'area_user_name' not in st.session_state: st.session_state['area_user_name'] = ""
    if 'admin_logged_in_key' not in st.session_state: st.session_state['admin_logged_in_key'] = None

    init_cloudinary()
    all_files = get_all_files_cached()

    st.title("📊 Monitoring IC Bali")
    
    menu_options = ["Area", "Internal IC", "DC", "Lapor Error", "🔐 Admin Panel", "🎨 Tampilan Web"]
    menu = st.radio("Navigasi:", menu_options, horizontal=True)
    st.divider()

    # --- 1. AREA ---
    if menu == "Area":
        if not st.session_state['auth_area']:
            c1, c2, c3 = st.columns([1, 2, 1])
            with c2:
                st.info("🔒 Silakan Login untuk akses menu Area")
                tab_login, tab_daftar = st.tabs(["Masuk (Login)", "Daftar Akun Baru"])
                
                with tab_login:
                    with st.form("login_area"):
                        u = st.text_input("Username")
                        p = st.text_input("Password", type="password")
                        if st.form_submit_button("Masuk"):
                            # PANGGIL FUNGSI FRESH (Anti Cache)
                            with st.spinner("Memverifikasi..."):
                                db_users = get_json_fresh(USER_DB_PATH) 
                                p_hash = hash_password(p)
                                if u in db_users and db_users[u] == p_hash:
                                    st.session_state['auth_area'] = True
                                    st.session_state['area_user_name'] = u
                                    catat_login_activity(u) 
                                    st.success("Login Berhasil!")
                                    st.rerun()
                                else:
                                    st.error("Username atau Password Salah (atau data belum update, coba 1 menit lagi)")
                    
                    with st.expander("❓ Lupa Password?"):
                        st.warning("Hubungi Admin Divisi NKL/Reporting.")

                with tab_daftar:
                    with st.form("daftar_area"):
                        st.write("Buat akun baru")
                        new_u = st.text_input("Username Baru")
                        new_p = st.text_input("Password Baru", type="password")
                        if st.form_submit_button("Daftar"):
                            if new_u and new_p:
                                with st.spinner("Mendaftarkan..."):
                                    # Ambil DB fresh dulu sebelum nambah
                                    db_users = get_json_fresh(USER_DB_PATH)
                                    if new_u in db_users:
                                        st.error("Username sudah dipakai!")
                                    else:
                                        db_users[new_u] = hash_password(new_p)
                                        upload_json_to_cloud(db_users, USER_DB_PATH)
                                        
                                        # AUTO LOGIN SETELAH DAFTAR (SOLUSI UX)
                                        st.session_state['auth_area'] = True
                                        st.session_state['area_user_name'] = new_u
                                        catat_login_activity(new_u)
                                        st.success("Akun Berhasil Dibuat & Login Otomatis!")
                                        time.sleep(1)
                                        st.rerun()
                            else: st.warning("Isi data dengan lengkap")
        else:
            c_info, c_out = st.columns([5, 1])
            with c_info: st.success(f"👋 Halo, {st.session_state['area_user_name']}")
            with c_out: 
                if st.button("Logout Area"):
                    st.session_state['auth_area'] = False
                    st.rerun()
            st.divider()
            t1, t2, t3 = st.tabs(["Intransit", "NKL", "Barang Rusak"])
            with t1: tampilkan_viewer("Intransit", ADMIN_CONFIG["AREA_INTRANSIT"]["folder"], all_files, "AREA_INTRANSIT")
            with t2: tampilkan_viewer("NKL", ADMIN_CONFIG["AREA_NKL"]["folder"], all_files, "AREA_NKL")
            with t3: tampilkan_viewer_area_rusak(ADMIN_CONFIG["AREA_RUSAK"]["folder"], all_files, "AREA_RUSAK")

    # --- 2. INTERNAL IC ---
    elif menu == "Internal IC":
        if not st.session_state['auth_internal']:
            c1, c2, c3 = st.columns([1,2,1])
            with c2:
                st.info("🔒 Internal Only")
                with st.form("fi"):
                    u, p = st.text_input("User"), st.text_input("Pass", type="password")
                    if st.form_submit_button("Buka"):
                        c = VIEWER_CREDENTIALS["INTERNAL_IC"]
                        if u == c['user'] and p == c['pass']:
                            st.session_state['auth_internal'] = True
                            st.rerun()
                        else: st.error("Salah")
        else:
            if st.button("Lock Internal"): 
                st.session_state['auth_internal'] = False
                st.rerun()
            t1, t2, t3 = st.tabs(["Reporting", "NKL", "Rusak"])
            with t1: tampilkan_viewer("Reporting", ADMIN_CONFIG["INTERNAL_REP"]["folder"], all_files, None)
            with t2: tampilkan_viewer("NKL", ADMIN_CONFIG["INTERNAL_NKL"]["folder"], all_files, None)
            with t3: tampilkan_viewer("Rusak", ADMIN_CONFIG["INTERNAL_RUSAK"]["folder"], all_files, None)

    # --- 3. DC ---
    elif menu == "DC":
        if not st.session_state['auth_dc']:
            c1, c2, c3 = st.columns([1,2,1])
            with c2:
                st.info("🔒 DC Only")
                with st.form("fd"):
                    u, p = st.text_input("User"), st.text_input("Pass", type="password")
                    if st.form_submit_button("Buka"):
                        c = VIEWER_CREDENTIALS["DC"]
                        if u == c['user'] and p == c['pass']:
                            st.session_state['auth_dc'] = True
                            st.rerun()
                        else: st.error("Salah")
        else:
            if st.button("Lock DC"): 
                st.session_state['auth_dc'] = False
                st.rerun()
            tampilkan_viewer("Data DC", ADMIN_CONFIG["DC_DATA"]["folder"], all_files, None)

    # --- 4. LAPOR ERROR ---
    elif menu == "Lapor Error":
        st.subheader("🚨 Lapor Error")
        up = st.file_uploader("Upload Screenshot", type=['png', 'jpg', 'jpeg'])
        if up and st.button("Kirim"):
            with st.spinner("Sending..."):
                upload_image_error(up)
                st.success("terima kasih, error anda akan diselesaikan sesuai mood admin :)")
                st.balloons()
    
    # --- 5. ADMIN PANEL ---
    elif menu == "🔐 Admin Panel":
        st.subheader("⚙️ Kelola Data (Admin Only)")
        
        if st.session_state['admin_logged_in_key'] is None:
            c1, c2, c3 = st.columns([1, 2, 1])
            with c2:
                with st.container(border=True):
                    st.write("Silakan Login sesuai Divisi")
                    dept = st.selectbox("Departemen:", ["Area", "Internal IC", "DC"])
                    pilihan_sub = []
                    if dept == "Area":
                        pilihan_sub = [("Intransit", "AREA_INTRANSIT"), ("NKL", "AREA_NKL"), ("Barang Rusak", "AREA_RUSAK")]
                    elif dept == "Internal IC":
                        pilihan_sub = [("Reporting", "INTERNAL_REP"), ("NKL", "INTERNAL_NKL"), ("Barang Rusak", "INTERNAL_RUSAK")]
                    elif dept == "DC":
                        pilihan_sub = [("Data DC", "DC_DATA")]
                    
                    sub_nm, sub_kd = st.selectbox("Target Menu:", pilihan_sub, format_func=lambda x: x[0])
                    u = st.text_input("Username Admin")
                    p = st.text_input("Password", type="password")
                    
                    if st.button("Masuk Panel Admin", use_container_width=True):
                        cfg = ADMIN_CONFIG[sub_kd]
                        if u == cfg['username'] and p == cfg['password']:
                            st.session_state['admin_logged_in_key'] = sub_kd
                            st.rerun()
                        else: st.error("Username atau Password Salah")
        else:
            key = st.session_state['admin_logged_in_key']
            cfg = ADMIN_CONFIG[key]
            
            c_head, c_out = st.columns([6, 1])
            with c_head: st.success(f"✅ Login Berhasil: {cfg['label']}")
            with c_out: 
                if st.button("Logout"): st.session_state['admin_logged_in_key']=None; st.rerun()
            
            tab_file, tab_user_mgr = st.tabs(["📂 Manajemen File", "👥 Manajemen User & Monitoring"])
            
            with tab_file:
                col_up, col_del = st.columns(2)
                with col_up:
                    st.markdown("#### 📤 Upload File Baru")
                    with st.container(border=True):
                        st.info(f"Target: `{cfg['folder']}`")
                        up = st.file_uploader("Pilih Excel", type=['xlsx'], key="admin_up")
                        if up and st.button("Mulai Upload", use_container_width=True):
                            with st.spinner("Uploading..."):
                                upload_file(up, cfg['folder'])
                                get_all_files_cached.clear()
                                st.success("Selesai!")
                                st.rerun()

                with col_del:
                    st.markdown("#### 🗑️ Hapus File")
                    with st.container(border=True):
                        prefix = cfg['folder'] + "/"
                        my_files = [f for f in all_files if f['public_id'].startswith(prefix)]
                        
                        if my_files:
                            d_del = {f['public_id'].replace(prefix, ""): f['public_id'] for f in my_files}
                            sel_del = st.selectbox("Pilih File:", list(d_del.keys()), key="admin_del")
                            if st.button("Hapus Permanen", type="primary", use_container_width=True):
                                with st.spinner("Deleting..."):
                                    hapus_file(d_del[sel_del])
                                    get_all_files_cached.clear()
                                    st.success("Terhapus.")
                                    st.rerun()
                        else:
                            st.caption("Folder kosong.")

            with tab_user_mgr:
                col_users, col_monitor = st.columns([1, 2])
                with col_users:
                    st.markdown("#### 🛠️ Kelola User Area")
                    with st.container(border=True):
                        if st.button("🔄 Reload Data User"): st.rerun()
                        # Gunakan Fresh DB untuk kelola user
                        db_users = get_json_fresh(USER_DB_PATH)
                        if db_users:
                            st.write(f"Total User: **{len(db_users)}**")
                            pilih_user = st.selectbox("Pilih Username:", list(db_users.keys()))
                            new_pass = st.text_input("Password Baru:", type="password")
                            if st.button("Reset Password", use_container_width=True):
                                if new_pass:
                                    db_users[pilih_user] = hash_password(new_pass)
                                    upload_json_to_cloud(db_users, USER_DB_PATH)
                                    st.success(f"Pass '{pilih_user}' direset!")
                                else: st.warning("Password kosong!")
                        else: st.info("Belum ada user.")

                with col_monitor:
                    st.markdown("#### 📊 Monitoring Aktivitas")
                    with st.container(border=True):
                        if st.button("🔄 Refresh Monitoring"): st.rerun()
                        # Gunakan Fresh Log
                        log_data = get_json_fresh(LOG_DB_PATH)
                        
                        if log_data:
                            rekap_list = []
                            total_hits = 0
                            for tgl, users in log_data.items():
                                for usr, count in users.items():
                                    rekap_list.append({"Tanggal": tgl, "Username": usr, "Jumlah Akses": count})
                                    total_hits += count
                            
                            df_log = pd.DataFrame(rekap_list)
                            df_log = df_log.sort_values(by="Tanggal", ascending=False)
                            
                            m1, m2 = st.columns(2)
                            m1.metric("Total Login (All Time)", total_hits)
                            
                            st.dataframe(df_log, use_container_width=True, height=300)
                            
                            csv_log = df_log.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label="📥 Download Log (CSV)", 
                                data=csv_log, 
                                file_name="Activity_Log.csv", 
                                mime="text/csv", 
                                use_container_width=True
                            )
                        else: st.info("Log aktivitas kosong.")

    # --- 6. TAMPILAN WEB ---
    elif menu == "🎨 Tampilan Web":
        st.subheader("🎨 Pengaturan Tampilan")
        c1, c2 = st.columns([1, 2])
        with c1:
            with st.container(border=True):
                opts = ["System", "Light", "Dark"]
                if st.session_state['current_theme'] not in opts: st.session_state['current_theme'] = "Dark"
                curr = opts.index(st.session_state['current_theme'])
                sel = st.radio("Mode:", opts, index=curr)
                if sel != st.session_state['current_theme']: st.session_state['current_theme'] = sel; st.rerun()
        st.info(f"Mode: **{st.session_state['current_theme']}**")

    st.markdown("""<div style='position: fixed; bottom: 0; right: 0; padding: 10px; opacity: 0.5; font-size: 12px; color: grey;'>Monitoring IC Bali System</div>""", unsafe_allow_html=True)

if __name__ == "__main__":
    main()