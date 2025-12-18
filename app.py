import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
import cloudinary.api
import hashlib
import requests
import io
import openpyxl
from openpyxl.styles import PatternFill

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Web Monitoring IC Bali", layout="wide", page_icon="📊")

# --- 2. DATA AKUN & FOLDER ---
AKUN_DIVISI = {
    "REPORTING": {
        "username": "admin_rep",
        "password": "rep123",
        "folder_name": "Reporting",
        "nama_lengkap": "Divisi Reporting / Intransit"
    },
    "NKL": {
        "username": "admin_nkl",
        "password": "nkl123",
        "folder_name": "NKL",
        "nama_lengkap": "Divisi NKL"
    },
    "RUSAK": {
        "username": "admin_rusak",
        "password": "rusak123",
        "folder_name": "BarangRusak",
        "nama_lengkap": "Divisi Barang Rusak"
    }
}

# --- 3. KONEKSI CLOUDINARY ---
def init_cloudinary():
    if "cloudinary" not in st.secrets:
        st.error("⚠️ Kunci Cloudinary belum dipasang!")
        st.stop()
        
    cloudinary.config( 
        cloud_name = st.secrets["cloudinary"]["cloud_name"], 
        api_key = st.secrets["cloudinary"]["api_key"], 
        api_secret = st.secrets["cloudinary"]["api_secret"],
        secure = True
    )

def upload_file(file_upload, nama_folder):
    public_id_path = f"{nama_folder}/{file_upload.name}"
    res = cloudinary.uploader.upload(
        file_upload, 
        resource_type = "raw", 
        public_id = public_id_path,
        overwrite = True
    )
    return res

def hapus_file(public_id):
    try:
        cloudinary.api.delete_resources([public_id], resource_type="raw", type="upload")
        return True
    except Exception as e:
        st.error(f"Gagal menghapus: {e}")
        return False

# --- 4. FUNGSI MAGIC COLOR (PERBAIKAN ERROR KOLOM) ---
def get_excel_styles(file_content, sheet_name, header_row, df_original):
    """
    Fungsi ini mengambil warna dari Excel dan memastikan
    struktur kolomnya SAMA PERSIS dengan DataFrame pandas.
    """
    try:
        wb = openpyxl.load_workbook(file_content, data_only=True)
        ws = wb[sheet_name]
        
        # PERBAIKAN DI SINI:
        # Kita buat DataFrame kosong tapi Index dan Kolomnya meniru df_original
        # Ini mencegah error "invalid columns labels"
        styles = pd.DataFrame("", index=df_original.index, columns=df_original.columns)
        
        # Menentukan baris awal data di Excel (Header + 1)
        start_row_excel = header_row + 1 
        
        # Kita loop berdasarkan ukuran DataFrame
        # r_idx = index baris (0, 1, 2...)
        # row_data = isi baris (tidak dipakai, kita cuma butuh indexnya)
        for r_idx in range(len(df_original)):
            # Tentukan posisi baris di Excel
            current_excel_row = start_row_excel + r_idx
            
            # Ambil baris dari Excel
            # (Optimasi: kita akses langsung row-nya)
            row_cells = ws[current_excel_row]
            
            for c_idx in range(len(df_original.columns)):
                # Pastikan tidak melampaui kolom yang ada di Excel
                if c_idx < len(row_cells):
                    cell = row_cells[c_idx]
                    fill = cell.fill
                    
                    if fill and fill.patternType == 'solid':
                        fg = fill.start_color
                        if fg.type == 'rgb':
                            # Warna RGB Hex
                            # Kadang ada alpha channel di depan (misal FF000000), kita ambil 6 digit terakhir
                            hex_code = fg.rgb
                            if len(str(hex_code)) > 6:
                                hex_code = str(hex_code)[2:] 
                            
                            color_code = f"#{hex_code}"
                            
                            # Masukkan ke styles menggunakan .iat (akses posisi angka)
                            styles.iat[r_idx, c_idx] = f'background-color: {color_code}'
        
        return styles
    except Exception as e:
        # Jika error, return None agar kode utama tahu
        # st.error(f"Debug Style Error: {e}") # Uncomment untuk debug
        return None

# --- 5. TAMPILAN PER DIVISI ---
def tampilkan_tab_divisi(nama_divisi, folder_target, semua_files):
    st.subheader(f"📂 Data: {nama_divisi}")
    
    prefix_folder = folder_target + "/"
    files_divisi = [f for f in semua_files if f['public_id'].startswith(prefix_folder) and f['public_id'].endswith('.xlsx')]
    
    if not files_divisi:
        st.info(f"Folder '{folder_target}' kosong.")
    else:
        dict_files = {}
        for f in files_divisi:
            nama_bersih = f['public_id'].replace(prefix_folder, "")
            dict_files[nama_bersih] = f['secure_url']
        
        pilihan_file = st.selectbox(f"1. Pilih File Excel:", list(dict_files.keys()), key=f"sel_file_{folder_target}")
        
        if pilihan_file:
            url_file = dict_files[pilihan_file]
            
            try:
                # Download ke memory
                response = requests.get(url_file)
                file_content = io.BytesIO(response.content)
                
                xls = pd.ExcelFile(file_content)
                daftar_sheet = xls.sheet_names
                
                st.write("---")
                col1, col2, col3 = st.columns([2, 1, 2])
                
                with col1:
                    sheet_terpilih = st.selectbox("2. Pilih Sheet:", daftar_sheet, key=f"sheet_{folder_target}")
                
                with col2:
                    header_row = st.number_input("3. Header Baris ke-", min_value=1, value=1, key=f"head_{folder_target}")
                
                with col3:
                    cari = st.text_input("🔍 Cari Data:", key=f"search_{folder_target}")

                # --- BACA DATA UTAMA ---
                # Baca dataframe lengkap dulu
                df = pd.read_excel(file_content, sheet_name=sheet_terpilih, header=header_row - 1)
                
                # --- PROSES FILTER DATA ---
                if cari:
                    # Filter Data
                    mask = df.astype(str).apply(lambda x: x.str.contains(cari, case=False, na=False)).any(axis=1)
                    df_tampil = df[mask]
                else:
                    df_tampil = df

                # --- PROSES WARNA (FIXED) ---
                tampilkan_polos = True # Default polos jika warna gagal
                
                if len(df_tampil) < 3000: # Batas baris agar tidak berat
                    with st.spinner("Mencocokkan warna sel..."):
                        # Ambil style matrix Penuh (Sesuai df asli)
                        style_matrix = get_excel_styles(file_content, sheet_terpilih, header_row, df)
                        
                        if style_matrix is not None:
                            try:
                                # Filter style matrix agar barisnya sama dengan df_tampil (hasil search)
                                # .loc akan mencocokkan Index Baris secara otomatis
                                style_tampil = style_matrix.loc[df_tampil.index]
                                
                                # Tampilkan dengan Styler
                                st.success(f"Menampilkan Sheet: **{sheet_terpilih}** (Warna Aktif 🎨)")
                                st.dataframe(
                                    df_tampil.style.apply(lambda x: style_tampil, axis=None), 
                                    use_container_width=True,
                                    height=600
                                )
                                tampilkan_polos = False
                            except Exception as e:
                                st.warning(f"Gagal menerapkan filter warna, menampilkan data polos. ({e})")
                
                if tampilkan_polos:
                    # Jika warna dimatikan atau error, tampilkan biasa
                    st.success(f"Menampilkan Sheet: **{sheet_terpilih}**")
                    st.dataframe(df_tampil, use_container_width=True, height=600)
                
                st.caption(f"Total: {len(df_tampil)} Baris")
                
            except Exception as e:
                st.error("Gagal membaca file atau format header salah.")
                st.error(f"Info Error: {e}")

# --- 6. PROGRAM UTAMA ---
def main():
    if 'logged_in_divisi' not in st.session_state:
        st.session_state['logged_in_divisi'] = None

    init_cloudinary()

    try:
        raw_files = cloudinary.api.resources(resource_type="raw", type="upload", max_results=500)
        files_list = raw_files.get('resources', [])
    except:
        files_list = []

    # === SIDEBAR ===
    with st.sidebar:
        st.header("🔐 Login Upload")
        
        if st.session_state['logged_in_divisi'] is None:
            target_divisi = st.selectbox("Pilih Divisi:", ["REPORTING", "NKL", "RUSAK"])
            user_input = st.text_input("Username")
            pass_input = st.text_input("Password", type="password")
            
            if st.button("Masuk"):
                akun = AKUN_DIVISI[target_divisi]
                if user_input == akun["username"] and pass_input == akun["password"]:
                    st.session_state['logged_in_divisi'] = target_divisi
                    st.success("Berhasil!")
                    st.rerun()
                else:
                    st.error("Salah password!")
        else:
            divisi_aktif = st.session_state['logged_in_divisi']
            info_akun = AKUN_DIVISI[divisi_aktif]
            folder_aktif = info_akun['folder_name']
            
            st.success(f"Login: {info_akun['nama_lengkap']}")
            
            st.subheader("📤 Upload File")
            uploaded_file = st.file_uploader("Pilih Excel", type=['xlsx'])
            if uploaded_file is not None:
                if st.button(f"Upload ke {divisi_aktif}"):
                    with st.spinner("Mengirim..."):
                        try:
                            upload_file(uploaded_file, folder_aktif)
                            st.success("Sukses upload!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
            
            st.markdown("---")
            st.subheader("🗑️ Hapus File")
            prefix_folder = folder_aktif + "/"
            file_milik_divisi = [f for f in files_list if f['public_id'].startswith(prefix_folder)]
            
            if not file_milik_divisi:
                st.caption("Tidak ada file.")
            else:
                opsi_hapus = {f['public_id'].replace(prefix_folder, ""): f['public_id'] for f in file_milik_divisi}
                file_to_delete = st.selectbox("Pilih file:", list(opsi_hapus.keys()))
                if st.button(f"❌ Hapus {file_to_delete}"):
                     with st.spinner("Menghapus..."):
                         if hapus_file(opsi_hapus[file_to_delete]):
                             st.success("Terhapus.")
                             st.rerun()
            
            st.markdown("---")
            if st.button("🚪 Log Out"):
                st.session_state['logged_in_divisi'] = None
                st.rerun()

    # === HALAMAN UTAMA ===
    st.title("📊 Monitoring IC Bali")
    
    tab_rep, tab_nkl, tab_rusak = st.tabs(["🚛 Reporting", "📉 NKL", "⚠️ Barang Rusak"])

    with tab_rep:
        tampilkan_tab_divisi("Reporting", AKUN_DIVISI["REPORTING"]["folder_name"], files_list)

    with tab_nkl:
        tampilkan_tab_divisi("NKL", AKUN_DIVISI["NKL"]["folder_name"], files_list)

    with tab_rusak:
        tampilkan_tab_divisi("Barang Rusak", AKUN_DIVISI["RUSAK"]["folder_name"], files_list)

if __name__ == "__main__":
    main()