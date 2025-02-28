import pandas as pd
import streamlit as st

# **🔗 Link CSV dari Google Sheets**
CSV_URL = "https://docs.google.com/spreadsheets/d/1Nev5-cSUKDlU4z3glFC90VhJjxv09njFlbJWK5G4oOc/gviz/tq?tqx=out:csv"

# **📥 Baca data dari Google Sheets**
@st.cache_data
def load_data():
    df = pd.read_csv(CSV_URL)
    df["Created Date"] = pd.to_datetime(df["Created Date"], errors='coerce').dt.date
    return df

df = load_data()

# **🛠 Filter Data dengan Streamlit**
st.sidebar.header("📊 Filter Data")
min_date = df["Created Date"].min()
max_date = df["Created Date"].max()
date_range = st.sidebar.date_input("📅 Pilih Rentang Tanggal", [min_date, max_date])

df_filtered = df[(df["Created Date"] >= date_range[0]) & (df["Created Date"] <= date_range[1])]

# **🎟️ Hitung Jumlah Tiket**
total_tiket = len(df_filtered)
finish_tiket = len(df_filtered[df_filtered["Condition"] == "FINISH"])
not_finish_tiket = len(df_filtered[df_filtered["Condition"] == "NOT FINISH"])

# **📊 Tampilkan Data di Dashboard**
st.title("📊 Dashboard Tiket Support")

col1, col2, col3 = st.columns(3)
col1.metric(label="🎟️ Total Tiket", value=total_tiket)
col2.metric(label="✅ Tiket Selesai", value=finish_tiket)
col3.metric(label="⏳ Tiket Belum Selesai", value=not_finish_tiket)

st.subheader("📌 Data Tiket yang Difilter")
st.dataframe(df_filtered)
