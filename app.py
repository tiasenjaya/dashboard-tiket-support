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
    start_date = pd.to_datetime(start_date).date()
    end_date = pd.to_datetime(end_date).date()


# **👤 Sidebar - Pilih Support**
support_filter = st.sidebar.selectbox("👤 Pilih Agent:", ["All"] + df["Assign To"].dropna().unique().tolist())

# **📌 Filter Data berdasarkan pilihan**
df_filtered = df.copy()
if "Created" in df.columns:
    df_filtered = df_filtered[(df_filtered["Created"] >= start_date) & (df_filtered["Created"] <= end_date)]

if support_filter != "All":
    df_filtered = df_filtered[df_filtered["Assign To"] == support_filter]
	
# **📌 Jika Sheet CARELINE, Load Sheet CSAT Juga**
df_csat_filtered = None
if selected_sheet == "CARELINE":
    CSAT_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=CSAT"
    df_csat = load_data(CSAT_URL)

    # **Pastikan df_csat tidak kosong sebelum diproses**
    if not df_csat.empty:
        # Konversi format tanggal
        if "Created" in df_csat.columns:
            df_csat["Created"] = pd.to_datetime(df_csat["Created"], errors='coerce', dayfirst=True).dt.date

        # Pastikan "Assign To" dan "Rating" ada dalam dataset
        if "Assign To" in df_csat.columns and "Rating" in df_csat.columns:
            df_csat["Rating"] = pd.to_numeric(df_csat["Rating"], errors="coerce")  # Pastikan angka
            
            # **Filter berdasarkan rentang tanggal**
            df_csat_filtered = df_csat.copy()
            df_csat_filtered = df_csat_filtered[
                (df_csat_filtered["Created"] >= start_date) & 
                (df_csat_filtered["Created"] <= end_date)
            ]

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
        df_visit["Schedule Date"] = pd.to_datetime(df_visit["Schedule Date"], errors='coerce', dayfirst=True).dt.date
    if "Visit Date" in df_visit.columns:
        df_visit["Visit Date"] = pd.to_datetime(df_visit["Visit Date"], errors='coerce', dayfirst=True).dt.date
    
    df_visit_filtered = df_visit.copy()
    df_visit_filtered = df_visit_filtered[(df_visit_filtered["Schedule Date"] >= start_date) & (df_visit_filtered["Schedule Date"] <= end_date)]

    if support_filter != "All":
        df_visit_filtered = df_visit_filtered[df_visit_filtered["Assign To"] == support_filter]
		
# 📄 Load Data SUPPORT_ACTIVITY
df_visit_filtered = None
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
        df_efftime["Schedule Date"] = pd.to_datetime(df_efftime["Schedule Date"], errors='coerce', dayfirst=True).dt.date
		
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
    df_efftime_filtered = df_efftime_filtered[
        (df_efftime_filtered["Schedule Date"] >= start_date) &
        (df_efftime_filtered["Schedule Date"] <= end_date)
    ]
    if support_filter != "All":
        df_efftime_filtered = df_efftime_filtered[df_efftime_filtered["Assign To"] == support_filter]


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


# **🖥️ Dashboard Tampilan**
if selected_sheet == "SUPPORT":
    tab1, tab2, tab4 = st.tabs(["📄 Data Tiket", "📅 Data Visit", "⏱️ Activity"])
elif selected_sheet == "CARELINE":
    tab1, tab3 = st.tabs(["📋 Data Tiket", "⭐ Data CSAT"])
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

# **Pastikan hanya CARELINE yang menampilkan grafik CSAT**
# **Pastikan grafik CSAT hanya muncul di Tab Data CSAT (bukan di Data Tiket)**
if selected_sheet == "CARELINE":
    with tab3:
        st.subheader("📊 Analisis CSAT")

        if not df_csat_filtered.empty:
            # 🎯 1. Rata-rata CSAT per Agent
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

            # 📈 2. Melihat Tren Naik Turunnya Kepuasan Pelanggan (Line Chart)
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

            # 🏆 3. Top 5 & Bottom 5 Agent Berdasarkan Rata-rata CSAT
            # **Pastikan hanya CARELINE dan hanya di tab3 (Data CSAT)**

if selected_sheet == "CARELINE":
    with tab3:

        # **Cek apakah df_csat_filtered ada datanya**
        if df_csat_filtered is not None and not df_csat_filtered.empty:
            
            # **Pastikan grafik hanya muncul saat Agent yang dipilih adalah "All"**
            if support_filter == "All":
                st.subheader("🏆 Top 5 Agent dengan CSAT Tertinggi")

                # **Ambil 5 Agent dengan Rata-rata CSAT Tertinggi**
                df_top_5 = df_csat_filtered.groupby("Assign To")["Rating"].mean().nlargest(5).reset_index()

                # **Buat Bar Chart dengan Skala Warna**
                fig_top_5 = px.bar(
                    df_top_5,
                    x="Rating",
                    y="Assign To",
                    text="Rating",
                    orientation="h",
                    title="Top 5 Agent dengan CSAT Tertinggi",
                    color="Rating",
                    color_continuous_scale="greens",
                    labels={"Rating": "Rata-rata CSAT", "Assign To": "Agent"}
                )
                fig_top_5.update_traces(texttemplate='%{text:.2f}', textposition='inside')
                fig_top_5.update_layout(xaxis_title="Rata-rata CSAT", yaxis_title="Agent", coloraxis_showscale=True)

                st.plotly_chart(fig_top_5, use_container_width=True)

                # **BOTTOM 5 Agent dengan CSAT Terendah**
                st.subheader("⚠️ Bottom 5 Agent dengan CSAT Terendah")

                # **Ambil 5 Agent dengan Rata-rata CSAT Terendah**
                df_bottom_5 = df_csat_filtered.groupby("Assign To")["Rating"].mean().nsmallest(5).reset_index()

                # **Buat Bar Chart dengan Skala Warna**
                fig_bottom_5 = px.bar(
                    df_bottom_5,
                    x="Rating",
                    y="Assign To",
                    text="Rating",
                    orientation="h",
                    title="Bottom 5 Agent dengan CSAT Terendah",
                    color="Rating",
                    color_continuous_scale="reds",
                    labels={"Rating": "Rata-rata CSAT", "Assign To": "Agent"}
                )
                fig_bottom_5.update_traces(texttemplate='%{text:.2f}', textposition='inside')
                fig_bottom_5.update_layout(xaxis_title="Rata-rata CSAT", yaxis_title="Agent", coloraxis_showscale=True)

                st.plotly_chart(fig_bottom_5, use_container_width=True)

            else:
                st.warning("⚠️ Grafik ini hanya ditampilkan jika Agent yang dipilih adalah 'All'.")

        else:
            st.warning("🔍 Tidak ada data CSAT dalam rentang tanggal dan filter yang dipilih.")


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
        if df_visit_filtered is not None and not df_visit_filtered.empty:
            df_summary_visit = df_visit_filtered.groupby("Schedule Date").size().reset_index(name="Total Visits")
            fig_visit = px.bar(df_summary_visit, x="Schedule Date", y="Total Visits", title="Jumlah Visit Per Hari")
            st.plotly_chart(fig_visit)

        with st.expander("📅 Klik untuk melihat data visit yang difilter"):
            st.dataframe(df_visit_filtered)

# **Data Activity hanya untuk Sheet SUPPORT**
if selected_sheet == "SUPPORT":			
    with tab4:
        st.title("⏱️ Effective vs Un-effective Time")

    if not df_efftime_filtered.empty:
        # Backup semua data (OK + non-OK) untuk ditampilkan di tabel
        df_all_for_display = df_efftime_filtered.copy()

        # Filter hanya yang status OK untuk perhitungan
        df_valid = df_efftime_filtered[df_efftime_filtered["Status"] == "OK"]

        # Filter berdasarkan agent jika bukan "All"
        if support_filter != "All":
            df_valid = df_valid[df_valid["Assign To"] == support_filter]
            df_all_for_display = df_all_for_display[df_all_for_display["Assign To"] == support_filter]

        # Cek apakah ada data OK
        if not df_valid.empty:
			
			#Checkbox memunculkan nilai negatif
            show_negative = st.checkbox("Tampilkan nilai negatif un-effective time", value=False)
			
            # Konversi tipe data datetime dan timedelta
            df_valid["Schedule Date"] = pd.to_datetime(df_valid["Schedule Date"], errors='coerce').dt.date
            df_valid["Duration"] = pd.to_timedelta(df_valid["Duration"], errors='coerce')

            # Total hari kerja unik
            total_days = df_valid["Schedule Date"].nunique()

            # Standar kerja per hari (misal 9 jam)
            standard_duration = 9

            # Hitung total duration actual dari kolom
            total_duration = df_valid["Duration"].sum()
            total_eff_hours = total_duration.total_seconds() / 3600

            # Hitung durasi kerja sesuai standar (9 jam per hari)
            total_duration_hours = total_days * standard_duration

            # Un-effective = selisih dari jam kerja harian
            total_un_eff_hours = total_duration_hours - total_eff_hours

            # Opsi checkbox untuk nilai negatif
            if not show_negative:
                total_un_eff_hours = max(0, total_un_eff_hours) #sembunyikan nilai negatif

            # Tampilkan metrik
            col1, col2, col3 = st.columns(3)
            col1.metric("📅 Durasi Kerja", f"{total_days} Hari")
            col2.metric("✅ Effective Time", f"{total_eff_hours:.2f} Jam")
            col3.metric("⏳ Un-effective Time", f"{total_un_eff_hours:.2f} Jam")

            # Markdown simulasi
            st.markdown("### 🔍 Simulasi Berdasarkan Status = 'OK'")
            st.markdown(f"""
            - **Durasi Kerja (Hari)**: `{total_days}`
            - ✅ **Total Duration (Jam)**: `{total_eff_hours:.2f}` `(Standar kerja: 9 jam/hari)`
            - ✅ **Total Effective Time (Jam)**: `{total_eff_hours:.2f}` `(Dihitung berdasarkan lama pengerjaan di Outlet)`
            - ⏳ **Total Un-effective Time (Jam)**: `{total_un_eff_hours:.2f}` `(Jam Kerja dikurangi Effective Time)`
            """)

            # Tampilkan seluruh data (OK + non-OK)
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

            # Format tampilan kolom timedelta
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

			
# **🔄 Tombol Refresh Data**
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
