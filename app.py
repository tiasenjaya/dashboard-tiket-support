#Import dan set up awal
import streamlit as st
st.set_page_config(layout="wide", initial_sidebar_state="collapsed")

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
import calendar
from datetime import timedelta
import re   
from urllib.parse import quote
from calendar import monthrange

# =========================
# 🧽 Normalisasi Header & String (GSheet sering ada NBSP / spasi dobel)
# =========================
_NBSP = chr(160)  # NBSP (lebih aman daripada "\u00a0")

def normalize_header(col):
    if col is None:
        return col
    col = str(col).replace(_NBSP, " ")
    col = re.sub(r"\s+", " ", col).strip()
    return col

def normalize_columns(df):
    if df is None or df.empty:
        return df
    df = df.copy()
    df.rename(columns=lambda c: normalize_header(c), inplace=True)

    col_map = {
        "Created Date": "Created",
        "Finish Date": "Finish",
        "Assigned To": "Assign To",
        "Assignee": "Assign To",
        "Ticket No": "Ticket Number",
        "Ticket_Number": "Ticket Number",
        "On Progress": "On Progress Date",
        "OnProgress": "On Progress Date",
        "Repaired": "Repaired Ticket Date",
        "Repaired Date": "Repaired Ticket Date",
        "Repaired Ticket": "Repaired Ticket Date",
        "KPI_Scope": "KPI Scope",
    }
    col_map = {normalize_header(k): v for k, v in col_map.items()}
    df.rename(columns={c: col_map.get(c, c) for c in df.columns}, inplace=True)
    return df

def normalize_text_series(s):
    s = s.copy().astype("string")
    s = s.str.replace(_NBSP, " ", regex=False)
    s = s.str.replace(r"\s+", " ", regex=True)
    s = s.str.strip()
    s = s.replace({"": pd.NA, "nan": pd.NA, "NaN": pd.NA, "<NA>": pd.NA})
    return s

def robust_parse_datetime(series):
    if series is None:
        return series
    if pd.api.types.is_datetime64_any_dtype(series):
        return series

    s = series.astype("string")
    s = s.str.replace(_NBSP, " ", regex=False).str.replace(r"\s+", " ", regex=True).str.strip()

    dt1 = pd.to_datetime(s, errors="coerce", dayfirst=True)
    dt2 = pd.to_datetime(s, errors="coerce", dayfirst=False)
    return dt1 if dt1.isna().sum() <= dt2.isna().sum() else dt2


# =========================
# 📦 Fungsi Utility Umum
# =========================
@st.cache_data
def load_data(url):
    from urllib.parse import quote
    url_encoded = re.sub(r"sheet=([^&]+)", lambda m: f"sheet={quote(m.group(1))}", url)
    df = pd.read_csv(url_encoded)

    # 1) header normalize (NBSP/spasi dobel) + mapping variasi nama kolom
    df = normalize_columns(df)

    # 2) normalize string di kolom yang sering bikin filter salah
    for c in ["TAG", "Assign To", "Services", "Status", "KPI Scope", "Ticket Number"]:
        if c in df.columns:
            df[c] = normalize_text_series(df[c])

    return df

def filter_by_date(df, date_col, start_date, end_date):
    if df is None or df.empty:
        return df
    if date_col in df.columns and start_date and end_date:
        df = df.copy()
        df[date_col] = robust_parse_datetime(df[date_col])
        return df[(df[date_col] >= pd.to_datetime(start_date)) & (df[date_col] <= pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))]
    return df

def filter_by_agent(df, agent):
    return df if agent == "All" else df[df["Assign To"] == agent]

# =========================
# 🎟️ Tiket Metrics
# =========================
def calculate_ticket_metrics(df):
    total_tiket = len(df)
    selesai_24_jam = len(df[df["Durasi (Jam)"] <= 24])
    selesai_lebih_24_jam = len(df[df["Durasi (Jam)"] > 24])
    belum_selesai = len(df[df["Status"] != "Finish"]) if "Status" in df.columns else 0
    avg_durasi = df["Durasi (Jam)"].mean() if "Durasi (Jam)" in df.columns else None
    return total_tiket, selesai_24_jam, selesai_lebih_24_jam, belum_selesai, avg_durasi

def calculate_admin_kpi_metrics(df, sla_hours=48):
    if df is None or df.empty:
        return 0, 0, 0, 0, None

    total = len(df)

    finished_mask = df["Finish"].notna() if "Finish" in df.columns else pd.Series([False]*len(df), index=df.index)
    unfinished = int((~finished_mask).sum())

    dur = pd.to_numeric(df.loc[finished_mask, "Durasi (Jam)"], errors="coerce") if "Durasi (Jam)" in df.columns else pd.Series([], dtype=float)

    ontime = int(dur.le(sla_hours).sum()) if not dur.empty else 0
    late   = int(dur.gt(sla_hours).sum()) if not dur.empty else 0
    avg    = float(dur.mean()) if dur.notna().any() else None

    return total, ontime, late, unfinished, avg

def calculate_admin_qty_metrics(df):
    if df is None or df.empty:
        return 0, 0, 0
    total = len(df)
    finished = int(df["Finish"].notna().sum()) if "Finish" in df.columns else 0
    unfinished = total - finished
    return total, finished, unfinished

# =========================
# 🗓️ Visit Metrics
# =========================
def calculate_visit_metrics(df):
    # Hitung durasi dalam jam jika belum ada
    if "Durasi (Jam)" not in df.columns:
        df["Schedule Date"] = pd.to_datetime(df["Schedule Date"], errors='coerce')
        df["Visit Date"] = pd.to_datetime(df["Visit Date"], errors='coerce')
        df["Durasi (Jam)"] = (df["Visit Date"] - df["Schedule Date"]).dt.total_seconds() / 3600

    visited_df = df[df["Status"] == "Visited"]
    total_visit = len(visited_df)
    selesai_hari_h = len(visited_df[visited_df["Durasi (Jam)"] <= 24])
    selesai_setelah_hari_h = len(visited_df[visited_df["Durasi (Jam)"] > 24])
    belum_dikunjungi = len(df[df["Status"] != "Visited"]) if "Status" in df.columns else 0

    return total_visit, selesai_hari_h, selesai_setelah_hari_h, belum_dikunjungi

# =========================
# ⏱️ Activity Metrics
# =========================
def calculate_efftime_metrics(df, support_filter="All"):
    df_valid = df[df["Status"] == "OK"].copy()
    if support_filter != "All":
        df_valid = df_valid[df_valid["Assign To"] == support_filter]

    total_days = df_valid["Schedule Date"].nunique()
    total_duration = df_valid["Duration"].sum()
    total_eff_hours = total_duration.total_seconds() / 3600 if pd.notnull(total_duration) else 0
    total_duration_hours = total_days * 9  # 9 jam per hari
    total_un_eff_hours = max(0, total_duration_hours - total_eff_hours)
    return total_days, total_eff_hours, total_un_eff_hours

# 🎨 Palet Warna Kontras untuk Konsistensi Visual
def get_default_colors():
    return ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

def hours_to_dhm(hours_float, show_seconds=False):
    """
    Convert jam(float) -> 'X Hari Y Jam Z Menit' (opsional detik).
    Cocok buat Durasi (Jam) dan Avg_Durasi.
    """
    if hours_float is None or pd.isna(hours_float):
        return "-"

    total_seconds = int(round(float(hours_float) * 3600))
    days, rem = divmod(total_seconds, 86400)
    hrs, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)

    if show_seconds:
        if days > 0:
            return f"{days} Hari {hrs} Jam {mins} Menit {secs} Detik"
        return f"{hrs} Jam {mins} Menit {secs} Detik"

    # default: days-hours-minutes (tanpa detik)
    if days > 0:
        return f"{days} Hari {hrs} Jam {mins} Menit"
    return f"{hrs} Jam {mins} Menit"


def metric_card(label, value, sub=None):
    sub_html = f'<div style="font-size:12px;opacity:.7;margin-top:6px;">{sub}</div>' if sub else ""
    st.markdown(
        f"""
        <div style="padding:14px 16px;border:1px solid rgba(49,51,63,.15);
                    border-radius:14px;background:rgba(255,255,255,.0);">
            <div style="font-size:13px;opacity:.75;margin-bottom:6px;">{label}</div>
            <div style="font-size:34px;font-weight:700;line-height:1;">{value}</div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True
    )


# ===============================
# 🎟️ TAB: Data Tiket
# ===============================
def render_tab_tiket(df_filtered, layanan, service_options, total_tiket, selesai_24_jam, selesai_lebih_24_jam, belum_selesai, avg_durasi, support_filter):
    st.title("📊 PERFORMANCE DASHBOARD")
    st.subheader("📌 Performa Penyelesaian Tiket")
    layanan = st.radio("⚙️ Pilih Jenis Services:", options=service_options, key="layanan")

    progress = total_tiket - belum_selesai
    progress_percentage = (progress / total_tiket) * 100 if total_tiket > 0 else 0
    st.progress(progress_percentage / 100)
    st.success(f"✅ **{progress_percentage:.2f}% tiket telah selesai** dari total {total_tiket} tiket.")

    # --- KPI cards (rapih) ---
    m1, m2, m3, m4, m5 = st.columns(5, gap="small")

    with m1:
        metric_card("🎟️ Total Tiket", f"{total_tiket:,}".replace(",", "."))
    with m2:
        metric_card("✅ Selesai ≤ 24 Jam", f"{selesai_24_jam:,}".replace(",", "."))
    with m3:
        metric_card("📋 Selesai > 24 Jam", f"{selesai_lebih_24_jam:,}".replace(",", "."))
    with m4:
        metric_card("⏳ Belum Selesai", f"{belum_selesai:,}".replace(",", "."))
    with m5:
        # avg_durasi boleh None, aman
        metric_card("🕒 Avg Durasi", hours_to_dhm(avg_durasi, show_seconds=False))

    # === Audit: delay setelah dev ===
    if "After_Dev (Jam)" in df_filtered.columns:
        dev_done = df_filtered[df_filtered["After_Dev (Jam)"].notna()].copy()
        total_dev_done = len(dev_done)
        avg_after_dev = dev_done["After_Dev (Jam)"].mean() if total_dev_done > 0 else None
        after_dev_gt_24 = int((dev_done["After_Dev (Jam)"] > 24).sum()) if total_dev_done > 0 else 0

        st.markdown("#### 🧑‍💻 Audit After Dev")
        a1, a2, a3 = st.columns(3, gap="small")
        with a1:
            metric_card("Tiket Repaired (Dev Done)", f"{total_dev_done:,}".replace(",", "."))
        with a2:
            metric_card("Avg Delay After Dev", hours_to_dhm(avg_after_dev, show_seconds=False))
        with a3:
            metric_card("Delay After Dev > 24 Jam", f"{after_dev_gt_24:,}".replace(",", "."))

    st.subheader("📊 Grafik Bar Chart (Total Tiket vs Tiket Selesai)")
    if not df_filtered.empty:
        # Step 1: Pastikan kolom Created sudah datetime
        df_filtered["Created"] = robust_parse_datetime(df_filtered["Created"])

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
            title="Total Tiket vs Tiket Selesai ≤ 24 Jam (Bar Chart)"
            )
        for trace in fig_bar.data:
            trace.text = trace.y
            trace.textposition = 'outside'
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

    if support_filter == "All" and not df_filtered.empty:
        agent_summary = df_filtered.groupby("Assign To").agg(
            Total_Ticket = ("Ticket Number", "count"),
            Durasi_Kurang_24_Jam = ("Durasi (Jam)", lambda x: (x <= 24).sum())
        ).reset_index()

        agent_summary["Ontime_Percentage"] = (
            agent_summary["Durasi_Kurang_24_Jam"] / agent_summary["Total_Ticket"]
        ) * 100

        # Klasifikasi berdasarkan ambang
        agent_summary["Klasifikasi"] = agent_summary["Ontime_Percentage"].apply(lambda x: 
            "Sangat Baik" if x >= 90 else 
            "Baik" if x >= 75 else 
            "Cukup" if x >= 60 else 
            "Kurang Baik"
        )

        # Cari agent terdekat dari masing-masing kategori
        target_klasifikasi = {
            "Sangat Baik": 90,
            "Baik": 75,
            "Cukup": 60,
            "Kurang Baik": 50}

        selected_agents = []

        for klasifikasi, target in target_klasifikasi.items():
            df_k = agent_summary[agent_summary["Klasifikasi"] == klasifikasi].copy()
            if not df_k.empty:
                selected_agents.append(df_k.sort_values("Ontime_Percentage", ascending=False).iloc[0])

        # Gabungkan agent hasil seleksi
        representative_df = pd.DataFrame(selected_agents).reset_index(drop=True)

        # Tampilkan hasil klasifikasi ringkas
        for _, row in representative_df.iterrows():
            nama = row["Assign To"]
            persen = row["Ontime_Percentage"]
            kategori = row["Klasifikasi"]
            icon = {
                "Sangat Baik": "🟢",
                "Baik": "🟡",
                "Cukup": "🟠",
                "Kurang Baik": "🔴"
            }.get(kategori, "⚪")

            st.markdown(f"- {icon} **{nama}**: {kategori} ({persen:.1f}%)")

    with st.expander("📋 Klik untuk melihat data tiket yang difilter"):
        df_display = df_filtered.copy()
        def format_durasi(jam_float):
            return hours_to_dhm(jam_float, show_seconds=True)

        if "After_Dev (Jam)" in df_display.columns:
            df_display["After_Dev (Jam)"] = df_display["After_Dev (Jam)"].apply(format_durasi)


        df_display["Durasi (Jam)"] = df_display["Durasi (Jam)"].apply(format_durasi)
        display_columns = [
            "Ticket Number", "Created", "On Progress Date", "Repaired Ticket Date", "Finish",
            "Assign To", "Services", "Status", "Durasi (Jam)", "After_Dev (Jam)"
        ]
        available_cols = [col for col in display_columns if col in df_display.columns]
        st.dataframe(df_display[available_cols])

def render_tab_admin_kpi(df_admin_kpi_filtered, sla_hours=48, selected_agents=None):
    st.title("📊 ADMIN KPI DASHBOARD")

    if df_admin_kpi_filtered is None or df_admin_kpi_filtered.empty:
        st.warning("Data ADMIN KPI kosong setelah filter.")
        return

    dfk = df_admin_kpi_filtered.copy()

    # normalisasi kolom penting (aman)
    if "KPI Scope" not in dfk.columns:
        dfk["KPI Scope"] = "QTY"
    else:
        dfk["KPI Scope"] = normalize_text_series(dfk["KPI Scope"])

    if "TAG" in dfk.columns:
        dfk["TAG"] = normalize_text_series(dfk["TAG"])

    if "Assign To" in dfk.columns:
        dfk["Assign To"] = normalize_text_series(dfk["Assign To"])

    # pastikan Durasi numerik
    if "Durasi (Jam)" in dfk.columns:
        dfk["Durasi (Jam)"] = pd.to_numeric(dfk["Durasi (Jam)"], errors="coerce")

    # =========================
    # Ringkasan umum (ALL scope)
    # =========================
    total_all = len(dfk)
    finished_all = int(dfk["Finish"].notna().sum()) if "Finish" in dfk.columns else 0
    unfinished_all = total_all - finished_all

    # --- UI helper khusus ADMIN (biar gak ganggu tab lain) ---
    def _card(label, value, sub=None):
        sub_html = f'<div style="font-size:12px;opacity:.7;margin-top:6px;">{sub}</div>' if sub else ""
        st.markdown(
            f"""
            <div style="padding:14px 16px;border:1px solid rgba(49,51,63,.15);
                        border-radius:14px;background:rgba(255,255,255,.0);">
            <div style="font-size:13px;opacity:.75;margin-bottom:6px;">{label}</div>
            <div style="font-size:34px;font-weight:700;line-height:1;">{value}</div>
            {sub_html}
            </div>
            """,
            unsafe_allow_html=True
        )

    progress_pct = (finished_all / total_all * 100) if total_all > 0 else 0.0

        # --- UI helper khusus ADMIN (biar gak ganggu tab lain) ---
    def _card(label, value, sub=None):
        sub_html = f'<div style="font-size:12px;opacity:.7;margin-top:6px;">{sub}</div>' if sub else ""
        st.markdown(
            f"""
            <div style="padding:14px 16px;border:1px solid rgba(49,51,63,.15);
                        border-radius:14px;background:rgba(255,255,255,.0);">
            <div style="font-size:13px;opacity:.75;margin-bottom:6px;">{label}</div>
            <div style="font-size:34px;font-weight:700;line-height:1;">{value}</div>
            {sub_html}
            </div>
            """,
            unsafe_allow_html=True
        )

    # --- formatter durasi untuk display di tabel detail (JANGAN dipakai buat KPI calc) ---
    def format_durasi_dhm(jam_float):
        if pd.isnull(jam_float):
            return "-"
        total_detik = int(round(float(jam_float) * 3600))
        hari = total_detik // 86400
        sisa = total_detik % 86400
        jam = sisa // 3600
        menit = (sisa % 3600) // 60
        return f"{hari} Hari {jam} Jam {menit} Menit" if hari > 0 else f"{jam} Jam {menit} Menit"

    progress_pct = (finished_all / total_all * 100) if total_all > 0 else 0.0


    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1: _card("📦 Total Pekerjaan", f"{total_all:,}".replace(",", "."))
    with c2: _card("✅ Selesai", f"{finished_all:,}".replace(",", "."))
    with c3: _card("⏳ Belum Selesai", f"{unfinished_all:,}".replace(",", "."))
    with c4: _card("📈 Completion", f"{progress_pct:.2f}%", sub=f"Target SLA: ≤ {sla_hours} jam (khusus SLA & QTY)")

    st.divider()

    # =========================
    # Split scope
    # =========================
    df_sla = dfk[dfk["KPI Scope"] == "SLA & QTY"].copy()
    df_qty = dfk[dfk["KPI Scope"] == "QTY"].copy()

    tab_sla, tab_qty = st.tabs(
        [f"🔗 SLA & QTY (≤ {sla_hours} jam) — NEW DB/BRAND/BRANCH",
         "📦 QTY-only — ESO/REVISI MENU"]
    )

    # =========================
    # TAB A — SLA & QTY
    # =========================
    with tab_sla:
        if df_sla.empty:
            st.info("Tidak ada data scope **SLA & QTY** untuk filter ini.")
        else:
            total, ontime, late, unfinished, avg = calculate_admin_kpi_metrics(df_sla, sla_hours=sla_hours)
            selesai = total - unfinished
            ontime_pct = (ontime / selesai * 100) if selesai > 0 else 0

            st.subheader(f"🔗 SLA & QTY (target ≤ {sla_hours} jam)")

            mc1, mc2, mc3, mc4, mc5 = st.columns(5, gap="small")
            with mc1: _card("Total", f"{total:,}".replace(",", "."))
            with mc2: _card("Selesai", f"{selesai:,}".replace(",", "."))
            with mc3: _card("Ontime", f"{ontime:,}".replace(",", "."))
            with mc4: _card("Late", f"{late:,}".replace(",", "."))
            with mc5: _card("Ontime %", f"{ontime_pct:.2f}%")

            if avg is not None:
                st.caption(f"Rata-rata durasi selesai: {avg:.2f} jam")

            st.markdown("### 🏷️ SLA per TAG")

            if "TAG" in df_sla.columns:
                by_tag_sla = df_sla.groupby("TAG").agg(
                    Total=("Ticket Number", "count"),
                    Selesai=("Finish", lambda x: x.notna().sum()),
                    Belum_Selesai=("Finish", lambda x: x.isna().sum()),
                    Ontime=("Durasi (Jam)", lambda x: (x <= sla_hours).sum()),
                    Late=("Durasi (Jam)", lambda x: (x > sla_hours).sum()),
                    Avg_Durasi=("Durasi (Jam)", "mean"),
                ).reset_index()

                by_tag_sla["Ontime_%"] = (
                    (by_tag_sla["Ontime"] / by_tag_sla["Selesai"].replace(0, pd.NA)) * 100
                ).round(2)

                # Chart ringkas (biar kerasa dashboard)
                fig_sla_tag = px.bar(
                    by_tag_sla.sort_values("Total", ascending=False),
                    x="TAG",
                    y=["Ontime", "Late"],
                    barmode="group",
                    text_auto=True,
                    color_discrete_sequence=get_default_colors(),  # ✅ ini yang bikin sama
                    title="Ontime vs Late per TAG (SLA & QTY)",
                    labels={"value": "Jumlah", "variable": "", "TAG": "TAG"},
                )

                # rapihin tampilannya biar mirip chart tiket
                fig_sla_tag.update_traces(textposition="outside", cliponaxis=False)
                fig_sla_tag.update_layout(
                    xaxis_tickangle=-35,
                    yaxis_title="Jumlah Ticket",
                    legend_title_text="",
                    margin=dict(t=60, b=60, l=40, r=20),
                )

                st.plotly_chart(fig_sla_tag, use_container_width=True)

                by_tag_view = by_tag_sla.sort_values("Total", ascending=False).copy()

                if "Avg_Durasi" in by_tag_view.columns:
                    by_tag_view["Avg_Durasi"] = by_tag_view["Avg_Durasi"].apply(format_durasi_dhm)

                st.dataframe(by_tag_view, use_container_width=True)


            # tampilkan per-admin hanya kalau All / multi agent
            if "Assign To" in df_sla.columns and (selected_agents is None or len(selected_agents) != 1):
                st.markdown("### 👤 SLA per Admin")
                by_admin_sla = df_sla.groupby("Assign To").agg(
                    Total=("Ticket Number", "count"),
                    Selesai=("Finish", lambda x: x.notna().sum()),
                    Ontime=("Durasi (Jam)", lambda x: (x <= sla_hours).sum()),
                    Late=("Durasi (Jam)", lambda x: (x > sla_hours).sum()),
                    Avg_Durasi=("Durasi (Jam)", "mean"),
                ).reset_index()

                by_admin_sla["Ontime_%"] = (
                    (by_admin_sla["Ontime"] / by_admin_sla["Selesai"].replace(0, pd.NA)) * 100
                ).round(2)

                by_admin_view = by_admin_sla.sort_values(["Ontime_%", "Total"], ascending=[False, False]).copy()

                if "Avg_Durasi" in by_admin_view.columns:
                    by_admin_view["Avg_Durasi"] = by_admin_view["Avg_Durasi"].apply(format_durasi_dhm)

                st.dataframe(by_admin_view, use_container_width=True)

                with st.expander("📋 Detail SLA & QTY (data mentah)"):
                    show_cols = [c for c in ["Ticket Number", "Created", "Finish", "Assign To", "TAG", "KPI Scope", "Durasi (Jam)"] if c in df_sla.columns]

                    df_view = df_sla[show_cols].copy()
                    if "Durasi (Jam)" in df_view.columns:
                        df_view["Durasi (Jam)"] = df_view["Durasi (Jam)"].apply(format_durasi_dhm)

                    st.dataframe(df_view, use_container_width=True)

    # =========================
    # TAB B — QTY-only
    # =========================
    with tab_qty:
        if df_qty.empty:
            st.info("Tidak ada data scope **QTY-only** untuk filter ini.")
        else:
            total, selesai, belum = calculate_admin_qty_metrics(df_qty)
            st.subheader("📦 QTY-only (ESO / REVISI MENU)")

            qc1, qc2, qc3 = st.columns(3, gap="small")
            with qc1: _card("Total", f"{total:,}".replace(",", "."))
            with qc2: _card("Selesai", f"{selesai:,}".replace(",", "."))
            with qc3: _card("Belum Selesai", f"{belum:,}".replace(",", "."))

            st.markdown("### 🏷️ QTY per TAG")

            if "TAG" in df_qty.columns:
                by_tag_qty = df_qty.groupby("TAG").agg(
                    Total=("Ticket Number", "count"),
                    Selesai=("Finish", lambda x: x.notna().sum()),
                    Belum_Selesai=("Finish", lambda x: x.isna().sum()),
                ).reset_index()

                fig_qty_tag = px.bar(
                    by_tag_qty.sort_values("Total", ascending=False),
                    x="TAG", y="Total",
                    title="Total Pekerjaan per TAG (QTY-only)"
                )
                st.plotly_chart(fig_qty_tag, use_container_width=True)

                st.dataframe(
                    by_tag_qty.sort_values("Total", ascending=False),
                    use_container_width=True
                )

            with st.expander("📋 Detail QTY-only (data mentah)"):
                show_cols = [c for c in ["Ticket Number", "Created", "Finish", "Assign To", "TAG", "KPI Scope"] if c in df_qty.columns]
                st.dataframe(df_qty[show_cols])

# ===============================
# 🗓️ TAB: Data Visit (SUPPORT)
# ===============================
def render_tab_visit(df_visit_filtered, support_filter):
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
    total_visit, selesai_hari_h_visit, selesai_setelah_hari_h_visit, not_visited = calculate_visit_metrics(df_visit_filtered)


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

        for trace in fig_visit.data:
            trace.text = trace.y
            trace.textposition = 'outside'
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

    if support_filter == "All" and not df_visit_filtered.empty:
        visit_summary = df_visit_filtered[df_visit_filtered["Status"] == "Visited"].copy()
        visit_summary = visit_summary.groupby("Assign To").agg(
            Total_Visit=("Status", "count"),
            Finish_Hari_H=("Durasi (Jam)", lambda x: (x <= 24).sum())
        ).reset_index()
        
        visit_summary["Ontime_Percentage"] = visit_summary["Finish_Hari_H"] / visit_summary["Total_Visit"] * 100

        visit_summary["Klasifikasi"] = visit_summary["Ontime_Percentage"].apply(lambda x:
            "Sangat Baik" if x >= 90 else
            "Baik" if x >= 75 else
            "Cukup" if x >= 60 else
            "Kurang Baik"
        )

        target_klasifikasi = {
            "Sangat Baik": 90,
            "Baik": 75,
            "Cukup": 60,
            "Kurang Baik": 50
        }

        selected_visits = []
        for klasifikasi, _ in target_klasifikasi.items():
            df_k = visit_summary[visit_summary["Klasifikasi"] == klasifikasi].copy()
            if not df_k.empty:
                selected_visits.append(df_k.sort_values("Ontime_Percentage", ascending=False).iloc[0])

        visit_representative_df = pd.DataFrame(selected_visits).reset_index(drop=True)

        for _, row in visit_representative_df.iterrows():
            nama = row["Assign To"]
            persen = row["Ontime_Percentage"]
            kategori = row["Klasifikasi"]
            icon = {
                "Sangat Baik": "🟢",
                "Baik": "🟡",
                "Cukup": "🟠",
                "Kurang Baik": "🔴"
            }.get(kategori, "⚪")
            
            st.markdown(f"**{icon} {nama}**: {kategori} ({persen:.1f}%)")

    # Tabel data
    st.subheader("📋 Data Visit")
    display_columns = ["Schedule Date", "Visit Date", "Assign To", "Visit Type", "Status", "Durasi (Jam)"]

    with st.expander("Klik untuk melihat data visit yang difilter"):
        st.dataframe(df_visit_filtered[display_columns])

# ===============================
# ⏱️ TAB: Activity (SUPPORT)
# ===============================
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

            total_days, total_eff_hours, total_un_eff_hours = calculate_efftime_metrics(df_efftime_filtered, support_filter)
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

# ===============================
# ⭐ TAB: Data CSAT (CARELINE/ ADMIN/ CUSTCARE)
# ===============================
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

# ===============================
# ⏱️ TAB: Response Time (CARELINE & CUSTCARE)
# ===============================
def render_tab_response_time(df_filtered, support_filter):
    st.title("⏱️ Analisis Response Time")

    # Validasi awal
    if df_filtered is None or df_filtered.empty:
        st.warning("Data kosong. Silakan atur filter tanggal atau agent.")
        return

    if support_filter != "All":
        df_filtered = df_filtered[df_filtered["Assign To"] == support_filter]

    if df_filtered.empty:
        st.warning("Tidak ada data untuk agent dan filter waktu yang dipilih.")
        return

    # Pastikan tipe data benar
    df_filtered = df_filtered.copy()
    df_filtered["First Response Time"] = pd.to_timedelta(df_filtered["First Response Time"], errors="coerce")
    df_filtered["Total Open Time"] = pd.to_timedelta(df_filtered["Total Open Time"], errors="coerce")
    # Kolom Average Reply bisa beda nama / tidak selalu ada → deteksi aman
    avg_reply_candidates = ["Average Reply", "Avg Reply", "Average Reply Time"]
    avg_reply_col = next((c for c in avg_reply_candidates if c in df_filtered.columns), None)
    if avg_reply_col:
        df_filtered[avg_reply_col] = pd.to_timedelta(df_filtered[avg_reply_col], errors="coerce")

    # =========================
    # Formatter waktu
    # =========================
    def format_total(td):
        """Format untuk TOTAL (pakai Days/Hours/Minutes)."""
        if pd.isnull(td):
            return "-"
        total_seconds = int(td.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{days} Days {hours} Hours {minutes} Minutes"

    def format_hhmmss(td):
        """Format untuk AVERAGE dengan satuan Hours, Minutes, Seconds."""
        if pd.isnull(td):
            return "-"
        secs = int(td.total_seconds())
        hours = secs // 3600
        minutes = (secs % 3600) // 60
        seconds = secs % 60
        return f"{hours} Hours, {minutes} Minutes, {seconds} Seconds"

    # ================================
    # ⏳ Periode & Jumlah Chat
    # ================================
    st.markdown(
        f"📆 **Periode:** {df_filtered['Created'].min().date()} s.d {df_filtered['Created'].max().date()}"
    )
    st.markdown(f"<b>Jumlah Chat:</b> {len(df_filtered)}", unsafe_allow_html=True)

    # ================================
    # 📊 Ringkasan Waktu (TOTAL & AVG)
    # ================================
    # Untuk perhitungan, nilai NaT dianggap 0 detik (ikut rata-rata seperti di pivot)
    fr_seconds   = df_filtered["First Response Time"].fillna(pd.Timedelta(0)).dt.total_seconds()
    open_seconds = df_filtered["Total Open Time"].fillna(pd.Timedelta(0)).dt.total_seconds()

    total_first_response = pd.to_timedelta(fr_seconds.sum(),   unit="s")
    total_open_time      = pd.to_timedelta(open_seconds.sum(), unit="s")

    count_rows = len(df_filtered)
    avg_first_response = pd.to_timedelta(fr_seconds.sum()   / count_rows, unit="s") if count_rows > 0 else pd.Timedelta(0)
    avg_open_time      = pd.to_timedelta(open_seconds.sum() / count_rows, unit="s") if count_rows > 0 else pd.Timedelta(0)

    # Hanya hitung Average Reply jika kolomnya ada
    if 'avg_reply_col' in locals() and avg_reply_col:
        reply_seconds    = df_filtered[avg_reply_col].fillna(pd.Timedelta(0)).dt.total_seconds()
        total_avg_reply  = pd.to_timedelta(reply_seconds.sum(), unit="s")
        avg_reply_time   = pd.to_timedelta(reply_seconds.sum() / count_rows, unit="s") if count_rows > 0 else pd.Timedelta(0)
    else:
        total_avg_reply = None
        avg_reply_time  = None

    st.markdown("### 📈 Ringkasan Waktu")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🕐 Total First Response")
        st.success(format_total(total_first_response))
        st.subheader("🕒 Total Open Time")
        st.info(format_total(total_open_time))
    with col2:
        st.subheader("⏱️ Rata-rata First Response")
        st.success(format_hhmmss(avg_first_response))
        st.subheader("📊 Rata-rata Open Time")
        st.info(format_hhmmss(avg_open_time))

    # Tampilkan kartu Average Reply hanya jika kolomnya ada
    if avg_reply_time is not None:
        col3, col4 = st.columns(2)
        with col3:
            st.subheader("💬 Total Average Reply")
            st.info(format_total(total_avg_reply))
        with col4:
            st.subheader("🧮 Rata-rata Average Reply")
            st.success(format_hhmmss(avg_reply_time))
    else:
        st.caption("ℹ️ Kolom **Average Reply** tidak ditemukan pada sheet ini, jadi metriknya disembunyikan.")

    st.markdown("---")

    # ==============================
    # 📊 Ringkasan per Agent
    # ==============================
    df_eval = df_filtered.copy()
    df_eval["Assign To"] = df_eval["Assign To"].astype(str).str.strip().str.title()

    # Biarkan nilai kosong menjadi 0 detik (ikut rata-rata)
    df_eval["fr_seconds"] = df_eval["First Response Time"].fillna(pd.Timedelta(0)).dt.total_seconds()
    df_eval["open_seconds"] = df_eval["Total Open Time"].fillna(pd.Timedelta(0)).dt.total_seconds()

    # Group by agent
    df_grouped = df_eval.groupby("Assign To").agg(
        total_fr=("fr_seconds", "sum"),
        total_open=("open_seconds", "sum"),
        count=("Assign To", "count")
    ).reset_index()

    # Rata-rata = total detik / jumlah tiket (termasuk yang 0 detik)
    df_grouped["avg_fr"] = df_grouped["total_fr"] / df_grouped["count"]
    df_grouped["avg_open"] = df_grouped["total_open"] / df_grouped["count"]

    # Simpan kolom detik untuk cari fastest/slowest
    df_grouped["_avg_first_secs"] = df_grouped["avg_fr"].astype(float)
    df_grouped["_total_first_secs"] = df_grouped["total_fr"].astype(float)

    # Konversi ke timedelta untuk display
    df_grouped["Total First"] = pd.to_timedelta(df_grouped["total_fr"], unit="s")
    df_grouped["Total Open"] = pd.to_timedelta(df_grouped["total_open"], unit="s")
    df_grouped["Avg First"] = pd.to_timedelta(df_grouped["avg_fr"], unit="s")
    df_grouped["Avg Open"] = pd.to_timedelta(df_grouped["avg_open"], unit="s")

    # Tentukan agent tercepat & terlambat berdasar avg (termasuk 0 detik)
    fastest_row = df_grouped.sort_values(["_avg_first_secs", "Assign To"]).iloc[0]
    slowest_row = df_grouped.sort_values(["_avg_first_secs", "Assign To"], ascending=[False, True]).iloc[0]

    # Tabel tampil: Avg = HH:MM:SS, Total = Days/Hours/Minutes
    df_display = df_grouped[["Assign To", "Total First", "Total Open", "Avg First", "Avg Open"]].copy()
    df_display["Total First"] = df_display["Total First"].apply(format_total)
    df_display["Total Open"] = df_display["Total Open"].apply(format_total)
    df_display["Avg First"] = df_display["Avg First"].apply(format_hhmmss)
    df_display["Avg Open"] = df_display["Avg Open"].apply(format_hhmmss)

    st.markdown("### 📊 Ringkasan per Agent")
    st.dataframe(
        df_display.style.highlight_max(axis=0, subset=["Avg First", "Avg Open"], color="lightcoral")
    )

    col_f, col_s = st.columns(2)
    with col_f:
        st.metric("🚀 Fastest Agent", fastest_row["Assign To"], delta=format_hhmmss(pd.to_timedelta(fastest_row["_avg_first_secs"], unit="s")))
    with col_s:
        st.metric("🐢 Slowest Agent", slowest_row["Assign To"], delta=format_hhmmss(pd.to_timedelta(slowest_row["_avg_first_secs"], unit="s")))

    st.markdown("---")

    # === Data detail (urut menurut FR naik) ===
    with st.expander("📄 Lihat Data Detail"):
        display_df = df_filtered[["Created", "Assign To", "First Response Time", "Total Open Time"]].copy()
        display_df["First Response Time"] = display_df["First Response Time"].fillna(pd.Timedelta(0))
        display_df["Total Open Time"] = display_df["Total Open Time"].fillna(pd.Timedelta(0))
        display_df["First Response Time (Avg View)"] = display_df["First Response Time"].apply(format_hhmmss)
        display_df["Total Open Time (Avg View)"] = display_df["Total Open Time"].apply(format_hhmmss)
        display_df = display_df.sort_values("First Response Time")
        st.dataframe(display_df)


# ===============================
#🗣️ TAB: Interaksi Careline
# ===============================
def render_tab_interaksi(df_interaksi_filtered, df_response_time=None):
    st.markdown("## 🧠 Ringkasan Interaksi")

    # Hitung jumlah chat dari df_response_time (sudah difilter sebelumnya)
    jumlah_chat = df_response_time["Created"].count() if df_response_time is not None and "Created" in df_response_time.columns else 0

    # Jumlah hari aktif
    n_days = df_interaksi_filtered["Created"].nunique()
    avg_per_day = (len(df_interaksi_filtered) + jumlah_chat) / n_days if n_days > 0 else 0

    # Metrik Utama
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Interaksi", len(df_interaksi_filtered) + jumlah_chat)
    col2.metric("Jumlah Agent", df_interaksi_filtered["Assign To"].dropna().nunique())
    col3.metric("Rata-rata Interaksi / Hari", f"{avg_per_day:.0f}")

    # Interaksi per Divisi
    divisi_counts = df_interaksi_filtered["Interaction"].value_counts().reset_index()
    divisi_counts.columns = ["Divisi", "Jumlah Interaksi"]
    divisi_counts = divisi_counts.sort_values("Jumlah Interaksi", ascending=False)

    st.markdown("### 🧩 Jumlah Interaksi per Divisi & Client")
    cols = st.columns(3)

    emoji_map = {
        "Support": "🛠️", "Admin": "🧾", "BC": "📞",
        "Careline": "💬", "Custcare": "🫶", "Client": "👥"
    }

    for i, row in enumerate(divisi_counts.itertuples()):
        col = cols[i % 3]
        emoji = emoji_map.get(row.Divisi, " ")
        col.metric(f"{emoji} {row.Divisi}", row._2)

    # Tambahkan Jumlah Chat sebagai "Client"
    col_client = cols[len(divisi_counts) % 3]
    col_client.metric("👥 Client", jumlah_chat)

    # Tampilkan Tabel
    st.markdown("---")
    st.markdown("📊 **Detail Data Interaksi**")
    st.dataframe(df_interaksi_filtered)

# ===============================
# 📥 Load Data Berdasarkan Sheet
# ===============================
# **📄 Konfigurasi Layout**
#Inisialisasi & Pemanggilan Data Sheet
GOOGLE_SHEET_LINKS = {
    "SUPPORT": {
        "ticket": "https://docs.google.com/spreadsheets/d/15DHR0cVyIAORGprLFPPX3CbhtK0NrD1d5mqkurhXeXU/gviz/tq?tqx=out:csv&sheet=DATA TICKET",
        "visit": "https://docs.google.com/spreadsheets/d/15DHR0cVyIAORGprLFPPX3CbhtK0NrD1d5mqkurhXeXU/gviz/tq?tqx=out:csv&sheet=DATA VISIT",
        "activity": "https://docs.google.com/spreadsheets/d/15DHR0cVyIAORGprLFPPX3CbhtK0NrD1d5mqkurhXeXU/gviz/tq?tqx=out:csv&sheet=DATA ACTIVITY",
    },
    "CARELINE": {
        "ticket": "https://docs.google.com/spreadsheets/d/10GxKf8rurFofXf86BdsnLJWly1eNOijjAz8_GPHftqQ/gviz/tq?tqx=out:csv&sheet=DATA TICKET",
        "csat": "https://docs.google.com/spreadsheets/d/10GxKf8rurFofXf86BdsnLJWly1eNOijjAz8_GPHftqQ/gviz/tq?tqx=out:csv&sheet=DATA CSAT",
        "goapp": "https://docs.google.com/spreadsheets/d/10GxKf8rurFofXf86BdsnLJWly1eNOijjAz8_GPHftqQ/gviz/tq?tqx=out:csv&sheet=DATA GOAPP",
        "interaction": "https://docs.google.com/spreadsheets/d/10GxKf8rurFofXf86BdsnLJWly1eNOijjAz8_GPHftqQ/gviz/tq?tqx=out:csv&sheet=INTERACTION",
    },
    "CUSTCARE": {
        "ticket": "https://docs.google.com/spreadsheets/d/1Iv-4W7Aha50oL76yM-kamet1k2L4dfH_VVKMjyXtgVI/gviz/tq?tqx=out:csv&sheet=DATA TICKET",
        "csat": "https://docs.google.com/spreadsheets/d/1Iv-4W7Aha50oL76yM-kamet1k2L4dfH_VVKMjyXtgVI/gviz/tq?tqx=out:csv&sheet=DATA CSAT",
        "goapp": "https://docs.google.com/spreadsheets/d/1Iv-4W7Aha50oL76yM-kamet1k2L4dfH_VVKMjyXtgVI/gviz/tq?tqx=out:csv&sheet=DATA GOAPP",
        "interaction": "https://docs.google.com/spreadsheets/d/1Iv-4W7Aha50oL76yM-kamet1k2L4dfH_VVKMjyXtgVI/gviz/tq?tqx=out:csv&sheet=INTERACTION",
    },
    "ADMIN": {
        "admin_kpi": "https://docs.google.com/spreadsheets/d/1f4RQTBIL7mRHGHCAQ0ewgi2SfzybXiiLP_tsnEjAHZE/gviz/tq?tqx=out:csv&sheet=On Board Master",
        "csat": "https://docs.google.com/spreadsheets/d/1f4RQTBIL7mRHGHCAQ0ewgi2SfzybXiiLP_tsnEjAHZE/gviz/tq?tqx=out:csv&sheet=DATA CSAT",
    }
}

sheet_names = list(GOOGLE_SHEET_LINKS.keys())
selected_sheet = st.sidebar.selectbox("📄 Pilih Sheet:", sheet_names)
df = pd.DataFrame()
if selected_sheet in ["SUPPORT", "CARELINE", "CUSTCARE"]:
    df = load_data(GOOGLE_SHEET_LINKS[selected_sheet]["ticket"])

df_visit = df_csat = df_goapp = df_efftime = df_interaksi = df_admin_kpi = None

# ⬇️ SUPPORT
if selected_sheet == "SUPPORT":
    df_visit = load_data(GOOGLE_SHEET_LINKS[selected_sheet].get("visit", ""))
    df_efftime = load_data(GOOGLE_SHEET_LINKS[selected_sheet].get("activity", ""))

# ⬇️ CARELINE
elif selected_sheet == "CARELINE":
    df_csat = load_data(GOOGLE_SHEET_LINKS[selected_sheet].get("csat", ""))
    df_goapp = load_data(GOOGLE_SHEET_LINKS[selected_sheet].get("goapp", ""))
    df_interaksi = load_data(GOOGLE_SHEET_LINKS[selected_sheet].get("interaction", ""))

# ⬇️ ADMIN
elif selected_sheet == "ADMIN":
    df_csat = load_data(GOOGLE_SHEET_LINKS[selected_sheet].get("csat", ""))
    df_admin_kpi = load_data(GOOGLE_SHEET_LINKS[selected_sheet].get("admin_kpi", ""))

# ⬇️ CUSTCARE
elif selected_sheet == "CUSTCARE":
    df_goapp = load_data(GOOGLE_SHEET_LINKS[selected_sheet].get("goapp", ""))
    df_csat = load_data(GOOGLE_SHEET_LINKS[selected_sheet].get("csat", ""))
    df_interaksi = load_data(GOOGLE_SHEET_LINKS[selected_sheet].get("interaction", ""))

# ===============================
# 🧹 PARSING & VALIDASI DATA
# ===============================
if "Created" in df.columns:
    df["Created"] = robust_parse_datetime(df["Created"])
    df["Created Display"] = df["Created"].dt.strftime("%d/%m/%Y %H:%M:%S")
    df["Created_Date"] = df["Created"].dt.date

if "On Progress Date" in df.columns:
    df["On Progress Date"] = robust_parse_datetime(df["On Progress Date"])

if "Repaired Ticket Date" in df.columns:
    df["Repaired Ticket Date"] = robust_parse_datetime(df["Repaired Ticket Date"])

if "Finish" in df.columns:
    df["Finish"] = robust_parse_datetime(df["Finish"])
    df["Finish Display"] = df["Finish"].dt.strftime("%d/%m/%Y %H:%M:%S")

    df["Durasi_Total (Jam)"] = (df["Finish"] - df["Created"]).dt.total_seconds() / 3600

    df["Durasi_Dev (Jam)"] = 0.0
    if "On Progress Date" in df.columns and "Repaired Ticket Date" in df.columns:
        has_dev = df["On Progress Date"].notna() & df["Repaired Ticket Date"].notna()
        df.loc[has_dev, "Durasi_Dev (Jam)"] = (
            (df.loc[has_dev, "Repaired Ticket Date"] - df.loc[has_dev, "On Progress Date"])
            .dt.total_seconds() / 3600
        )

    df["Durasi_Dev (Jam)"] = df["Durasi_Dev (Jam)"].clip(lower=0)
    df["Durasi (Jam)"] = (df["Durasi_Total (Jam)"] - df["Durasi_Dev (Jam)"]).clip(lower=0)

    df["After_Dev (Jam)"] = pd.NA
    if "Repaired Ticket Date" in df.columns:
        has_after_dev = df["Repaired Ticket Date"].notna() & df["Finish"].notna()
        df.loc[has_after_dev, "After_Dev (Jam)"] = (
            (df.loc[has_after_dev, "Finish"] - df.loc[has_after_dev, "Repaired Ticket Date"])
            .dt.total_seconds() / 3600
        ).clip(lower=0)

if df_visit is not None:
    df_visit["Schedule Date"] = pd.to_datetime(df_visit["Schedule Date"], errors='coerce', dayfirst=True)
    df_visit["Visit Date"] = pd.to_datetime(df_visit["Visit Date"], errors='coerce', dayfirst=True)

if df_efftime is not None:
    df_efftime["Schedule Date"] = pd.to_datetime(df_efftime["Schedule Date"], errors='coerce', dayfirst=True)
    df_efftime["Duration"] = pd.to_timedelta(df_efftime["Duration"], errors='coerce')
    df_efftime["Check In"] = pd.to_datetime(df_efftime["Check In"], errors='coerce')
    df_efftime["Check Out"] = pd.to_datetime(df_efftime["Check Out"], errors='coerce')
    df_efftime["Status"] = df_efftime.apply(
        lambda row: "Missing" if pd.isna(row["Check In"]) or pd.isna(row["Check Out"]) else "OK", axis=1)
    standard_duration = pd.to_timedelta("9:00:00")
    df_efftime["Un-effective Time"] = standard_duration - df_efftime["Duration"]

if df_csat is not None:
    df_csat["Created"] = pd.to_datetime(df_csat["Created"], errors='coerce', dayfirst=True)
    df_csat["Rating"] = pd.to_numeric(df_csat["Rating"], errors="coerce")

if df_goapp is not None and "Created" in df_goapp.columns:
    df_goapp["Created"] = robust_parse_datetime(df_goapp["Created"])
    df_goapp["First Response Time"] = pd.to_timedelta(df_goapp["First Response Time"], errors='coerce')
    df_goapp["Total Open Time"] = pd.to_timedelta(df_goapp["Total Open Time"], errors='coerce')

if df_interaksi is not None and "Created" in df_interaksi.columns:
    df_interaksi["Created"] = robust_parse_datetime(df_interaksi["Created"])

if df_admin_kpi is not None:
    if "Created" in df_admin_kpi.columns:
        df_admin_kpi["Created"] = robust_parse_datetime(df_admin_kpi["Created"])
    if "Finish" in df_admin_kpi.columns:
        df_admin_kpi["Finish"] = robust_parse_datetime(df_admin_kpi["Finish"])

    if "Created" in df_admin_kpi.columns and "Finish" in df_admin_kpi.columns:
        df_admin_kpi["Durasi (Jam)"] = (df_admin_kpi["Finish"] - df_admin_kpi["Created"]).dt.total_seconds() / 3600

    # ===============================
    # ADMIN KPI Scope (SLA & QTY vs QTY-only) — lebih robust
    # ===============================
    if "KPI Scope" not in df_admin_kpi.columns:
        df_admin_kpi["KPI Scope"] = pd.NA

    df_admin_kpi["KPI Scope"] = normalize_text_series(df_admin_kpi["KPI Scope"])

    if "TAG" in df_admin_kpi.columns:
        df_admin_kpi["TAG"] = normalize_text_series(df_admin_kpi["TAG"])

        # compare pakai UPPER biar "New DB" / "NEW DB" / " new  db " gak miss
        tag_u = df_admin_kpi["TAG"].astype("string").str.upper().str.strip()

        sla_qty_tags = {"NEW DB", "NEW BRAND", "NEW BRANCH"}
        qty_only_tags = {"ESO", "REVISI MENU"}

        scope_u = df_admin_kpi["KPI Scope"].astype("string").str.upper().str.strip()
        scope_empty = scope_u.isna() | (scope_u == "") | (scope_u == "<NA>")

        df_admin_kpi.loc[scope_empty & tag_u.isin(sla_qty_tags), "KPI Scope"] = "SLA & QTY"
        df_admin_kpi.loc[scope_empty & tag_u.isin(qty_only_tags), "KPI Scope"] = "QTY"

        still_empty = df_admin_kpi["KPI Scope"].isna()
        if still_empty.any():
            unknown_tags = sorted(df_admin_kpi.loc[still_empty, "TAG"].dropna().unique().tolist())
            df_admin_kpi.loc[still_empty, "KPI Scope"] = "QTY"
            st.warning(f"⚠️ TAG tidak dikenal untuk mapping KPI Scope (dipaksa QTY): {unknown_tags}")

# ===============================
# 📊 Sidebar Filter Umum
# ===============================
st.sidebar.header("📊 Filter Data")
filter_mode = st.sidebar.radio("🎯 Mode Filter Tanggal", ["Per Hari", "Per Bulan", "Per Tahun"], horizontal=True)

# ===============================
# Tentukan sumber tanggal fleksibel
# ===============================
df_tanggal_sources = []
# ADMIN: tanggal HARUS cuma dari df_admin_kpi (biar filter gak kebawa CSAT/dll)
if selected_sheet == "ADMIN":
    tanggal_sources = [df_admin_kpi]
elif selected_sheet == "SUPPORT":
    tanggal_sources = [df, df_visit, df_efftime]
elif selected_sheet == "CARELINE":
    tanggal_sources = [df, df_csat, df_goapp, df_interaksi]
else:  # CUSTCARE
    tanggal_sources = [df, df_goapp, df_csat, df_interaksi]

for df_source in tanggal_sources:
    if df_source is not None and not df_source.empty and "Created" in df_source.columns:
        tmp = df_source.copy()
        tmp["Created"] = robust_parse_datetime(tmp["Created"])
        df_valid = tmp[["Created"]].dropna()
        if not df_valid.empty:
            df_tanggal_sources.append(df_valid)

df_tanggal = pd.concat(df_tanggal_sources, ignore_index=True) if df_tanggal_sources else pd.DataFrame(columns=["Created"])

# Pastikan tanggal valid
if "Created" in df_tanggal.columns:
    df_tanggal["Created"] = pd.to_datetime(df_tanggal["Created"], errors="coerce", dayfirst=True)   
    min_date = df_tanggal["Created"].min()
    max_date = df_tanggal["Created"].max()
else:
    min_date = max_date = pd.to_datetime("today")

start_date = end_date = None

# 🎯 Per Hari
if filter_mode == "Per Hari":
    start_date, end_date = st.sidebar.date_input(
        "📆 Pilih Rentang Tanggal",
        [min_date, max_date],
        min_value=min_date,
        max_value=max_date
    )
    if isinstance(start_date, datetime.date) and isinstance(end_date, datetime.date):
        start_date = datetime.datetime.combine(start_date, datetime.time.min)
        end_date = datetime.datetime.combine(end_date, datetime.time.max)

# 📅 Per Bulan
elif filter_mode == "Per Bulan":
    available_months = sorted(df_tanggal["Created"].dt.month.dropna().unique())
    available_years = sorted(df_tanggal["Created"].dt.year.dropna().unique())

    month_map = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
        5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
        9: "September", 10: "Oktober", 11: "November", 12: "Desember"
    }

    col1, col2 = st.sidebar.columns(2)
    selected_month = col1.selectbox("📅 Pilih Bulan", available_months, format_func=lambda x: month_map[x])
    selected_year = int(col2.selectbox("📅 Pilih Tahun", available_years))

    start_date = datetime.datetime(int(selected_year), int(selected_month), 1)
    end_day = calendar.monthrange(int(selected_year), int(selected_month))[1]
    end_date = datetime.datetime(int(selected_year), int(selected_month), end_day, 23, 59, 59)

# 📆 Per Tahun (multi-bulan)
elif filter_mode == "Per Tahun":
    df_tanggal["Created"] = pd.to_datetime(df_tanggal["Created"], errors='coerce', dayfirst=True)

    available_years = sorted(df_tanggal["Created"].dropna().dt.year.astype(int).unique())
    selected_year = int(st.sidebar.selectbox("📅 Pilih Tahun", available_years))

    month_map = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
        5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
        9: "September", 10: "Oktober", 11: "November", 12: "Desember"
    }
    reverse_month_map = {v: k for k, v in month_map.items()}

    available_months = sorted(df_tanggal[df_tanggal["Created"].dt.year == selected_year]["Created"].dt.month.unique())
    month_labels = [month_map[m] for m in available_months]
    selected_months = st.sidebar.multiselect("📅 Pilih Beberapa Bulan", month_labels)

    selected_month_numbers = [reverse_month_map[m] for m in selected_months]
    if selected_month_numbers:
        start_date = datetime.datetime(selected_year, min(selected_month_numbers), 1)
        end_date = datetime.datetime(selected_year, max(selected_month_numbers), monthrange(selected_year, max(selected_month_numbers))[1], 23, 59, 59)

# 👤 Pilih Agent (MULTI + opsi "All")
df_sources = [df, df_csat, df_goapp, df_efftime, df_interaksi, df_admin_kpi]
assign_to_combined = pd.concat(
    [d[["Assign To"]] for d in df_sources if d is not None and "Assign To" in d.columns],
    ignore_index=True
)
assign_to_combined["Assign To"] = assign_to_combined["Assign To"].astype(str).str.strip()

# Daftar agent unik
if not assign_to_combined.empty:
    support_options = sorted(assign_to_combined["Assign To"].dropna().unique().tolist())
    agent_options = ["All"] + support_options
    # default hanya "All" supaya tidak memenuhi sidebar dengan chip agent
    selected_raw = st.sidebar.multiselect("👤 Pilih Agent:", options=agent_options, default=["All"],
                                          help="Pilih 'All' untuk semua agent, atau kosongkan untuk kembali ke 'All'.")
else:
    support_options = []
    selected_raw = ["All"]

# Normalisasi pilihan:
# - Jika "All" dipilih ATAU user tidak pilih apa pun → gunakan semua agent
# - Selain itu → gunakan daftar yang dipilih (kecuali string "All")
use_all = ("All" in selected_raw) or (len(selected_raw) == 0)
selected_agents = support_options if use_all else [a for a in selected_raw if a != "All"]

# Kompatibilitas variabel lama utk fungsi2 yang masih cek "All"
support_filter = selected_agents[0] if len(selected_agents) == 1 else "All"


# ⚙️ Pilih Service (jika tersedia)
if "Services" in df.columns:
    service_options = ["All"] + sorted(df["Services"].dropna().unique().tolist())
    layanan = st.session_state.get("layanan", "All")
    if "layanan" not in st.session_state:
        st.session_state["layanan"] = "All"
else:
    service_options = ["All"]
    layanan = "All"

# ===============================
# 🧼 Filtering Data Tiket
# ===============================
df_filtered = df.copy()

if start_date and end_date and "Created" in df_filtered.columns:
    df_filtered = df_filtered[
        (df_filtered["Created"] >= start_date) &
        (df_filtered["Created"] <= end_date)
    ]

if filter_mode == "Per Tahun" and "Created" in df_filtered.columns and 'selected_month_numbers' in locals():
    df_filtered = df_filtered[df_filtered["Created"].dt.month.isin(selected_month_numbers)]

if "Assign To" in df_filtered.columns and selected_agents:
    df_filtered = df_filtered[df_filtered["Assign To"].isin(selected_agents)]

if layanan != "All" and "Services" in df_filtered.columns:
    df_filtered = df_filtered[df_filtered["Services"] == layanan]

# ===============================
# 🧼 Filtering Data CSAT
# ===============================
df_csat_filtered = df_csat.copy() if df_csat is not None else pd.DataFrame()

if start_date and end_date and "Created" in df_csat_filtered.columns:
    df_csat_filtered = df_csat_filtered[
        (df_csat_filtered["Created"] >= start_date) &
        (df_csat_filtered["Created"] <= end_date)
    ]
if "Assign To" in df_csat_filtered.columns and selected_agents:
    df_csat_filtered = df_csat_filtered[df_csat_filtered["Assign To"].isin(selected_agents)]


# ===============================
# 🧼 Filtering Data GOAPP
# ===============================
df_goapp_filtered = df_goapp.copy() if df_goapp is not None else pd.DataFrame()

if start_date and end_date and "Created" in df_goapp_filtered.columns:
    df_goapp_filtered = df_goapp_filtered[
        (df_goapp_filtered["Created"] >= start_date) &
        (df_goapp_filtered["Created"] <= end_date)
    ]
if "Assign To" in df_goapp_filtered.columns and selected_agents:
    df_goapp_filtered = df_goapp_filtered[df_goapp_filtered["Assign To"].isin(selected_agents)]

# ===============================
# 🧼 Filtering Data Visit
# ===============================
df_visit_filtered = df_visit.copy() if df_visit is not None else pd.DataFrame()

if start_date and end_date and "Schedule Date" in df_visit_filtered.columns:
    df_visit_filtered = df_visit_filtered[
        (df_visit_filtered["Schedule Date"] >= start_date) &
        (df_visit_filtered["Schedule Date"] <= end_date)
    ]
if "Assign To" in df_visit_filtered.columns and selected_agents:
    df_visit_filtered = df_visit_filtered[df_visit_filtered["Assign To"].isin(selected_agents)]

# ===============================
# 🧼 Filtering Data Activity
# ===============================
df_efftime_filtered = df_efftime.copy() if df_efftime is not None else pd.DataFrame()

if start_date and end_date and "Schedule Date" in df_efftime_filtered.columns:
    df_efftime_filtered = df_efftime_filtered[
        (df_efftime_filtered["Schedule Date"] >= start_date) &
        (df_efftime_filtered["Schedule Date"] <= end_date)
    ]
if "Assign To" in df_efftime_filtered.columns and selected_agents:
    df_efftime_filtered = df_efftime_filtered[df_efftime_filtered["Assign To"].isin(selected_agents)]

# ===============================
# Filtering Data Interaksi
# ===============================
df_interaksi_filtered = df_interaksi.copy() if df_interaksi is not None else pd.DataFrame()

if start_date and end_date and "Created" in df_interaksi_filtered.columns:
    df_interaksi_filtered = df_interaksi_filtered[
        (df_interaksi_filtered["Created"] >= start_date) &
        (df_interaksi_filtered["Created"] <= end_date)
    ]

if "Assign To" in df_interaksi_filtered.columns and selected_agents:
    df_interaksi_filtered = df_interaksi_filtered[
        df_interaksi_filtered["Assign To"].isin(selected_agents)
    ]

# ===============================
# Filtering Data Admin
# ===============================
df_admin_kpi_filtered = df_admin_kpi.copy() if df_admin_kpi is not None else pd.DataFrame()

if start_date and end_date and "Created" in df_admin_kpi_filtered.columns:
    df_admin_kpi_filtered = df_admin_kpi_filtered[
        (df_admin_kpi_filtered["Created"] >= start_date) &
        (df_admin_kpi_filtered["Created"] <= end_date)
    ]

if "Assign To" in df_admin_kpi_filtered.columns and selected_agents:
    df_admin_kpi_filtered = df_admin_kpi_filtered[df_admin_kpi_filtered["Assign To"].isin(selected_agents)]


# ===============================
# 🧭 Penentuan Label Tab Dinamis
# ===============================
if selected_sheet == "SUPPORT":
    tab_labels = ["📄 Data Tiket", "🗓️ Data Visit", "⏱️ Activity"]
elif selected_sheet == "CARELINE":
    tab_labels = ["📄 Data Tiket", "⭐ Data CSAT", "⏱️ Response Time", "🗣️ Data Interaksi"]
elif selected_sheet == "ADMIN":
    tab_labels = ["📌 KPI Admin", "⭐ Data CSAT"]
else:  # CUSTCARE
    tab_labels = ["📄 Data Tiket", "⏱️ Response Time", "⭐ Data CSAT", "🗣️ Data Interaksi"]

if "last_filter" not in st.session_state:
    st.session_state.last_filter = (selected_sheet, start_date, end_date, support_filter)

current_filter = (selected_sheet, start_date, end_date, support_filter)

if "active_tab" not in st.session_state or st.session_state.active_tab not in tab_labels:
    st.session_state.active_tab = tab_labels[0]

# Update hanya jika filter berubah
if st.session_state.last_filter != current_filter:
    if st.session_state.active_tab not in tab_labels:
        st.session_state.active_tab = tab_labels[0]
    st.session_state.last_filter = current_filter

tabs = st.tabs(tab_labels)

for i, tab in enumerate(tabs):
    with tab:
        label = tab_labels[i]
        st.session_state.active_tab = label

        if label == "📌 KPI Admin" and selected_sheet == "ADMIN":
            render_tab_admin_kpi(df_admin_kpi_filtered, sla_hours=48, selected_agents=selected_agents)

        elif label == "📄 Data Tiket":
            # BIARIN buat SUPPORT/CARELINE/CUSTCARE
            total_tiket, selesai_24_jam, selesai_lebih_24_jam, belum_selesai, avg_durasi = calculate_ticket_metrics(df_filtered)
            render_tab_tiket(
                df_filtered, layanan, service_options,
                total_tiket, selesai_24_jam, selesai_lebih_24_jam,
                belum_selesai, avg_durasi, support_filter
            )

        elif label == "🗓️ Data Visit" and selected_sheet == "SUPPORT":
            render_tab_visit(df_visit_filtered, support_filter)

        elif label == "⭐ Data CSAT" and selected_sheet in ["CARELINE", "ADMIN", "CUSTCARE"]:
            render_tab_csat(df_csat_filtered, support_filter)

        elif label == "⏱️ Response Time" and selected_sheet in ["CARELINE", "CUSTCARE"]:
            render_tab_response_time(df_goapp_filtered, support_filter)

        elif label == "⏱️ Activity" and selected_sheet == "SUPPORT":
            render_tab_activity(df_efftime_filtered, support_filter)

        elif label == "🗣️ Data Interaksi" and selected_sheet in ["CARELINE", "CUSTCARE"]:
            render_tab_interaksi(df_interaksi_filtered, df_goapp_filtered)

# 🔄 Tombol Refresh
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
