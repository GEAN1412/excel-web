import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
import cloudinary.api
import hashlib
import requests
import io

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Web Monitoring IC Bali", layout="wide", page_icon="🏢")

# --- 2. CSS & STYLE (MENYEMBUNYIKAN MENU) ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            footer {visibility: hidden;}
            .stDeployButton {display:none;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- 3. KONFIGURASI ADMIN ---
ADMIN_CONFIG = {
    "AREA_INTRANSIT": {"username": "admin_area_prof", "password": "123", "folder": "Area/Intransit", "label": "Area - Intransit/Proforma"},
    "AREA_NKL": {"username": "admin_area_nkl", "password": "123", "folder": "Area/NKL", "label": "Area - NKL"},
    "AREA_RUSAK": {"username": "admin_area_rusak", "password": "123", "folder": "Area/BarangRusak", "label": "Area - Barang Rusak"},
    
    "INTERNAL_REP": {"username": "admin_ic_rep", "password": "123", "folder": "InternalIC/Reporting", "label": "Internal IC - Reporting"},
    "INTERNAL_NKL": {"username": "admin_ic_nkl", "password": "123", "folder": "InternalIC/NKL", "label": "Internal IC - NKL"},
    "INTERNAL_RUSAK": {"username": "admin_ic_rusak", "password": "123", "folder": "InternalIC/BarangRusak", "label": "Internal IC - Barang Rusak"},
    
    "DC_DATA": {"username": "admin_dc", "password": "123", "folder": "DC/General", "label": "DC - Data Utama"}
}

# --- 4. DATA KONTAK ---
DATA_CONTACT = {
    "AREA": [("Putu IC", "087850110155"), ("Pribadi IC", "087761390987")],
    "INTERNAL": [("Muklis IC", "081934327289"), ("Ari IC", "081353446516"), ("Yani IC", "087760346299"), ("Tulasi IC", "081805347302")],
    "DC": [("Admin DC", "-")]
}

VIEWER_CREDENTIALS = {
    "INTERNAL_IC": {"user": "ic_bli", "pass": "123456"},
    "DC": {"user": "IC_DC", "pass": "123456"}
}

# --- 5. FUNGSI SYSTEM ---
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

@st.cache_data(ttl=600, show_spinner=False)
def load_excel_data(url, sheet_name, header_row, force_text=False):
    try:
        response = requests.get(url)
        file_content = io.BytesIO(response.content)
        if force_text:
            df = pd.read_excel(file_content, sheet_name=sheet_name, header=header_row - 1, dtype=str).fillna("")
        else:
            df = pd.read_excel(file_content, sheet_name=sheet_name, header=header_row - 1)
            # Jangan bulatkan di sini dulu, biarkan raw number agar bisa diformat rupiah
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

def format_rupiah(nilai):
    """Mengubah angka menjadi format Rp Indonesia (Titik sebagai ribuan)"""
    try:
        # Format ribuan koma dulu (10,000)
        hasil = "{:,.0f}".format(float(nilai))
        # Ganti koma jadi titik, dan tempel Rp
        return f"Rp {hasil.replace(',', '.')}"
    except:
        return nilai

def tampilkan_kontak(tipe):
    kontak = DATA_CONTACT.get(tipe, [])
    if kontak:
        with st.expander(f"📞 Contact Person ({tipe})"):
            cols = st.columns(4)
            for i, (nama, telp) in enumerate(kontak):
                wa = "62" + telp[1:] if telp.startswith("0") else telp
                cols[i%4].info(f"**{nama}**\n[{telp}](https://wa.me/{wa})")

# --- LOGIKA TAMPILAN UTAMA ---
def proses_tampilkan_excel(url, key_unik):
    sheets = get_sheet_names(url)
    if sheets:
        c1, c2 = st.columns(2)
        sh = c1.selectbox("Sheet:", sheets, key=f"sh_{key_unik}")
        hd = c2.number_input("Header:", 1, key=f"hd_{key_unik}")
        c3, c4 = st.columns([2, 1])
        src = c3.text_input("Cari:", key=f"src_{key_unik}")
        fmt = c4.checkbox("Jaga Format Teks (No HP/Kode)", key=f"fmt_{key_unik}")
        
        with st.spinner("Loading..."):
            df = load_excel_data(url, sh, hd, fmt)
        
        if df is not None:
            # 1. Filter Pencarian
            if src:
                df = df[df.astype(str).apply(lambda x: x.str.contains(src, case=False, na=False)).any(axis=1)]

            # 2. FITUR AUTO FORMAT RUPIAH
            # Jika user TIDAK mencentang "Jaga Format Teks", kita aktifkan format Rupiah
            if not fmt:
                # Cari kolom yang berisi angka
                numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns.tolist()
                
                # Tebak kolom uang berdasarkan nama (Case Insensitive)
                # Kata kunci: Rp, Sales, Margin, Harga, Amount, Total, Cost, Jual, Beli
                keywords_uang = ['rp', 'sales', 'margin', 'harga', 'amount', 'total', 'cost', 'jual', 'beli', 'net', 'prod']
                
                # Filter kolom yang namanya mengandung kata kunci di atas
                default_rupiah = [col for col in numeric_cols if any(k in col.lower() for k in keywords_uang)]
                
                # Tampilkan Multiselect agar user bisa koreksi
                st.write("") # Spasi
                with st.expander("💰 Pengaturan Format Mata Uang (Rupiah)", expanded=False):
                    cols_to_format = st.multiselect(
                        "Pilih kolom yang ingin dijadikan format Rp:",
                        options=numeric_cols,
                        default=default_rupiah,
                        key=f"money_{key_unik}"
                    )
                
                # Terapkan Format Rupiah (Rp 10.000)
                # Kita ubah datanya menjadi String agar visualnya pas
                if cols_to_format:
                    for col in cols_to_format:
                        df[col] = df[col].apply(format_rupiah)
                    
                # Sisa kolom numerik yang BUKAN rupiah, kita bulatkan 2 digit desimal biasa
                sisa_cols = [c for c in numeric_cols if c not in cols_to_format]
                for col in sisa_cols:
                    # Cek lagi apakah kolom itu masih numeric (karena format_rupiah mengubah jadi object)
                    if pd.api.types.is_numeric_dtype(df[col]):
                        df[col] = df[col].round(2)

            st.dataframe(df, use_container_width=True, height=500)
            st.caption(f"Total: {len(df)} Baris")
        else:
            st.error("Error load data.")

def tampilkan_viewer(judul_tab, folder_target, semua_files, tipe_kontak):
    tampilkan_kontak(tipe_kontak)
    prefix = folder_target + "/"
    files_filtered = [f for f in semua_files if f['public_id'].startswith(prefix) and f['public_id'].endswith('.xlsx')]
    
    if not files_filtered:
        st.info(f"📭 Kosong: {folder_target}")
        return

    dict_files = {f['public_id'].replace(prefix, ""): f['secure_url'] for f in files_filtered}
    unik = f"std_{folder_target}"
    pilih = st.selectbox(f"Pilih File {judul_tab}:", list(dict_files.keys()), key=f"sel_{unik}")
    
    if pilih:
        proses_tampilkan_excel(dict_files[pilih], unik)

def tampilkan_viewer_area_rusak(folder_target, semua_files, tipe_kontak):
    tampilkan_kontak(tipe_kontak)
    st.markdown("### ⚠️ Area - Barang Rusak")
    
    kategori = st.radio("Filter:", ["Semua Data", "Say Bread", "Mr Bread", "Fried Chicken", "Onigiri"], horizontal=True)
    st.divider()

    prefix = folder_target + "/"
    files_in = [f for f in semua_files if f['public_id'].startswith(prefix) and f['public_id'].endswith('.xlsx')]
    
    if kategori == "Semua Data": files_final = files_in
    elif kategori == "Say Bread": files_final = [f for f in files_in if "say bread" in f['public_id'].lower()]
    elif kategori == "Mr Bread": files_final = [f for f in files_in if "mr bread" in f['public_id'].lower()]
    elif kategori == "Fried Chicken": files_final = [f for f in files_in if "fried chicken" in f['public_id'].lower()]
    elif kategori == "Onigiri": files_final = [f for f in files_in if "onigiri" in f['public_id'].lower()]
    else: files_final = []

    if not files_final:
        st.warning(f"File '{kategori}' tidak ditemukan.")
        return

    dict_files = {f['public_id'].replace(prefix, ""): f['secure_url'] for f in files_final}
    unik = "area_rusak_special"
    pilih = st.selectbox(f"Pilih File ({kategori}):", list(dict_files.keys()), key=f"sel_{unik}")
    
    if pilih:
        proses_tampilkan_excel(dict_files[pilih], unik)

# --- PROGRAM UTAMA ---
def main():
    if 'auth_internal' not in st.session_state: st.session_state['auth_internal'] = False
    if 'auth_dc' not in st.session_state: st.session_state['auth_dc'] = False
    if 'admin_logged_in_key' not in st.session_state: st.session_state['admin_logged_in_key'] = None

    init_cloudinary()
    try:
        raw = cloudinary.api.resources(resource_type="raw", type="upload", max_results=500)
        all_files = raw.get('resources', [])
    except: all_files = []

    # SIDEBAR ADMIN
    with st.sidebar:
        st.header("🔐 Admin Panel")
        if st.session_state['admin_logged_in_key'] is None:
            dept = st.selectbox("Departemen:", ["Area", "Internal IC", "DC"])
            pilihan_sub = []
            if dept == "Area":
                pilihan_sub = [("Intransit", "AREA_INTRANSIT"), ("NKL", "AREA_NKL"), ("Barang Rusak", "AREA_RUSAK")]
            elif dept == "Internal IC":
                pilihan_sub = [("Reporting", "INTERNAL_REP"), ("NKL", "INTERNAL_NKL"), ("Barang Rusak", "INTERNAL_RUSAK")]
            elif dept == "DC":
                pilihan_sub = [("Data DC", "DC_DATA")]
            
            sub_nm, sub_kd = st.selectbox("Menu:", pilihan_sub, format_func=lambda x: x[0])
            u, p = st.text_input("User"), st.text_input("Pass", type="password")
            
            if st.button("Masuk"):
                cfg = ADMIN_CONFIG[sub_kd]
                if u == cfg['username'] and p == cfg['password']:
                    st.session_state['admin_logged_in_key'] = sub_kd
                    st.rerun()
                else: st.error("Salah")
        else:
            key = st.session_state['admin_logged_in_key']
            cfg = ADMIN_CONFIG[key]
            st.success(f"Login: {cfg['label']}")
            
            up = st.file_uploader("Upload Excel", type=['xlsx'])
            if up and st.button("Upload"):
                with st.spinner("..."):
                    upload_file(up, cfg['folder'])
                    st.success("Sukses!")
                    st.rerun()
            
            st.divider()
            prefix = cfg['folder'] + "/"
            my_files = [f for f in all_files if f['public_id'].startswith(prefix)]
            if my_files:
                d_del = {f['public_id'].replace(prefix, ""): f['public_id'] for f in my_files}
                sel_del = st.selectbox("Hapus File:", list(d_del.keys()))
                if st.button("❌ Hapus"):
                    hapus_file(d_del[sel_del])
                    st.rerun()
            
            st.divider()
            if st.button("Logout"):
                st.session_state['admin_logged_in_key'] = None
                st.rerun()

    # CONTENT UTAMA
    st.title("📊 Monitoring IC Bali")
    menu = st.radio("Menu:", ["Area", "Internal IC", "DC", "Lapor Error"], horizontal=True)
    st.divider()

    if menu == "Area":
        t1, t2, t3 = st.tabs(["Intransit", "NKL", "Barang Rusak"])
        with t1: tampilkan_viewer("Intransit", ADMIN_CONFIG["AREA_INTRANSIT"]["folder"], all_files, "AREA")
        with t2: tampilkan_viewer("NKL", ADMIN_CONFIG["AREA_NKL"]["folder"], all_files, "AREA")
        with t3: tampilkan_viewer_area_rusak(ADMIN_CONFIG["AREA_RUSAK"]["folder"], all_files, "AREA")

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
            with t1: tampilkan_viewer("Reporting", ADMIN_CONFIG["INTERNAL_REP"]["folder"], all_files, "INTERNAL")
            with t2: tampilkan_viewer("NKL", ADMIN_CONFIG["INTERNAL_NKL"]["folder"], all_files, "INTERNAL")
            with t3: tampilkan_viewer("Rusak", ADMIN_CONFIG["INTERNAL_RUSAK"]["folder"], all_files, "INTERNAL")

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
            tampilkan_viewer("Data DC", ADMIN_CONFIG["DC_DATA"]["folder"], all_files, "DC")

    elif menu == "Lapor Error":
        st.subheader("🚨 Lapor Error")
        up = st.file_uploader("Upload Screenshot", type=['png', 'jpg', 'jpeg'])
        if up and st.button("Kirim"):
            with st.spinner("Sending..."):
                upload_image_error(up)
                st.success("terima kasih, error anda akan diselesaikan sesuai mood admin :)")
                st.balloons()

if __name__ == "__main__":
    main()