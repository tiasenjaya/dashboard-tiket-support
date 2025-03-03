import pandas as pd
import streamlit as st
import plotly.express as px

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
selected_sheet = st.sidebar.selectbox("📄 Pilih Sheet:", sheet_names)

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
st.sidebar.header("📊 Filter Data")
min_date = df["Created Date"].min()
max_date = df["Created Date"].max()
date_range = st.sidebar.date_input("📅 Pilih Rentang Tanggal", [min_date, max_date], min_value=min_date, max_value=max_date)

# **👤 Sidebar - Pilih Support**
support_filter = st.sidebar.selectbox("👤 Pilih Support:", ["All"] + df["Assign To"].dropna().unique().tolist())

# **📌 Filter Data berdasarkan pilihan**
df_filtered = df[(df["Created Date"] >= date_range[0]) & (df["Created Date"] <= date_range[1])]

if support_filter != "All":
    df_filtered = df_filtered[df_filtered["Assign To"] == support_filter]

# **🎟️ Hitung Jumlah Tiket**
total_tiket = len(df_filtered)
finish_tiket = len(df_filtered[df_filtered["Condition"] == "FINISH"])
not_finish_tiket = len(df_filtered[df_filtered["Condition"] == "NOT FINISH"])
finish_percentage = (finish_tiket / total_tiket) * 100 if total_tiket > 0 else 0

# **📊 Tampilkan Statistik di Dashboard**
st.title("📊 Dashboard Tiket Support")
st.markdown("<br>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
col1.metric(label="🎟️ Total Tiket", value=total_tiket)
col2.metric(label="✅ Tiket Selesai", value=finish_tiket)
col3.metric(label="⏳ Tiket Belum Selesai", value=not_finish_tiket)

st.markdown("<br>", unsafe_allow_html=True)
st.subheader("📌 Performa Penyelesaian Tiket")
st.progress(finish_percentage / 100)
st.write(f"✅ **{finish_percentage:.2f}% tiket telah selesai** dari total {total_tiket} tiket.")

# **📋 Data Tiket yang Difilter**
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("### 📝 Data Tiket yang Difilter")

def format_status(status):
    return "✅ FINISH" if status == "FINISH" else "❌ NOT FINISH"

df_filtered["Condition"] = df_filtered["Condition"].apply(format_status)

def highlight_status(row):
    if row["Condition"] == "✅ FINISH":
        return ['background-color: lightgreen'] * len(row)
    else:
        return ['background-color: lightcoral'] * len(row)

styled_df = df_filtered.style.apply(highlight_status, axis=1)

with st.expander("📋 Klik untuk melihat data tiket yang difilter"):
    st.dataframe(styled_df)

# **📈 Perhitungan Total Tiket & Tiket FINISH per Hari**
df_summary = df_filtered.groupby("Created Date").agg(
    Total_Tiket=("Ticket Number", "count"),
    Total_Finish=("Condition", lambda x: (x == "✅ FINISH").sum())
).reset_index()

# **📊 Menampilkan Grafik Total Tiket vs Tiket Selesai**
if not df_summary.empty:
    st.markdown("<br>", unsafe_allow_html=True)
st.subheader("📈 Statistik Tiket Per Hari")

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
