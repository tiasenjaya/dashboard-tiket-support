import pandas as pd
import streamlit as st

# **🔗 Link Google Sheets dalam format CSV**
GOOGLE_SHEET_ID = "1Nev5-cSUKDlU4z3glFC90VhJjxv09njFlbJWK5G4oOc"

# **📌 URL untuk membaca daftar sheet (Sheet_List)**
SHEET_LIST_URL = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Sheet_List"

# **📌 Fungsi untuk membaca daftar sheet**
@st.cache_data
def get_sheet_list():
    df_list = pd.read_csv(SHEET_LIST_URL, header=None)  # Membaca sheet pertama (daftar sheet)
    return df_list[0].tolist()  # Ambil daftar sheet sebagai list

# **📌 Sidebar - Pilih Sheet Secara Otomatis**
st.sidebar.header("📊 Filter Data")
sheet_list = get_sheet_list()
selected_sheet = st.sidebar.selectbox("📄 Pilih Sheet:", sheet_list)

# **📌 URL untuk membaca data dari sheet yang dipilih**
SHEET_DATA_URL = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/gviz/tq?tqx=out:csv&sheet={selected_sheet}"

# **📥 Baca data dari Google Sheets berdasarkan pilihan user**
@st.cache_data
def load_data(url):
    df = pd.read_csv(url)
    df["Created Date"] = pd.to_datetime(df["Created Date"], errors='coerce').dt.date
    return df

df = load_data(SHEET_DATA_URL)

# **📌 Sidebar - Pilih Rentang Tanggal**
min_date = df["Created Date"].min()
max_date = df["Created Date"].max()
date_range = st.sidebar.date_input("📅 Pilih Rentang Tanggal:", [min_date, max_date])

# **📌 Sidebar - Pilih Support**
support_filter = st.sidebar.selectbox("👤 Pilih Support:", ["All"] + df["Assign To"].unique().tolist())

# **📌 Filter Data berdasarkan pilihan**
df_filtered = df[(df["Created Date"] >= date_range[0]) & (df["Created Date"] <= date_range[1])]

if support_filter != "All":
    df_filtered = df_filtered[df_filtered["Assign To"] == support_filter]

# **📊 Hitung Total Tiket**
total_tiket = len(df_filtered)
finish_tiket = len(df_filtered[df_filtered["Condition"] == "FINISH"])
not_finish_tiket = len(df_filtered[df_filtered["Condition"] == "NOT FINISH"])
finish_percentage = (finish_tiket / total_tiket) * 100 if total_tiket > 0 else 0

# **📌 Tampilkan Header Dashboard**
st.markdown("<h1 style='text-align: center;'>📊 Dashboard Tiket Support</h1>", unsafe_allow_html=True)

# **📌 Tampilkan Statistik dalam Kartu**
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(f"<div style='background-color:#ff4757; padding: 20px; border-radius: 10px; text-align: center;'>"
                f"<h3 style='color:white;'>🎟️ Total Tiket</h3><h2 style='color:white;'>{total_tiket:,}</h2></div>",
                unsafe_allow_html=True)
with col2:
    st.markdown(f"<div style='background-color:#2ed573; padding: 20px; border-radius: 10px; text-align: center;'>"
                f"<h3 style='color:white;'>✅ Tiket Selesai</h3><h2 style='color:white;'>{finish_tiket:,}</h2></div>",
                unsafe_allow_html=True)
with col3:
    st.markdown(f"<div style='background-color:#ffa502; padding: 20px; border-radius: 10px; text-align: center;'>"
                f"<h3 style='color:white;'>⏳ Tiket Belum Selesai</h3><h2 style='color:white;'>{not_finish_tiket:,}</h2></div>",
                unsafe_allow_html=True)

# **📌 Progress Bar Persentase Tiket Selesai**
st.subheader("📌 Performa Penyelesaian Tiket")
st.progress(finish_percentage / 100)
st.write(f"✅ **{finish_percentage:.2f}% tiket telah selesai** dari total {total_tiket} tiket.")

# **📋 Tampilkan Data yang Difilter**
st.subheader("📋 Data Tiket yang Difilter")
st.dataframe(df_filtered)
