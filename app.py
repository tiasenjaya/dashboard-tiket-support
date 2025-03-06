import streamlit as st  # Pastikan Streamlit diimpor lebih dulu
st.set_page_config(layout="wide", initial_sidebar_state="collapsed")  # Mengatur layout menjadi full-width

import pandas as pd
import plotly.express as px  # Import lainnya setelahnya

# **🔗 Link ke Google Sheets (Pastikan diubah ke format CSV)**
SHEET_ID = "1Nev5-cSUKDlU4z3glFC90VhJjxv09njFlbJWK5G4oOc"  # Ganti dengan ID Spreadsheet Anda
SHEET_LIST_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Sheet_List"

# **📥 Baca daftar sheet dari Sheet_List**
@st.cache_data
def load_sheets():
    df_sheets = pd.read_csv(SHEET_LIST_URL, header=None)
    return df_sheets.iloc[:, 0].dropna().tolist()

sheet_names = load_sheets()

# **📄 Sidebar - Pilih Sheet**
st.sidebar.header("📊 Filter Data")
selected_sheet = st.sidebar.selectbox("📄 Pilih Sheet:", sheet_names)

# **📥 Baca Data dari Google Sheets berdasarkan Sheet yang dipilih**
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={selected_sheet}"

@st.cache_data
def load_data(url):
    df = pd.read_csv(url)
    df.rename(columns=lambda x: x.strip(), inplace=True)  # Menghilangkan spasi ekstra di nama kolom
    df["Ticket Number"] = df["Ticket Number"].astype(str)  # Pastikan Ticket Number tidak diformat sebagai angka
    df["Created"] = pd.to_datetime(df["Created"], errors='coerce', dayfirst=True).dt.date
    df["Finish"] = pd.to_datetime(df["Finish"], errors='coerce', dayfirst=True).dt.date
    df = df.dropna(subset=["Created"])  # Hapus data yang gagal dikonversi
    return df

df = load_data(CSV_URL)

# **📊 Sidebar - Pilih Rentang Tanggal**
min_date = df["Created"].min()
max_date = df["Created"].max()
date_range = st.sidebar.date_input("📅 Pilih Rentang Tanggal", [min_date, max_date], min_value=min_date, max_value=max_date)

# **👤 Sidebar - Pilih Support**
support_filter = st.sidebar.selectbox("👤 Pilih Support:", ["All"] + df["Assign To"].dropna().unique().tolist())

# **📌 Filter Data berdasarkan pilihan**
df_filtered = df[(df["Created"] >= date_range[0]) & (df["Created"] <= date_range[1])]

if support_filter != "All":
    df_filtered = df_filtered[df_filtered["Assign To"] == support_filter]

# **🔄 Pengaturan Layout agar Sidebar tidak terlalu besar & tampilan lebih rapi**
col_space, col_main, col_space2 = st.columns([0.2, 1, 0.2])  # Ruang kiri & kanan lebih kecil

with col_main:
    DASHBOARD_TITLE = "📊 Performance Dashboard"  # Ganti sesuai keinginan
    st.title(DASHBOARD_TITLE)
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_tiket = len(df_filtered)
    selesai_hari_h = len(df_filtered[df_filtered["Created"] == df_filtered["Finish"]])
    selesai_setelah_hari_h = len(df_filtered[df_filtered["Created"] < df_filtered["Finish"]])
    belum_selesai = len(df_filtered[df_filtered["Status"] != "Finish"])

    col1.metric(label="🎟️ Total Tiket", value=total_tiket)
    col2.metric(label="✅ Tiket Selesai di Hari H", value=selesai_hari_h)
    col3.metric(label="📋 Tiket Selesai Setelah Hari H", value=selesai_setelah_hari_h)
    col4.metric(label="⏳ Tiket Belum Selesai", value=belum_selesai)

    st.subheader("📌 Performa Penyelesaian Tiket")
    finish_percentage = ((selesai_hari_h + selesai_setelah_hari_h) / total_tiket) * 100 if total_tiket > 0 else 0
    st.progress(finish_percentage / 100)
    st.write(f"✅ **{finish_percentage:.2f}% tiket telah selesai** dari total {total_tiket} tiket.")

    st.markdown("### 📝 Data Tiket yang Difilter")
    with st.expander("📋 Klik untuk melihat data tiket yang difilter"):
        st.dataframe(df_filtered)

    st.subheader("📈 Statistik Tiket Per Hari")
    if not df_filtered.empty:
        df_summary = df_filtered.groupby("Created").agg(
            Total_Tiket=("Ticket Number", "count"),
            Total_Finish=("Status", lambda x: (x == "Finish").sum())
        ).reset_index()

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 📊 Grafik Bar Chart (Tren Penyelesaian Tiket Per Hari)")
            fig_bar = px.bar(
                df_summary,
                x="Created",
                y=["Total_Tiket", "Total_Finish"],
                labels={"value": "Jumlah Tiket", "Created": "Tanggal"},
                title="Tren Penyelesaian Tiket Per Hari",
                barmode="group"
            )
            fig_bar.update_xaxes(type="category")
            st.plotly_chart(fig_bar)

        with col2:
            st.markdown("### 🏆 Perbandingan Persentase Penyelesaian Tiket (Pie Chart)")
            df_pie = pd.DataFrame({
                "Kategori": ["Tiket Selesai di Hari H", "Tiket Selesai Setelah Hari H", "Tiket Belum Selesai"],
                "Jumlah": [selesai_hari_h, selesai_setelah_hari_h, belum_selesai]
            })

            color_mapping = {
                    "Tiket Selesai di Hari H": "#1f77b4",  # Biru
                    "Tiket Selesai Setelah Hari H": "#ff7f0e",  # Oranye
                    "Tiket Belum Selesai": "#d62728"  # Merah
            }

            fig_pie = px.pie(
            df_pie,
            names="Kategori",
            values="Jumlah",
            title="Distribusi Penyelesaian Tiket",
            color="Kategori",  # Menggunakan warna tetap
            color_discrete_map=color_mapping  # Tetapkan warna untuk setiap kategori
            )


# **🔄 Tombol Refresh Data**
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
