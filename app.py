import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# **📄 Konfigurasi Layout**
st.set_page_config(layout="wide", initial_sidebar_state="collapsed")

# **🔗 Link ke Google Sheets**
SHEET_ID = "1Nev5-cSUKDlU4z3glFC90VhJjxv09njFlbJWK5G4oOc"
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
    df.rename(columns=lambda x: x.strip(), inplace=True)
    return df

df = load_data(CSV_URL)

# **📌 Format Data**
if "Ticket Number" in df.columns:
    df["Ticket Number"] = df["Ticket Number"].astype(str)
if "Created" in df.columns:
    df["Created"] = pd.to_datetime(df["Created"], errors='coerce', dayfirst=True).dt.date
if "Finish" in df.columns:
    df["Finish"] = pd.to_datetime(df["Finish"], errors='coerce', dayfirst=True).dt.date
if "Schedule Date" in df.columns:
    df["Schedule Date"] = pd.to_datetime(df["Schedule Date"], errors='coerce', dayfirst=True).dt.date
if "Visit Date" in df.columns:
    df["Visit Date"] = pd.to_datetime(df["Visit Date"], errors='coerce', dayfirst=True).dt.date

# **📊 Sidebar - Pilih Rentang Tanggal**
min_date = df["Created"].min() if "Created" in df.columns else df["Schedule Date"].min()
max_date = df["Created"].max() if "Created" in df.columns else df["Schedule Date"].max()
date_range = st.sidebar.date_input("📅 Pilih Rentang Tanggal", [min_date, max_date], min_value=min_date, max_value=max_date)

# **👤 Sidebar - Pilih Support**
support_filter = st.sidebar.selectbox("👤 Pilih Agent:", ["All"] + df["Assign To"].dropna().unique().tolist())

# **📌 Filter Data berdasarkan pilihan**
df_filtered = df.copy()
if "Created" in df.columns:
    df_filtered = df_filtered[(df_filtered["Created"] >= date_range[0]) & (df_filtered["Created"] <= date_range[1])]

if support_filter != "All":
    df_filtered = df_filtered[df_filtered["Assign To"] == support_filter]

# **📌 Jika Sheet SUPPORT, Load Sheet VISIT Juga**
df_visit_filtered = None
if selected_sheet == "SUPPORT":
    VISIT_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=VISIT"
    df_visit = load_data(VISIT_URL)
    
    if "Schedule Date" in df_visit.columns:
        df_visit["Schedule Date"] = pd.to_datetime(df_visit["Schedule Date"], errors='coerce', dayfirst=True).dt.date
    if "Visit Date" in df_visit.columns:
        df_visit["Visit Date"] = pd.to_datetime(df_visit["Visit Date"], errors='coerce', dayfirst=True).dt.date
    
    df_visit_filtered = df_visit.copy()
    df_visit_filtered = df_visit_filtered[(df_visit_filtered["Schedule Date"] >= date_range[0]) & (df_visit_filtered["Schedule Date"] <= date_range[1])]

    if support_filter != "All":
        df_visit_filtered = df_visit_filtered[df_visit_filtered["Assign To"] == support_filter]

# **📌 Hitung Metrik Tiket**
total_tiket = len(df_filtered) if df_filtered is not None else 0
selesai_hari_h = len(df_filtered[df_filtered["Created"] == df_filtered["Finish"]]) if df_filtered is not None else 0
selesai_setelah_hari_h = len(df_filtered[df_filtered["Created"] < df_filtered["Finish"]]) if df_filtered is not None else 0
belum_selesai = len(df_filtered[df_filtered["Status"] != "Finish"]) if df_filtered is not None else 0

# **📌 Hitung Metrik Visit (Hanya untuk SUPPORT)**
total_visit, selesai_hari_h_visit, selesai_setelah_hari_h_visit, belum_dikunjungi = 0, 0, 0, 0
if df_visit_filtered is not None:
    total_visit = len(df_visit_filtered)
    selesai_hari_h_visit = len(df_visit_filtered[df_visit_filtered["Schedule Date"] == df_visit_filtered["Visit Date"]])
    selesai_setelah_hari_h_visit = len(df_visit_filtered[df_visit_filtered["Schedule Date"] < df_visit_filtered["Visit Date"]])
    belum_dikunjungi = len(df_visit_filtered[df_visit_filtered["Status"] != "Visited"])


# **🔄 Dashboard Tampilan**
if selected_sheet == "SUPPORT":
    tab1, tab2 = st.tabs(["📋 Data Tiket", "📅 Data Visit"])
else:
    tab1, = st.tabs(["📋 Data Tiket"])

with tab1:
    st.title(f"📊 PERFORMANCE DASHBOARD")
	
	# **📌 Performa Penyelesaian Tiket**
    st.subheader("📌 Performa Penyelesaian Tiket")
    progress = selesai_hari_h + selesai_setelah_hari_h
    progress_percentage = (progress / total_tiket) * 100 if total_tiket > 0 else 0

    st.progress(progress_percentage / 100)
    st.success(f"✅ **{progress_percentage:.2f}% tiket telah selesai** dari total {total_tiket} tiket.")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(label="🎟️ Total Tiket", value=total_tiket)
    col2.metric(label="✅ Tiket Selesai di Hari H", value=selesai_hari_h)
    col3.metric(label="📋 Tiket Selesai Setelah Hari H", value=selesai_setelah_hari_h)
    col4.metric(label="⏳ Tiket Belum Selesai", value=belum_selesai)

    # **📊 Grafik Bar Chart (Total Tiket vs Tiket Selesai)**
    st.subheader("📊 Grafik Bar Chart (Total Tiket vs Tiket Selesai)")
    if not df_filtered.empty:
        df_summary = df_filtered.groupby("Created").agg(
            Total_Tiket=("Created", "count"),
            Total_Finish=("Finish", lambda x: (x == x).sum())  # Hitung tiket selesai
        ).reset_index()

        fig_bar = px.bar(
            df_summary, x="Created", y=["Total_Tiket", "Total_Finish"],
            barmode="group", labels={"Created": "Tanggal", "value": "Jumlah Tiket"},
            title="Total Tiket vs Tiket Selesai (Bar Chart)"
        )
        fig_bar.update_layout(
            legend=dict(title="Variable"),
            xaxis=dict(title="Tanggal"),
            yaxis=dict(title="Jumlah Tiket")
        )
        st.plotly_chart(fig_bar)

    # **📊 Grafik Pie Chart Distribusi Penyelesaian Tiket**
    st.subheader("🥇 Perbandingan Persentase Penyelesaian Tiket (Pie Chart)")
    labels = ["Tiket Selesai di Hari H", "Tiket Selesai Setelah Hari H", "Tiket Belum Selesai"]
    values = [selesai_hari_h, selesai_setelah_hari_h, belum_selesai]
    colors = ["blue", "lightblue", "red"]  # **Konsisten dengan warna legenda**

    fig_pie = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        marker=dict(colors=colors),
        textinfo="percent+label"
    )])

    fig_pie.update_layout(
        title_text="Distribusi Penyelesaian Tiket",
        showlegend=True
    )
    st.plotly_chart(fig_pie)

    # **📋 Data Tiket yang difilter (dengan Expander)**
    with st.expander("📋 Klik untuk melihat data tiket yang difilter"):
        st.dataframe(df_filtered)

# **Data Visit hanya untuk Sheet SUPPORT**
if selected_sheet == "SUPPORT":
    with tab2:
        st.title("📊 PERFORMANCE DASHBOARD")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric(label="📅 Total Visit", value=total_visit)
        col2.metric(label="✅ Form Visit Finish pada hari H", value=selesai_hari_h_visit)
        col3.metric(label="📋 Form Visit Finish tidak dihari H", value=selesai_setelah_hari_h_visit)
        col4.metric(label="⏳ Not Visited", value=belum_dikunjungi)

        # **📊 Grafik Visit Per Hari hanya untuk Data Visit**
        st.subheader("📊 Grafik Visit Per Hari")
        if not df_visit_filtered.empty:
            df_summary_visit = df_visit_filtered.groupby("Schedule Date").size().reset_index(name="Total Visits")
            fig_visit = px.bar(df_summary_visit, x="Schedule Date", y="Total Visits", title="Jumlah Visit Per Hari")
            st.plotly_chart(fig_visit)

        with st.expander("📅 Klik untuk melihat data visit yang difilter"):
            st.dataframe(df_visit_filtered)
			
# **🔄 Tombol Refresh Data**
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
