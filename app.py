# === FUNGSI MODULAR ===

def load_data(url):
    df = pd.read_csv(url)
    df.rename(columns=lambda x: x.strip(), inplace=True)
    return df

def filter_data(df, start_date, end_date, agent_filter, service_filter=None):
    df_filtered = df.copy()
    if start_date and end_date:
        if "Created" in df_filtered.columns:
            df_filtered = df_filtered[
                (df_filtered["Created"] >= start_date) &
                (df_filtered["Created"] <= end_date)
            ]
    if agent_filter != "All":
        df_filtered = df_filtered[df_filtered["Assign To"] == agent_filter]
    if service_filter and service_filter != "All":
        if "Services" in df_filtered.columns:
            df_filtered = df_filtered[df_filtered["Services"] == service_filter]
    return df_filtered

def calculate_ticket_metrics(df_filtered):
    total_tiket = len(df_filtered)
    selesai_24_jam = len(df_filtered[df_filtered["Durasi (Jam)"] <= 24])
    selesai_lebih_24_jam = len(df_filtered[df_filtered["Durasi (Jam)"] > 24])
    belum_selesai = len(df_filtered[df_filtered["Status"] != "Finish"]) if "Status" in df_filtered.columns else 0
    avg_durasi = df_filtered["Durasi (Jam)"].mean() if "Durasi (Jam)" in df_filtered.columns else None
    return total_tiket, selesai_24_jam, selesai_lebih_24_jam, belum_selesai, avg_durasi

def calculate_visit_metrics(df_visit_filtered):
    total_visit = len(df_visit_filtered)
    selesai_hari_h = len(df_visit_filtered[df_visit_filtered["Schedule Date"] == df_visit_filtered["Visit Date"]])
    selesai_setelah_hari_h = len(df_visit_filtered[df_visit_filtered["Schedule Date"] < df_visit_filtered["Visit Date"]])
    belum_dikunjungi = len(df_visit_filtered[df_visit_filtered["Status"] != "Visited"]) if "Status" in df_visit_filtered.columns else 0
    return total_visit, selesai_hari_h, selesai_setelah_hari_h, belum_dikunjungi

def calculate_efftime_metrics(df_efftime_filtered, support_filter):
    df_valid = df_efftime_filtered[df_efftime_filtered["Status"] == "OK"].copy()

    if support_filter != "All":
        df_valid = df_valid[df_valid["Assign To"] == support_filter]

    total_days, total_eff_hours, total_un_eff_hours = calculate_efftime_metrics(df_efftime_filtered, support_filter)

def render_tab_tiket(df_filtered, layanan, service_options, total_tiket, selesai_24_jam, selesai_lebih_24_jam, belum_selesai, avg_durasi):
    st.title("📊 PERFORMANCE DASHBOARD")
    st.subheader("📌 Performa Penyelesaian Tiket")
    layanan = st.radio("⚙️ Pilih Jenis Services:", options=service_options, key="layanan")

    progress = total_tiket - belum_selesai
    progress_percentage = (progress / total_tiket) * 100 if total_tiket > 0 else 0
    st.progress(progress_percentage / 100)
    st.success(f"✅ **{progress_percentage:.2f}% tiket telah selesai** dari total {total_tiket} tiket.")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🎟️ Total Tiket", total_tiket)
    col2.metric("✅ Tiket Selesai ≤ 24 Jam", selesai_24_jam)
    col3.metric("📋 Tiket Selesai > 24 Jam", selesai_lebih_24_jam)
    col4.metric("⏳ Tiket Belum Selesai", belum_selesai)

    if avg_durasi:
        st.metric("🕒 Rata-rata Durasi Pengerjaan", f"{avg_durasi:.2f} Jam")

    st.subheader("📊 Grafik Bar Chart (Total Tiket vs Tiket Selesai)")
    if not df_filtered.empty:
        # Step 1: Pastikan kolom Created sudah datetime
        df_filtered["Created"] = pd.to_datetime(df_filtered["Created"], errors="coerce")

        # Step 2: Buat kolom hanya tanggal saja untuk grouping
        df_filtered["Created_Date"] = df_filtered["Created"].dt.date  # ← penting!

        # Step 3: Group by Created_Date (bukan Created full datetime)
        df_summary = df_filtered.groupby("Created_Date").agg(
            Total_Tiket=("Created", "count"),
            Selesai_24_Jam=("Durasi (Jam)", lambda x: (x <= 24).sum())).reset_index()
            
        # Konversi ulang Created_Date agar bisa pakai .dt
        df_summary["Created_Date"] = pd.to_datetime(df_summary["Created_Date"], errors="coerce")

        # Format string
        df_summary["Created Display"] = df_summary["Created_Date"].dt.strftime("%Y-%m-%d")
       
        fig_bar = px.bar(
            df_summary,
            x="Created Display",
            y=["Total_Tiket", "Selesai_24_Jam"],
            color_discrete_sequence=get_default_colors(),
            barmode="group",
            labels={"Created": "Tanggal", "value": "Jumlah Tiket"},
            title="Total Tiket vs Tiket Selesai ≤ 24 Jam (Bar Chart)")
        # Penting! ubah x-axis ke mode kategori agar tanggal kosong disembunyikan
        fig_bar.update_xaxes(type="category", tickangle=45)
        st.plotly_chart(fig_bar)

    st.subheader("🥇 Distribusi Penyelesaian Tiket")
    colors = get_default_colors()
    labels = ["Tiket ≤ 24 Jam", "Tiket > 24 Jam"]
    values = [selesai_24_jam, selesai_lebih_24_jam]

    fig_pie = go.Figure(data=[go.Pie(
        labels=labels, 
        values=values, 
        hole=0.4,
        textinfo="percent+label",
        marker=dict(colors=colors[:2])
    )])

    fig_pie.update_layout(
        title_text="Distribusi Tiket Bedasarkan Durasi Penyelesaian",
        annotations=[dict(text=f"{total_tiket} Tiket", x=0.5, y=0.5, font_size=16, showarrow=False)]
    )

    st.plotly_chart(fig_pie)

    # Klasifikasi performa tiket
    if total_tiket > 0:
        selesai_percent = (selesai_24_jam / total_tiket) * 100
        if selesai_percent >= 90:
            kategori = "🟢 Sangat Baik"
        elif selesai_percent >= 75:
            kategori = "🟡 Baik"
        elif selesai_percent >= 60:
            kategori = "🟠 Cukup"
        else:
            kategori = "🔴 Kurang Baik"
        st.info(f"**Klasifikasi Durasi Penyelesaian Tiket:** {kategori} ({selesai_percent:.1f}%)")


    with st.expander("📋 Klik untuk melihat data tiket yang difilter"):
        df_display = df_filtered.copy()
        def format_durasi(jam_float):
            if pd.isnull(jam_float):
                return "-"
            total_detik = int(jam_float * 3600)
            jam = total_detik // 3600
            menit = (total_detik % 3600) // 60
            detik = total_detik % 60
            return f"{jam} Jam {menit} Menit {detik} Detik"

        df_display["Durasi (Jam)"] = df_display["Durasi (Jam)"].apply(format_durasi)
        display_columns = [
            "Ticket Number", "Created", "Finish", "Assign To", 
            "Services", "Status", "Durasi (Jam)"]
        available_cols = [col for col in display_columns if col in df_display.columns]
        st.dataframe(df_display[available_cols])

def render_tab_visit(df_visit_filtered):
    st.title("📋 PERFORMANCE DASHBOARD")
    st.subheader("📊 Grafik Visit Per Hari")

    # Konversi kolom tanggal ke datetime
    df_visit_filtered["Schedule Date"] = pd.to_datetime(df_visit_filtered["Schedule Date"], errors='coerce')
    df_visit_filtered["Visit Date"] = pd.to_datetime(df_visit_filtered["Visit Date"], errors='coerce')

    # Pilih Visit Type (selectbox)
    visit_types = df_visit_filtered["Visit Type"].dropna().unique().tolist()
    visit_types.sort()
    visit_types.insert(0, "All")
    visit_type_selected = st.selectbox("📌 Pilih Visit Type (Selectbox)", options=visit_types)

    if visit_type_selected != "All":
        df_visit_filtered = df_visit_filtered[df_visit_filtered["Visit Type"] == visit_type_selected]

    # Hitung durasi pengerjaan
    df_visit_filtered["Durasi (Jam)"] = (df_visit_filtered["Visit Date"] - df_visit_filtered["Schedule Date"]).dt.total_seconds() / 3600

    # Hitung metrik
    total_visit = df_visit_filtered[df_visit_filtered["Status"] == "Visited"].shape[0]
    not_visited = df_visit_filtered[df_visit_filtered["Status"] == "Not Visited"].shape[0]
    selesai_hari_h_visit = df_visit_filtered[(df_visit_filtered["Status"] == "Visited") & (df_visit_filtered["Durasi (Jam)"] <= 24)].shape[0]
    selesai_setelah_hari_h_visit = df_visit_filtered[(df_visit_filtered["Status"] == "Visited") & (df_visit_filtered["Durasi (Jam)"] > 24)].shape[0]

    # Tampilkan metrik
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("✅ Total Visit", total_visit)
    col2.metric("❌ Not Visited", not_visited)
    col3.metric("📅 Visit Hari H", selesai_hari_h_visit)
    col4.metric("🕒 Visit > Hari H", selesai_setelah_hari_h_visit)

    st.subheader("📈 Grafik Visit Hari H")
    # Filter hanya data yang visited
    df_visited_only = df_visit_filtered[df_visit_filtered["Status"] == "Visited"]
    df_visited_only["Schedule_Date_Hari"] = df_visited_only["Schedule Date"].dt.date

    if not df_visited_only.empty:
        # Grouping grafik
        df_summary_visit = df_visited_only.groupby("Schedule_Date_Hari").agg({
            "Visit Date": "count",
            "Durasi (Jam)": lambda x: (x <= 24).sum()
        }).reset_index()

        df_summary_visit["Schedule_Date_Display"] = pd.to_datetime(df_summary_visit["Schedule_Date_Hari"]).dt.strftime("%Y-%m-%d")
        df_summary_visit.rename(columns={"Visit Date": "Total_Visit", "Durasi (Jam)": "Finish_Hari_H"}, inplace=True)

        fig_visit = px.bar(
            df_summary_visit,
            x="Schedule_Date_Display",
            y=["Total_Visit", "Finish_Hari_H"],
            barmode="group",
            color_discrete_sequence=px.colors.qualitative.Set2[:2],
            title="Total Visit vs Visit Selesai Hari H",
            labels={"value": "Jumlah Visit", "variable": "Kategori"}
        )
        fig_visit.update_xaxes(type="category", tickangle=45)
        st.plotly_chart(fig_visit)

    # Pie Chart
    st.subheader("🟠 Distribusi Penyelesaian Visit")

    labels = ["Finish form Visit Hari H", "Finish form Visit H +1", "Belum Menyelesaikan Form Visit"]
    values = [selesai_hari_h_visit, selesai_setelah_hari_h_visit, not_visited]

    colors = px.colors.qualitative.Set2

    fig_pie = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.4,
        textinfo="percent+label",
        marker=dict(colors=colors)
    )])

    fig_pie.update_layout(
        title_text="Distribusi Visit Berdasarkan Hari Pengisian",
        annotations=[dict(text=str(total_visit + not_visited), x=0.5, y=0.5, font_size=16, showarrow=False)]
    )
    st.plotly_chart(fig_pie)
    # Klasifikasi performa visit
    total_semua = total_visit + not_visited
    if total_semua > 0:
        selesai_hari_h_percent = (selesai_hari_h_visit / total_semua) * 100
        if selesai_hari_h_percent >= 90:
            kategori_visit = "🟢 Sangat Baik"
        elif selesai_hari_h_percent >= 75:
            kategori_visit = "🟡 Baik"
        elif selesai_hari_h_percent >=60:
            kategori_visit = "🟠 Cukup"
        else:
            kategori_visit = "🔴 Kurang"
        st.info(f"**Klasifikasi Penyelesaian Visit:** {kategori_visit} ({selesai_hari_h_percent:.1f}%)")


    # Tabel data
    st.subheader("📋 Data Visit")
    display_columns = ["Schedule Date", "Visit Date", "Assign To", "Visit Type", "Status", "Durasi (Jam)"]

    with st.expander("Klik untuk melihat data visit yang difilter"):
        st.dataframe(df_visit_filtered[display_columns])

def render_tab_csat(df_csat_filtered, support_filter):
    st.title("📊 PERFORMANCE DASHBOARD")
    st.subheader("📊 Analisis CSAT")

    if df_csat_filtered is not None and not df_csat_filtered.empty:
        df_csat_avg = df_csat_filtered.groupby("Assign To")["Rating"].mean().reset_index()
        fig_csat_avg = px.bar(
            df_csat_avg,
            x="Assign To",
            y="Rating",
            title="📊 Rata-rata Skor CSAT per Agent",
            labels={"Rating": "Rata-rata CSAT"},
            color="Rating",
            color_continuous_scale="blues"
        )
        st.plotly_chart(fig_csat_avg)

        df_csat_trend = df_csat_filtered.groupby("Created")["Rating"].mean().reset_index()
        fig_csat_trend = px.line(
            df_csat_trend,
            x="Created",
            y="Rating",
            title="📈 Tren Kepuasan Pelanggan (Rata-rata CSAT per Hari)",
            labels={"Created": "Tanggal", "Rating": "Rata-rata CSAT"},
            markers=True
        )
        st.plotly_chart(fig_csat_trend)

        st.markdown("----")
        if support_filter == "All":
            st.subheader("🏆 Top 5 Agent dengan CSAT Tertinggi")
            df_top_5 = df_csat_filtered.groupby("Assign To")["Rating"].mean().nlargest(5).reset_index()
            fig_top_5 = px.bar(
                df_top_5,
                x="Rating",
                y="Assign To",
                text="Rating",
                orientation="h",
                title="Top 5 Agent dengan CSAT Tertinggi",
                color="Rating",
                color_continuous_scale="greens",
                labels={"Rating": "Rata-rata CSAT", "Assign To": "Agent"},
                category_orders={"Assign To": df_top_5.sort_values("Rating", ascending=False)["Assign To"]}
            )

            fig_top_5.update_traces(texttemplate='%{text:.2f}', textposition='inside')
            st.plotly_chart(fig_top_5, use_container_width=True)

            st.subheader("⚠️ Bottom 5 Agent dengan CSAT Terendah")
            df_bottom_5 = df_csat_filtered.groupby("Assign To")["Rating"].mean().nsmallest(5).reset_index()
            fig_bottom_5 = px.bar(
                df_bottom_5,
                x="Rating",
                y="Assign To",
                text="Rating",
                orientation="h",
                title="Bottom 5 Agent dengan CSAT Terendah",
                color="Rating",
                color_continuous_scale="reds",
                labels={"Rating": "Rata-rata CSAT", "Assign To": "Agent"},
                category_orders={"Assign To": df_bottom_5.sort_values("Rating", ascending=False)["Assign To"]}
            )
            fig_bottom_5.update_traces(texttemplate='%{text:.2f}', textposition='inside')
            st.plotly_chart(fig_bottom_5, use_container_width=True)
        else:
            st.warning("⚠️ Grafik ini hanya ditampilkan jika Agent yang dipilih adalah 'All'.")
    else:
        st.warning("🔍 Tidak ada data CSAT dalam rentang tanggal dan filter yang dipilih.")

def render_tab_activity(df_efftime_filtered, support_filter):
    st.title("⏱️ Effective vs Un-effective Time")

    if df_efftime_filtered is not None and not df_efftime_filtered.empty:
        df_all_for_display = df_efftime_filtered.copy()
        df_valid = df_efftime_filtered[df_efftime_filtered["Status"] == "OK"].copy()

        if support_filter != "All":
            df_valid = df_valid[df_valid["Assign To"] == support_filter]
            df_all_for_display = df_all_for_display[df_all_for_display["Assign To"] == support_filter]

        if not df_valid.empty:
            show_negative = st.checkbox("Tampilkan nilai negatif un-effective time", value=False)

            # Perhitungan / pemrosesan nilai negatif
            df_efftime_filtered["Un-effective Time"] = df_efftime_filtered["Un-effective Time"].apply(
                lambda x: x if show_negative else max(x,timedelta(0))
            )

            df_valid["Schedule Date"] = pd.to_datetime(df_valid["Schedule Date"], errors='coerce').dt.date
            df_valid["Duration"] = pd.to_timedelta(df_valid["Duration"], errors='coerce')

            total_days = df_valid["Schedule Date"].nunique()
            standard_duration = 9
            total_duration = df_valid["Duration"].sum()
            total_eff_hours = total_duration.total_seconds() / 3600 if pd.notnull(total_duration) else 0
            total_duration_hours = total_days * standard_duration
            total_un_eff_hours = total_duration_hours - total_eff_hours
            if not show_negative:
                total_un_eff_hours = max(0, total_un_eff_hours)

            col1, col2, col3 = st.columns(3)
            col1.metric("📅 Durasi Kerja", f"{total_days} Hari")
            col2.metric("✅ Effective Time", f"{total_eff_hours:.2f} Jam")
            col3.metric("⏳ Un-effective Time", f"{total_un_eff_hours:.2f} Jam")

            st.markdown("### 🔍 Simulasi Berdasarkan Status = 'OK'")
            st.markdown(f"""
            - **Durasi Kerja (Hari)**: `{total_days}`
            - ✅ **Total Duration (Jam)**: `{total_eff_hours:.2f}` `(Standar kerja: 9 jam/hari)`
            - ✅ **Total Effective Time (Jam)**: `{total_eff_hours:.2f}` `(Dihitung berdasarkan lama pengerjaan di Outlet)`
            - ⏳ **Total Un-effective Time (Jam)**: `{total_un_eff_hours:.2f}` `(Jam Kerja dikurangi Effective Time)`
            """)

            st.markdown("### 🧾 Klik untuk melihat data aktivitas detail:")

            def highlight_non_ok(row):
                color = 'background-color: #ffe6e6' if row["Status"] != "OK" else ''
                return [color]*len(row)

            def format_timedelta(td):
                if pd.isna(td):
                    return "-"
                total_seconds = td.total_seconds()
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)
                return f"{hours} jam {minutes} menit"

            df_all_for_display["Duration"] = pd.to_timedelta(df_all_for_display["Duration"], errors="coerce")
            df_all_for_display["Un-effective Time"] = pd.to_timedelta(df_all_for_display["Un-effective Time"], errors="coerce")
            df_all_for_display["Duration"] = df_all_for_display["Duration"].apply(format_timedelta)
            df_all_for_display["Un-effective Time"] = df_all_for_display["Un-effective Time"].apply(format_timedelta)

            styled_table = df_all_for_display.style.apply(highlight_non_ok, axis=1)
            with st.expander("📄 Klik untuk melihat data aktivitas detail"):
                st.dataframe(styled_table)

        else:
            st.warning("Tidak ada data aktivitas dengan status **OK** pada rentang tanggal & agent yang dipilih.")
    else:
        st.warning("Data kosong setelah difilter. Coba sesuaikan rentang tanggal atau sheet.")

def render_tabs(tabs, tab_labels, selected_sheet, df_filtered, df_visit_filtered, df_csat_filtered, df_efftime_filtered, layanan, service_options, support_filter):
    for i, tab in enumerate(tabs):
        with tab:
            tab_label = tab_labels[i]

            if st.session_state.active_tab != tab_label:
                st.session_state.active_tab = tab_label

            if st.session_state.active_tab == tab_label:
                if tab_label == "📄 Data Tiket":
                    total_tiket, selesai_24_jam, selesai_lebih_24_jam, belum_selesai, avg_durasi = calculate_ticket_metrics(df_filtered)
                    render_tab_tiket(df_filtered, layanan, service_options, total_tiket, selesai_24_jam, selesai_lebih_24_jam, belum_selesai, avg_durasi)

                elif tab_label == "🗓️ Data Visit" and selected_sheet == "SUPPORT":
                    if df_visit_filtered is not None:
                        total_visit, selesai_hari_h_visit, selesai_setelah_hari_h_visit, belum_dikunjungi = calculate_visit_metrics(df_visit_filtered)
                        render_tab_visit(df_visit_filtered)

                elif tab_label == "⭐ Data CSAT" and selected_sheet == "CARELINE":
                    render_tab_csat(df_csat_filtered, support_filter)

                elif tab_label == "⏱️ Activity" and selected_sheet == "SUPPORT":
                    render_tab_activity(df_efftime_filtered, support_filter)


# === KODE UTAMA ===
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
from datetime import timedelta

# 🎨 Palet Warna Kontras untuk Konsistensi Visual
def get_default_colors():
    return ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

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

# Format dan Konversi
if "Ticket Number" in df.columns:
    df["Ticket Number"] = df["Ticket Number"].astype(str)

if "Created" in df.columns:
    df["Created"] = pd.to_datetime(df["Created"], errors='coerce', dayfirst=True)
    df["Created Display"] = df["Created"].dt.strftime("%d/%m/%Y %H:%M:%S")
    df["Created_Date"] = df["Created"].dt.date  # <-- Tambahkan ini

if "Finish" in df.columns:
    df["Finish"] = pd.to_datetime(df["Finish"], errors='coerce', dayfirst=True)
    df["Finish Display"] = df["Finish"].dt.strftime("%d/%m/%Y %H:%M:%S")

# Durasi
if "Created" in df.columns and "Finish" in df.columns:
    df["Durasi (Jam)"] = (df["Finish"] - df["Created"]).dt.total_seconds() / 3600
  

# **📊 Sidebar - Pilih Rentang Tanggal**
min_date = df["Created"].min() if "Created" in df.columns else df["Schedule Date"].min()
max_date = df["Created"].max() if "Created" in df.columns else df["Schedule Date"].max()

min_date = pd.to_datetime(min_date)
max_date = pd.to_datetime(max_date)

date_range = st.sidebar.date_input("📅 Pilih Rentang Tanggal", [min_date, max_date], min_value=min_date, max_value=max_date)

# Tangani kasus jika hanya satu tanggal dipilih
if isinstance(date_range, (list,tuple)):
    if len(date_range) == 2:
        start_date, end_date = date_range
    elif len(date_range) == 1:
        start_date = end_date = date_range[0]
    else:
        start_date = end_date = None
else:
    start_date = end_date = None

if start_date and end_date:
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)


# **👤 Sidebar - Pilih Support**
support_options = sorted(df["Assign To"].dropna().unique().tolist())
support_filter = st.sidebar.selectbox("👤 Pilih Agent:", ["All"] + support_options)


# **📌 Filter Data berdasarkan pilihan**
# Inisialisasi df_filtered
df_filtered = df.copy()

# Pastikan user memilih 2 tanggal (start & end)
if "Created" in df.columns and isinstance(date_range, tuple) and len(date_range) == 2:
    start_date = pd.to_datetime(date_range[0])
    end_date = pd.to_datetime(date_range[1])

    df_filtered = df_filtered[
        (df_filtered["Created"] >= start_date) &
        (df_filtered["Created"] <= end_date)]

if support_filter != "All":
    df_filtered = df_filtered[df_filtered["Assign To"] == support_filter]

# Inisialisasi session_state agar tidak error
if "layanan" not in st.session_state:
    st.session_state["layanan"] = "All"

	
# **📌 Jika Sheet CARELINE, Load Sheet CSAT Juga**
df_csat_filtered = None
if selected_sheet == "CARELINE":
    CSAT_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=CSAT"
    df_csat = load_data(CSAT_URL)

    # **Pastikan df_csat tidak kosong sebelum diproses**
    if not df_csat.empty:
        # Konversi format tanggal
        if "Created" in df_csat.columns:
            df_csat["Created"] = pd.to_datetime(df_csat["Created"], errors='coerce', dayfirst=True)

        # Pastikan "Assign To" dan "Rating" ada dalam dataset
        if "Assign To" in df_csat.columns and "Rating" in df_csat.columns:
            df_csat["Rating"] = pd.to_numeric(df_csat["Rating"], errors="coerce")  # Pastikan angka
            
            # **Filter berdasarkan rentang tanggal**
            df_csat_filtered = df_csat.copy()

            if start_date and end_date:
                df_csat_filtered = df_csat_filtered[
                (df_csat_filtered["Created"] >= start_date) &
                (df_csat_filtered["Created"] <= end_date)]
            else:
                st.warning("📅 Silakan pilih rentang tanggal lengkap (2 tanggal).")


            # **Filter berdasarkan agent jika dipilih**
            if support_filter != "All":
                df_csat_filtered = df_csat_filtered[df_csat_filtered["Assign To"] == support_filter]

            # **Agregasi Data CSAT berdasarkan rating**
            df_csat_summary = df_csat_filtered.groupby(["Assign To", "Rating"]).size().unstack(fill_value=0)


# **📌 Jika Sheet SUPPORT, Load Sheet VISIT Juga**
df_visit_filtered = None
if selected_sheet == "SUPPORT":
    VISIT_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=VISIT"
    df_visit = load_data(VISIT_URL)
    
    if "Schedule Date" in df_visit.columns:
        df_visit["Schedule Date"] = pd.to_datetime(df_visit["Schedule Date"], errors='coerce', dayfirst=True)
    if "Visit Date" in df_visit.columns:
        df_visit["Visit Date"] = pd.to_datetime(df_visit["Visit Date"], errors='coerce', dayfirst=True)
    
    df_visit_filtered = df_visit.copy()
    if start_date and end_date:
        df_visit_filtered = df_visit_filtered[
            (df_visit_filtered["Schedule Date"] >= start_date) &
            (df_visit_filtered["Schedule Date"] <= end_date)]
    
    if "Schedule Date" in df_visit.columns:
        df_visit["Schedule Date"] = pd.to_datetime(df_visit["Schedule Date"], errors="coerce", dayfirst=True)

    # Konversi nilai date_input ke datetime64 agar cocok dengan kolom Schedule Date
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date = pd.to_datetime(date_range[0])
        end_date = pd.to_datetime(date_range[1]).replace(hour=23, minute=59, second=59)

        df_filtered = df_filtered[
            (df_filtered["Created"] >= start_date) &
            (df_filtered["Created"] <= end_date)]
    else:
        st.warning("📅 Silakan pilih rentang tanggal lengkap (2 tanggal).")


    if support_filter != "All":
        df_visit_filtered = df_visit_filtered[df_visit_filtered["Assign To"] == support_filter]

df_efftime_filtered = None		
# 📄 Load Data SUPPORT_ACTIVITY
if selected_sheet == "SUPPORT":
    ACTIVITY_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=SUPPORT_ACTIVITY"
    df_efftime = load_data(ACTIVITY_URL)
	
	# Tambahkan kolom Status untuk menandai jika Check In / Check Out kosong
    df_efftime["Status"] = df_efftime.apply(
    lambda row: "Missing Check In/Out" if pd.isna(row.get("Check In")) or pd.isna(row.get("Check Out")) else "OK",
    axis=1
    )

    # Format kolom datetime dan duration
    if "Schedule Date" in df_efftime.columns:
        df_efftime["Schedule Date"] = pd.to_datetime(df_efftime["Schedule Date"], errors='coerce', dayfirst=True)
		
    if "Duration" in df_efftime.columns:
        df_efftime["Duration"] = pd.to_timedelta(df_efftime["Duration"], errors='coerce')
		
    if "Un-effective Time" in df_efftime.columns:
        df_efftime["Un-effective Time"] = pd.to_timedelta(df_efftime["Un-effective Time"], errors='coerce')

		
	# ✅ Tambahkan kolom Status berdasarkan Check In / Check Out
    df_efftime["Status"] = df_efftime.apply(
        lambda row: "Missing" if pd.isna(row["Check In"]) or pd.isna(row["Check Out"]) else "OK",
        axis=1
    )

    # Hitung kolom 'Un-effective Time'
    standard_duration = pd.to_timedelta("9:00:00")
    df_efftime["Un-effective Time"] = standard_duration - df_efftime["Duration"]

    # Filter berdasarkan tanggal dan support_filter
    df_efftime_filtered = df_efftime.copy()

    # Cek apakah start_date dan end_date valid (bukan None)
    if start_date is not None and end_date is not None:
        df_efftime_filtered = df_efftime_filtered[
            (df_efftime_filtered["Schedule Date"] >= pd.to_datetime(start_date)) &
            (df_efftime_filtered["Schedule Date"] <= pd.to_datetime(end_date))]
    else:
        st.warning("📅 Silakan pilih rentang tanggal lengkap (2 tanggal).")

    if support_filter != "All":
        df_efftime_filtered = df_efftime_filtered[df_efftime_filtered["Assign To"] == support_filter]

# Diasumsikan df_filtered sudah difilter tanggal & agent sebelumnya
# service_options dibuat berdasarkan df_filtered saat ini
if "Services" in df_filtered.columns:
    service_options = ["All"] + sorted(df_filtered["Services"].dropna().unique().tolist())

# Filter Agent
if support_filter != "All":
    df_filtered = df_filtered[df_filtered["Assign To"] == support_filter]

layanan = st.session_state.get("layanan", "All")

if layanan != "All":
    df_filtered = df_filtered[df_filtered["Services"] == layanan]

# **🖥️ Dashboard Tampilan**
if selected_sheet == "SUPPORT":
    tab_labels = ["📄 Data Tiket", "🗓️ Data Visit", "⏱️ Activity"]
elif selected_sheet == "CARELINE":
    tab_labels = ["📄 Data Tiket", "⭐ Data CSAT"]
else:
    tab_labels = ["📄 Data Tiket"]

if "last_filter" not in st.session_state:
    st.session_state.last_filter = (selected_sheet, start_date, end_date, support_filter)

current_filter = (selected_sheet, start_date, end_date, support_filter)

if "last_filter" not in st.session_state:
    st.session_state.last_filter = current_filter

if "active_tab" not in st.session_state or st.session_state.active_tab not in tab_labels:
    st.session_state.active_tab = tab_labels[0]

# Update hanya jika filter berubah
if st.session_state.last_filter != current_filter:
    # Jangan ubah active_tab jika masih valid
    if st.session_state.active_tab not in tab_labels:
        st.session_state.active_tab = tab_labels[0]

    # Simpan filter baru ke session_state
    st.session_state.last_filter = current_filter

tabs = st.tabs(tab_labels)

render_tabs(tabs, tab_labels, selected_sheet, df_filtered, df_visit_filtered, df_csat_filtered, df_efftime_filtered, layanan, service_options, support_filter)
			
# **🔄 Tombol Refresh Data**
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
