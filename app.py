import pandas as pd
import streamlit as st
import plotly.express as px

# **🔗 Link CSV dari Google Sheets**
CSV_URL = "https://docs.google.com/spreadsheets/d/GOOGLE_SHEET_ID/gviz/tq?tqx=out:csv"

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
finish_percentage = (finish_tiket / total_tiket) * 100 if total_tiket > 0 else 0

# **📌 Desain Header Dashboard**
st.markdown("<h1 style='text-align: center;'>📊 Dashboard Tiket Support</h1>", unsafe_allow_html=True)

# **📌 Statistik dalam Kartu**
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("<div style='background-color:#ff4757; padding: 20px; border-radius: 10px; text-align: center;'>"
                f"<h3 style='color:white;'>🎟️ Total Tiket</h3><h2 style='color:white;'>{total_tiket:,}</h2></div>",
                unsafe_allow_html=True)
with col2:
    st.markdown("<div style='background-color:#2ed573; padding: 20px; border-radius: 10px; text-align: center;'>"
                f"<h3 style='color:white;'>✅ Tiket Selesai</h3><h2 style='color:white;'>{finish_tiket:,}</h2></div>",
                unsafe_allow_html=True)
with col3:
    st.markdown("<div style='background-color:#ffa502; padding: 20px; border-radius: 10px; text-align: center;'>"
                f"<h3 style='color:white;'>⏳ Tiket Belum Selesai</h3><h2 style='color:white;'>{not_finish_tiket:,}</h2></div>",
                unsafe_allow_html=True)

# **📌 Progress Bar Persentase Tiket Selesai**
st.subheader("📌 Performa Penyelesaian Tiket")
st.progress(finish_percentage / 100)
st.write(f"✅ **{finish_percentage:.2f}% tiket telah selesai** dari total {total_tiket} tiket.")

# **📌 Data Tiket yang Difilter**
st.subheader("📋 Data Tiket yang Difilter")
st.dataframe(df_filtered[["Created Date", "Condition", "Assign To"]])

# **📌 Perhitungan Total Tiket & Tiket FINISH per Hari**
df_summary = df_filtered.groupby("Created Date").agg(
    Total_Tiket=("Ticket Number", "count"),
    Total_Finish=("Condition", lambda x: (x == "FINISH").sum())
).reset_index()

# **📌 Grafik Total Tiket vs Tiket Selesai**
if not df_summary.empty:
    st.subheader("📈 Statistik Tiket Per Hari")

    # **📌 Buat dua kolom untuk grafik**
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📊 Grafik Bar Chart (Total Tiket vs Tiket Selesai)")
        fig_bar = px.bar(
            df_summary,
            x="Created Date",
            y=["Total_Tiket", "Total_Finish"],
            labels={"value": "Jumlah Tiket", "Created Date": "Tanggal"},
            title="Total Tiket vs Tiket Selesai (Bar Chart)",
            barmode="group",
            color_discrete_map={"Total_Tiket": "#3742fa", "Total_Finish": "#2ed573"}
        )
        fig_bar.update_xaxes(type="category")
        fig_bar.update_layout(yaxis_title="Total Tiket", xaxis_title="Tanggal")
        st.plotly_chart(fig_bar)

    with col2:
        st.markdown("### 📈 Grafik Line Chart (Total Tiket vs Tiket Selesai)")
        fig_line = px.line(
            df_summary,
            x="Created Date",
            y=["Total_Tiket", "Total_Finish"],
            markers=True,
            title="Total Tiket vs Tiket Selesai (Line Chart)",
            labels={"value": "Jumlah Tiket", "Created Date": "Tanggal"},
            line_shape="linear"
        )
        fig_line.update_xaxes(type="category")
        fig_line.update_traces(marker=dict(size=8))
        st.plotly_chart(fig_line)
else:
    st.warning("⚠️ Tidak ada data yang dapat ditampilkan dalam grafik untuk filter yang dipilih.")
