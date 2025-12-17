import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
import cloudinary.api

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Web Excel Cloudinary", layout="wide")

# --- 2. SAMBUNGKAN KE CLOUDINARY ---
# Mengambil kunci dari pengaturan rahasia (Secrets)
def init_cloudinary():
    # Cek apakah kunci ada
    if "cloudinary" not in st.secrets:
        st.error("Kunci Cloudinary belum dipasang!")
        st.stop()
        
    cloudinary.config( 
        cloud_name = st.secrets["cloudinary"]["cloud_name"], 
        api_key = st.secrets["cloudinary"]["api_key"], 
        api_secret = st.secrets["cloudinary"]["api_secret"],
        secure = True
    )

# --- 3. FUNGSI UPLOAD FILE ---
def upload_file(file_upload):
    # resource_type="raw" wajib untuk file dokumen (Excel/Word/PDF)
    res = cloudinary.uploader.upload(
        file_upload, 
        resource_type = "raw", 
        public_id = file_upload.name,
        overwrite = True
    )
    return res

# --- 4. TAMPILAN UTAMA ---
def main():
    st.title("📊 Web Penampil Excel (Cloudinary)")
    
    # Panggil fungsi koneksi
    init_cloudinary()

    # --- MENU KIRI: UPLOAD ---
    with st.sidebar:
        st.header("Upload Data Baru")
        uploaded_file = st.file_uploader("Pilih file Excel (.xlsx)", type=['xlsx'])
        
        if uploaded_file is not None:
            if st.button("Simpan ke Cloud"):
                with st.spinner("Sedang mengupload..."):
                    try:
                        upload_file(uploaded_file)
                        st.success("Berhasil! File tersimpan.")
                        st.rerun() # Refresh halaman
                    except Exception as e:
                        st.error(f"Gagal upload: {e}")

    # --- MENU KANAN: LIHAT DATA ---
    st.subheader("Pilih File untuk Dilihat")
    
    # Ambil daftar file dari Cloudinary
    try:
        # Mengambil file tipe 'raw' (dokumen)
        result = cloudinary.api.resources(resource_type="raw", type="upload", max_results=100)
        files = result.get('resources', [])
    except Exception as e:
        st.warning("Gagal mengambil daftar file (Mungkin kunci salah atau internet putus).")
        files = []

    # Filter hanya file excel
    excel_files = [f for f in files if f['public_id'].endswith('.xlsx')]

    if not excel_files:
        st.info("Belum ada file Excel. Silahkan upload di menu sebelah kiri.")
    else:
        # Buat pilihan nama file
        dict_files = {f['public_id']: f['secure_url'] for f in excel_files}
        pilihan = st.selectbox("Daftar File:", list(dict_files.keys()))
        
        # Jika user memilih file
        if pilihan:
            url_file = dict_files[pilihan]
            
            # Baca Excel langsung dari URL Cloudinary
            try:
                df = pd.read_excel(url_file)
                
                st.divider()
                st.write(f"Menampilkan data: **{pilihan}**")

                # --- FITUR PENCARIAN & FILTER ---
                cari = st.text_input("🔍 Cari data (Ketik kata kunci):")
                
                if cari:
                    # Logic pencarian: Cek di semua kolom apakah mengandung kata kunci
                    mask = df.astype(str).apply(lambda x: x.str.contains(cari, case=False, na=False)).any(axis=1)
                    df_tampil = df[mask]
                else:
                    df_tampil = df
                
                # Tampilkan Tabel
                st.dataframe(df_tampil, use_container_width=True)
                st.write(f"Jumlah baris: {len(df_tampil)}")

            except Exception as e:
                st.error("File rusak atau bukan format Excel yang benar.")

if __name__ == "__main__":
    main()