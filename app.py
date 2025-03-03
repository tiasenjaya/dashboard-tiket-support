import streamlit as st  # Pastikan Streamlit diimpor lebih dulu
st.set_page_config(layout="wide")  # Mengatur layout menjadi full-width

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
selected_sheet = st.sidebar.selectbox("📄 Pilih Sheet:", sheet_names, key="sheet_select_sidebar")

# **📥 Baca Data dari Google Sheets berdasarkan Sheet yang dipilih**
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={selected_sheet}"

@st.cache_data
def load_data(url):
    df = pd.read_csv(url)
    df["Created Date"] = pd.to_datetime(df["Created Date"], errors='coerce', dayfirst=True).dt.date
    df = df.dropna(subset=["Created Date"])  # Hapus data yang gagal dikonversi
    return df

df = load_data(CSV_URL)

# **📊 Sidebar - Pilih Rentang Tanggal**
min_date = df["Created Date"].min()
max_date = df["Created Date"].max()
date_range = st.sidebar.date_input("📅 Pilih Rentang Tanggal", [min_date, max_date], min_value=min_date, max_value=max_date)

# **👤 Sidebar - Pilih Support**
support_filter = st.sidebar.selectbox("👤 Pilih Support:", ["All"] + df["Assign To"].dropna().unique().tolist(), key="support_select_sidebar")

# **📌 Filter Data berdasarkan pilihan**
df_filtered = df[(df["Created Date"] >= date_range[0]) & (df["Created Date"] <= date_range[1])]

if support_filter != "All":
    df_filtered = df_filtered[df_filtered["Assign To"] == support_filter]

# **🔄 Pengaturan Layout agar Sidebar tidak terlalu besar**
col_sidebar, col_main = st.columns([1, 3])  # Sidebar lebih kecil, konten lebih besar

with col_sidebar:
    selected_sheet = st.selectbox("📄 Pilih Sheet:", sheet_names, key="sheet_select_main")
    date_range = st.date_input("📅 Pilih Rentang Tanggal", [min_date, max_date], min_value=min_date, max_value=max_date, key="date_select_main")
    support_filter = st.selectbox("👤 Pilih Support:", ["All"] + df["Assign To"].dropna().unique().tolist(), key="support_select_main")
    
with col_main:
    st.title("📊 Dashboard Tiket Support")
    col1, col2, col3 = st.columns(3)
    col1.metric(label="🎟️ Total Tiket", value=len(df_filtered))
    col2.metric(label="✅ Tiket Selesai", value=len(df_filtered[df_filtered["Condition"] == "FINISH"]))
    col3.metric(label="⏳ Tiket Belum Selesai", value=len(df_filtered[df_filtered["Condition"] == "NOT FINISH"]))

    st.subheader("📌 Performa Penyelesaian Tiket")
    finish_percentage = (len(df_filtered[df_filtered["Condition"] == "FINISH"]) / len(df_filtered)) * 100 if len(df_filtered) > 0 else 0
    st.progress(finish_percentage / 100)
    st.write(f"✅ **{finish_percentage:.2f}% tiket telah selesai** dari total {len(df_filtered)} tiket.")

    st.markdown("### 📝 Data Tiket yang Difilter")
    with st.expander("📋 Klik untuk melihat data tiket yang difilter"):
        st.dataframe(df_filtered)

    st.subheader("📈 Statistik Tiket Per Hari")
    if not df_filtered.empty:
        df_summary = df_filtered.groupby("Created Date").agg(
            Total_Tiket=("Ticket Number", "count"),
            Total_Finish=("Condition", lambda x: (x == "FINISH").sum())
        ).reset_index()

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 📊 Grafik Bar Chart (Total Tiket vs Tiket Selesai)")
            fig_bar = px.bar(
                df_summary,
                x="Created Date",
                y=["Total_Tiket", "Total_Finish"],
                labels={"value": "Jumlah Tiket", "Created Date": "Tanggal"},
                title="Total Tiket vs Tiket Selesai (Bar Chart)",
                barmode="group"
            )
            fig_bar.update_xaxes(type="category")
            st.plotly_chart(fig_bar)

        with col2:
            st.markdown("### 📈 Grafik Line Chart (Total Tiket vs Tiket Selesai)")
            fig_line = px.line(
                df_summary,
                x="Created Date",
                y=["Total_Tiket", "Total_Finish"],
                markers=True,
                title="Total Tiket vs Tiket Selesai (Line Chart)"
            )
            fig_line.update_xaxes(type="category")
            st.plotly_chart(fig_line)
    else:
        st.warning("⚠️ Tidak ada data yang dapat ditampilkan dalam grafik untuk filter yang dipilih.")

# **🔄 Tombol Refresh Data**
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
