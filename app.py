import os
from typing import List, Tuple

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st
from streamlit_echarts5 import st_echarts
from pathlib import Path  # noqa: F401 (placeholder for future static paths)


# --------------
# Helpers & data
# --------------

@st.cache_data(show_spinner=False)
def load_csv(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    # Normalize expected columns with robust fallbacks
    # Column names in Data.csv: Ground Speed, Altitude Radar,
    # Local Hour, Local Minute, Local Second
    rename_map = {
        'Ground Speed': 'ground_speed',
        'Altitude Radar': 'altitude_radar',
        'Vertical Speed': 'vertical_speed',
        'Eng 1 Torque': 'eng1_torque',
        'Eng 2 Torque': 'eng2_torque',
        'Local Hour': 'h',
        'Local Minute': 'm',
        'Local Second': 's',
        'Transcripts': 'transcript',
        'Crew': 'crew'
    }
    for k, v in rename_map.items():
        if k in df.columns:
            df.rename(columns={k: v}, inplace=True)
    # Construct time string HH:MM:SS and seconds-from-start for sorting
    # and filtering

    def mk_ts(row):
        hh = int(row.get('h', 0)) if not pd.isna(row.get('h', np.nan)) else 0
        mm = int(row.get('m', 0)) if not pd.isna(row.get('m', np.nan)) else 0
        ss = int(row.get('s', 0)) if not pd.isna(row.get('s', np.nan)) else 0
        return f"{hh:02d}:{mm:02d}:{ss:02d}"

    df['time_str'] = df.apply(mk_ts, axis=1)
    df['t_seconds'] = (
        df.get('h', 0).fillna(0).astype(int) * 3600
        + df.get('m', 0).fillna(0).astype(int) * 60
        + df.get('s', 0).fillna(0).astype(int)
    )
    # Clamp negative radar altitude to 0 for realism per README
    if 'altitude_radar' in df.columns:
        df['altitude_radar'] = df['altitude_radar'].fillna(0)
        df.loc[df['altitude_radar'] < 0, 'altitude_radar'] = 0
    # Ensure numeric
    for col in ['ground_speed', 'altitude_radar', 'vertical_speed']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


@st.cache_data(show_spinner=False)
def load_timeline_md(path: str) -> list:
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return []
    events = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("- ") and "—" in s:
            events.append(s[2:])
    return events


@st.cache_data(show_spinner=False)
def parse_kml_line_strings(kml_path: str) -> List[List[Tuple[float, float]]]:
    # Minimal KML parser for LineString coordinates
    # We avoid heavy deps; this extracts sequences inside
    # <LineString><coordinates>...</coordinates>
    if not os.path.exists(kml_path):
        return []
    with open(kml_path, 'r', encoding='utf-8') as f:
        text = f.read()
    coords_blocks = []
    start = 0
    while True:
        a = text.find('<coordinates>', start)
        if a == -1:
            break
        b = text.find('</coordinates>', a)
        if b == -1:
            break
        raw = text[a + len('<coordinates>'): b].strip()
        coords = []
        # Coordinates are like: lon,lat,alt lon,lat,alt ...
        for token in raw.replace('\n', ' ').split():
            parts = token.split(',')
            if len(parts) >= 2:
                try:
                    lon = float(parts[0])
                    lat = float(parts[1])
                    coords.append((lon, lat))
                except ValueError:
                    pass
        if coords:
            coords_blocks.append(coords)
        start = b + len('</coordinates>')
    return coords_blocks


def echarts_theme_dark() -> dict:
    return {
        "darkMode": True,
        "color": ["#58a6ff", "#3fb950", "#ff6b6b", "#d2a8ff"],
        "textStyle": {"fontFamily": "Inter, system-ui, Segoe UI, Roboto"},
        "grid": {"left": 40, "right": 24, "top": 40, "bottom": 60},
        "tooltip": {
            "backgroundColor": "rgba(22,27,34,.95)",
            "borderColor": "#30363d",
        },
        "legend": {"textStyle": {"color": "#c9d1d9"}},
        "xAxis": {
            "axisLine": {"lineStyle": {"color": "#2a3645"}},
            "axisLabel": {"color": "#8b949e"},
        },
        "yAxis": {
            "axisLine": {"lineStyle": {"color": "#2a3645"}},
            "axisLabel": {"color": "#8b949e"},
            "splitLine": {"lineStyle": {"color": "#2a3645"}},
        },
    }


@st.cache_data(show_spinner=False)
def load_weather_from_roi(md_path: str) -> pd.DataFrame:
    # Parse "Surface Observations from Hurlburt Tower" table
    if not os.path.exists(md_path):
        return pd.DataFrame()
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return pd.DataFrame()

    start_idx = -1
    for i, ln in enumerate(lines):
        if "Surface Observations from Hurlburt Tower" in ln:
            start_idx = i
            break
    if start_idx == -1:
        return pd.DataFrame()

    tds: List[str] = []
    for ln in lines[start_idx:]:
        s = ln.strip()
        if s.startswith("</table>"):
            break
        if s.startswith("<td>") and s.endswith("</td>"):
            tds.append(s[len("<td>"):-len("</td>")].strip())

    rows = []
    for i in range(0, len(tds), 3):
        chunk = tds[i:i + 3]
        if len(chunk) == 3:
            rows.append(tuple(chunk))

    def fmt_hhmm(s: str) -> str:
        s = s.strip().replace(" ", "")
        if ":" in s:
            return s
        if len(s) == 4 and s.isdigit():
            return f"{s[:2]}:{s[2:]}"
        return s

    def parse_time_pair(cell: str) -> Tuple[str, str]:
        if "/" in cell:
            a, b = cell.split("/", 1)
            return fmt_hhmm(a.strip()), fmt_hhmm(b.strip())
        return fmt_hhmm(cell.strip()), ""

    def parse_visibility(cell: str) -> float:
        try:
            return float(cell.strip())
        except Exception:
            return float("nan")

    def parse_ceiling(cell: str) -> float:
        digits = "".join(ch for ch in cell if ch.isdigit())
        try:
            return float(digits)
        except Exception:
            return float("nan")

    parsed = []
    for time_cell, vis_cell, ceil_cell in rows:
        t_local, t_z = parse_time_pair(time_cell)
        vis = parse_visibility(vis_cell)
        ceil_ft = parse_ceiling(ceil_cell)
        parsed.append({
            "time_local": t_local,
            "time_zulu": t_z,
            "visibility_sm": vis,
            "ceiling_ft": ceil_ft,
        })

    dfw = pd.DataFrame(parsed)
    if not dfw.empty:
        dfw = dfw.dropna(subset=["visibility_sm", "ceiling_ft"], how="all")
    return dfw


# -----------------
# Layout & sections
# -----------------
st.set_page_config(
    page_title="UH‑60M Flight Briefing",
    page_icon=("icon.png" if os.path.exists("icon.png") else "🚁"),
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    "<h1 style='margin-bottom:6px'>"
    "Congreso Internacional de Escuelas de Helicópteros de Latinoamérica "
    "2025 🚁"
    "</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<h2 style='color:#FF4B4B;margin-top:0'>"
    "Análisis de caso: Rendimiento Humano con Dispositivos de Visión "
    "Nocturna"
    "</h2>",
    unsafe_allow_html=True,
)
st.markdown(
    "<div style='color:#FF4B4B;font-weight:600'>"
    "Dr Diego Malpica MD - Medicina Aeroespacial"
    "</div>",
    unsafe_allow_html=True,
)
st.markdown(
    "<div style='color:#FF4B4B'>"
    "Dirección de Medicina Aeroespacial"
    "</div>",
    unsafe_allow_html=True,
)

# Default data sources (hidden from sidebar)
data_csv = "Data.csv"
kml_file = "MOJO69 Flight Path.kml"
stl_file = "UH-60_Blackhawk.stl"


# Sidebar controls (no data source inputs)
with st.sidebar:
    if os.path.exists("icon.png"):
        st.image("icon.png", use_container_width=True)
    st.markdown("### MOJO69 🚁")
    show_stl = st.checkbox("Mostrar modelo 3D (opcional)", value=False)
    if show_stl:
        try:
            from streamlit_stl import stl_from_file
            stl_from_file(
                file_path=stl_file,
                color="#9aa6b2",
                auto_rotate=True,
                height=220,
            )
        except Exception:
            st.caption("UH‑60 STL preview unavailable.")
    st.markdown("---")
    st.header("Filters")
    df = load_csv(data_csv)
    t_min = int(df['t_seconds'].min())
    t_max = int(df['t_seconds'].max())
    default_lo = max(t_min, 72988)
    default_hi = min(t_max, 73299)
    sel = st.slider(
        "Time window (s)",
        min_value=t_min,
        max_value=t_max,
        value=(default_lo, default_hi),
        step=1,
    )
    smooth = st.checkbox("Smooth series (moving avg)", value=True)
    window = st.slider("Smoothing window", 1, 21, 9, step=2)
    st.markdown("---")
    st.header("Chart style")
    chart_style = st.selectbox(
        "Style",
        [
            "Smooth area",
            "Line",
            "Scatter",
            "Sparkline",
        ],
        index=0,
    )
    enable_gradient = st.checkbox("Gradient fill", value=True)
    enable_crosshair = st.checkbox("Axis crosshair", value=True)
    enable_toolbox = st.checkbox("Toolbox (zoom/save/restore)", value=False)
    show_markers = st.checkbox("Show markers (min/max)", value=True)
    declutter = st.checkbox(
        "Declutter (lighter grid, fewer labels)", value=True
    )
    display_mode = st.radio(
        "Display mode",
        ["Combined", "Small multiples"],
        index=0,
        horizontal=True,
    )
    st.markdown("---")
    st.header("Visibility")
    show_map = st.checkbox("Show flight path map", value=True)
    show_gauges = st.checkbox("Show summary gauges (simple)", value=False)
    show_extra = st.checkbox("Show extra plots", value=True)
    if show_extra:
        show_vsi = st.checkbox("Vertical Speed plot", value=True)
        show_torques = st.checkbox("Engine Torques plots", value=True)
    else:
        show_vsi = False
        show_torques = False
    st.markdown("---")
    st.header("Panels")
    show_transcripts = st.checkbox("Transcripciones", value=False)
    pos_transcripts = st.selectbox(
        "Posición de transcripciones",
        ["Right column", "Below charts"],
        index=0,
    )
    show_context = st.checkbox("Contexto del accidente", value=False)
    pos_context = st.selectbox(
        "Posición del contexto",
        ["Right column", "Below charts"],
        index=0,
    )
    show_timeline_panel = st.checkbox(
        "Mostrar línea de tiempo (español)", value=True
    )
    st.markdown("---")
    st.header("Weather chart")
    show_weather_chart = st.checkbox(
        "Show weather (visibility & ceiling)", value=True
    )
    weather_chart_style = st.selectbox(
        "Weather style",
        [
            "2D Bar",
            "2D Line",
        ],
        index=0,
    )


# Top row: two columns with charts/gauges and transcripts/context
col_left, col_right = st.columns([2.2, 1.3], gap="large")

with col_left:
    lo, hi = sel
    dff = df[(df['t_seconds'] >= lo) & (df['t_seconds'] <= hi)].copy()
    if smooth:
        for c in ['ground_speed', 'altitude_radar']:
            if c in dff.columns:
                dff[c] = (
                    dff[c].rolling(window, min_periods=1, center=True).mean()
                )

    x = dff['time_str'].tolist()
    gs = (
        dff.get('ground_speed', pd.Series([np.nan] * len(dff)))
        .fillna(np.nan)
        .tolist()
    )
    alt = (
        dff.get('altitude_radar', pd.Series([np.nan] * len(dff)))
        .fillna(np.nan)
        .tolist()
    )

    def compute_range(values, pad=0.1):
        arr = [v for v in values if v is not None and not np.isnan(v)]
        if not arr:
            return [0, 1]
        vmin, vmax = float(min(arr)), float(max(arr))
        if vmin == vmax:
            return [vmin - 1, vmax + 1]
        span = vmax - vmin
        return [vmin - span * pad, vmax + span * pad]

    if display_mode == "Combined":
        # Modern combined chart with dual axes
        y1_min, y1_max = compute_range(gs)
        y2_min, y2_max = compute_range(alt)
        options = {
            "backgroundColor": "transparent",
            "aria": {"enabled": True},
            "legend": {"top": 4},
            "tooltip": {
                "trigger": "axis",
                "valueFormatter": (
                    "function (v) { return v == null ? '-' : v.toFixed(2); }"
                ),
            },
            "axisPointer": (
                {"type": "cross"} if enable_crosshair else {"type": "line"}
            ),
            "toolbox": (
                {
                    "feature": {
                        "saveAsImage": {},
                        "dataZoom": {"yAxisIndex": "none"},
                        "restore": {},
                    }
                }
                if enable_toolbox
                else {}
            ),
            "dataZoom": [
                {"type": "inside", "throttle": 50},
                {"type": "slider", "bottom": 8, "height": 14},
            ],
            "xAxis": {
                "type": "category",
                "data": x,
                "boundaryGap": False,
                "axisLabel": {"interval": "auto" if not declutter else 5},
            },
            "yAxis": [
                {
                    "type": "value",
                    "name": "Ground Speed (kt)",
                    "min": y1_min,
                    "max": y1_max,
                    "splitLine": {"show": not declutter},
                },
                {
                    "type": "value",
                    "name": "Radar Altitude (ft)",
                    "min": y2_min,
                    "max": y2_max,
                    "splitLine": {"show": False},
                },
            ],
            "series": [
                {
                    "name": "Ground Speed",
                    "type": "scatter" if chart_style == "Scatter" else "line",
                    "yAxisIndex": 0,
                    "showSymbol": chart_style in ["Scatter", "Sparkline"],
                    "symbolSize": 6 if chart_style == "Scatter" else 2,
                    "smooth": chart_style in ["Smooth area", "Line"],
                    "sampling": "lttb",
                    "lineStyle": {"width": 2},
                    "areaStyle": (
                        {
                            "color": {
                                "type": "linear",
                                "x": 0,
                                "y": 0,
                                "x2": 0,
                                "y2": 1,
                                "colorStops": [
                                    {
                                        "offset": 0,
                                        "color": "rgba(88,166,255,.35)",
                                    },
                                    {
                                        "offset": 1,
                                        "color": "rgba(88,166,255,.05)",
                                    },
                                ],
                            }
                        }
                        if enable_gradient and chart_style == "Smooth area"
                        else {"opacity": 0}
                    ),
                    "markLine": (
                        {"data": [{"type": "max"}, {"type": "min"}]}
                        if show_markers
                        else None
                    ),
                    "data": gs,
                },
                {
                    "name": "Radar Altitude",
                    "type": "line",
                    "yAxisIndex": 1,
                    "showSymbol": chart_style == "Sparkline",
                    "smooth": chart_style in ["Smooth area", "Line"],
                    "sampling": "lttb",
                    "lineStyle": {"width": 2},
                    "markLine": (
                        {"data": [{"type": "max"}, {"type": "min"}]}
                        if show_markers
                        else None
                    ),
                    "data": alt,
                },
            ],
        }
        st_echarts(
            options=options,
            height="420px",
            theme=echarts_theme_dark(),
        )
    else:
        # Small multiples: two decluttered charts stacked
        y1_min, y1_max = compute_range(gs)
        y2_min, y2_max = compute_range(alt)
        opt_gs = {
            "backgroundColor": "transparent",
            "legend": {"show": False},
            "tooltip": {"trigger": "axis"},
            "xAxis": {
                "type": "category",
                "data": x,
                "boundaryGap": False,
                "axisLabel": {"interval": 8},
            },
            "yAxis": {
                "type": "value",
                "name": "Ground Speed (kt)",
                "min": y1_min,
                "max": y1_max,
                "splitLine": {"show": not declutter},
            },
            "dataZoom": [
                {"type": "inside"},
                {"type": "slider", "bottom": 6, "height": 12},
            ],
            "series": [
                {
                    "type": "line",
                    "showSymbol": False,
                    "smooth": True,
                    "sampling": "lttb",
                    "areaStyle": (
                        {"opacity": .2} if enable_gradient else {"opacity": 0}
                    ),
                    "data": gs,
                }
            ],
        }
        opt_ra = {
            "backgroundColor": "transparent",
            "legend": {"show": False},
            "tooltip": {"trigger": "axis"},
            "xAxis": {
                "type": "category",
                "data": x,
                "boundaryGap": False,
                "axisLabel": {"interval": 8},
            },
            "yAxis": {
                "type": "value",
                "name": "Radar Altitude (ft)",
                "min": y2_min,
                "max": y2_max,
                "splitLine": {"show": not declutter},
            },
            "dataZoom": [
                {"type": "inside"},
                {"type": "slider", "bottom": 6, "height": 12},
            ],
            "series": [
                {
                    "type": "line",
                    "showSymbol": False,
                    "smooth": True,
                    "sampling": "lttb",
                    "areaStyle": (
                        {"opacity": .2} if enable_gradient else {"opacity": 0}
                    ),
                    "data": alt,
                }
            ],
        }
        st_echarts(opt_gs, height="260px", theme=echarts_theme_dark())
        st_echarts(opt_ra, height="260px", theme=echarts_theme_dark())

    # Flight path map directly under charts in the left column
    if show_map:
        paths = parse_kml_line_strings(kml_file)
        if not paths:
            st.info("No LineString coordinates found in KML.")
        else:
            all_points = [
                (lon, lat)
                for path in paths
                for (lon, lat) in path
            ]
            center_lat = np.mean([lat for _, lat in all_points])
            center_lon = np.mean([lon for lon, _ in all_points])

            data_rows = []
            for path in paths:
                data_rows.append({"path": [[lon, lat] for (lon, lat) in path]})
            path_df = pd.DataFrame(data_rows)

            layer = pdk.Layer(
                "PathLayer",
                path_df,
                get_path="path",
                get_color=[88, 166, 255],
                width_scale=2,
                width_min_pixels=3,
            )
            view_state = pdk.ViewState(
                latitude=center_lat,
                longitude=center_lon,
                zoom=11,
                pitch=45,
                bearing=0,
            )
            st.pydeck_chart(
                pdk.Deck(layers=[layer], initial_view_state=view_state)
            )

    # Optional simple summary gauges (ECharts minimal rings)
    if show_gauges:
        st.markdown("\n")
        g1, g2, g3 = st.columns(3)
        latest = dff.tail(1)
        latest_gs = float(
            latest.get('ground_speed', pd.Series([np.nan])).iloc[0]
        )
        latest_ra = float(
            latest.get('altitude_radar', pd.Series([np.nan])).iloc[0]
        )
        latest_vsi = float(
            latest.get('vertical_speed', pd.Series([np.nan])).iloc[0]
        )

        def ring(name, value, unit):
            return {
                "series": [
                    {
                        "type": "gauge",
                        "startAngle": 210,
                        "endAngle": -30,
                        "min": 0,
                        "max": 1,
                        "axisLine": {"lineStyle": {"width": 8}},
                        "progress": {"show": True, "width": 8},
                        "pointer": {"show": False},
                        "splitLine": {"show": False},
                        "axisTick": {"show": False},
                        "axisLabel": {"show": False},
                        "title": {"show": True, "offsetCenter": [0, "65%"]},
                        "detail": {
                            "valueAnimation": True,
                            "fontSize": 18,
                            "formatter": f"{value:.0f} {unit}",
                        },
                        "data": [{"value": 0.0, "name": name}],
                    }
                ]
            }

        with g1:
            st_echarts(ring("Radar Alt", latest_ra, "ft"), height="150px",
                       theme=echarts_theme_dark())
        with g2:
            st_echarts(ring("VSI", latest_vsi, "fpm"), height="150px",
                       theme=echarts_theme_dark())
        with g3:
            st_echarts(ring("Ground Spd", latest_gs, "kt"), height="150px",
                       theme=echarts_theme_dark())

    # Quick stats removed per requirements

    # Extra plots (optional)
    if show_vsi:
        vsi_vals = (
            dff.get('vertical_speed', pd.Series([np.nan] * len(dff)))
            .fillna(np.nan)
            .tolist()
        )
        vmin, vmax = compute_range(vsi_vals)
        opt_vsi = {
            "backgroundColor": "transparent",
            "legend": {"show": False},
            "tooltip": {"trigger": "axis"},
            "xAxis": {
                "type": "category",
                "data": x,
                "boundaryGap": False,
                "axisLabel": {"interval": 8},
            },
            "yAxis": {
                "type": "value",
                "name": "VSI (fpm)",
                "min": vmin,
                "max": vmax,
                "splitLine": {"show": not declutter},
            },
            "series": [
                {"type": "line", "showSymbol": False, "smooth": True,
                 "data": vsi_vals}
            ],
        }
        st_echarts(opt_vsi, height="220px", theme=echarts_theme_dark())

    if show_torques:
        t1 = (
            dff.get('eng1_torque', pd.Series([np.nan] * len(dff)))
            .fillna(np.nan)
            .tolist()
        )
        t2 = (
            dff.get('eng2_torque', pd.Series([np.nan] * len(dff)))
            .fillna(np.nan)
            .tolist()
        )
        tmin, tmax = compute_range(t1 + t2)
        opt_tq = {
            "backgroundColor": "transparent",
            "tooltip": {"trigger": "axis"},
            "legend": {"top": 0},
            "xAxis": {"type": "category", "data": x, "boundaryGap": False},
            "yAxis": {"type": "value", "min": tmin, "max": tmax},
            "series": [
                {"name": "Eng 1", "type": "line", "showSymbol": False,
                 "smooth": True, "data": t1},
                {"name": "Eng 2", "type": "line", "showSymbol": False,
                 "smooth": True, "data": t2},
            ],
        }
        st_echarts(opt_tq, height="240px", theme=echarts_theme_dark())
    # Weather chart (below plots)
    if 'show_weather_chart' in globals() and show_weather_chart:
        st.markdown("\n")
        wdf = load_weather_from_roi("ROI_UH60 (1).md")
        if wdf.empty:
            st.info("No weather table found in ROI markdown.")
        else:
            times = wdf["time_local"].tolist()
            dataset_3d = {
                "dimensions": ["time", "metric", "z", "actual"],
                "source": []
            }
            for _, r in wdf.iterrows():
                t_local_val = r["time_local"]
                t = (
                    str(t_local_val) if not pd.isna(t_local_val) else ""
                )
                vis_val = r["visibility_sm"]
                vis = (
                    float(vis_val) if not pd.isna(vis_val) else None
                )
                ceil_val = r["ceiling_ft"]
                ceil = (
                    float(ceil_val) if not pd.isna(ceil_val) else None
                )
                if vis is not None:
                    dataset_3d["source"].append({
                        "time": t,
                        "metric": "Visibility (SM)",
                        "z": vis,
                        "actual": vis,
                    })
                if ceil is not None:
                    dataset_3d["source"].append({
                        "time": t,
                        "metric": "Ceiling (ft)",
                        "z": ceil / 100.0,
                        "actual": ceil,
                    })

            dataset_2d = {
                "dimensions": [
                    "time", "Visibility (SM)", "Ceiling (ft)"
                ],
                "source": [
                    {
                        "time": (
                            str(r["time_local"]) if not pd.isna(
                                r["time_local"]
                            ) else ""
                        ),
                        "Visibility (SM)": (
                            float(r["visibility_sm"]) if not pd.isna(
                                r["visibility_sm"]
                            ) else None
                        ),
                        "Ceiling (ft)": (
                            float(r["ceiling_ft"]) if not pd.isna(
                                r["ceiling_ft"]
                            ) else None
                        ),
                    }
                    for _, r in wdf.iterrows()
                ],
            }

            # Compute y-axis ranges to ensure VFR thresholds are visible
            vis_vals = [
                float(v) for v in wdf["visibility_sm"].dropna().tolist()
            ]
            ceil_vals = [
                float(v) for v in wdf["ceiling_ft"].dropna().tolist()
            ]
            v_base_min = min(vis_vals + [3]) if vis_vals else 3
            v_base_max = max(vis_vals + [3]) if vis_vals else 3
            v_span = (v_base_max - v_base_min) or 1.0
            v_min = max(0.0, v_base_min - 0.1 * v_span)
            v_max = v_base_max + 0.1 * v_span
            c_base_min = min(ceil_vals + [1000]) if ceil_vals else 1000
            c_base_max = max(ceil_vals + [1000]) if ceil_vals else 1000
            c_span = (c_base_max - c_base_min) or 1.0
            c_min = max(0.0, c_base_min - 0.1 * c_span)
            c_max = c_base_max + 0.1 * c_span

            if weather_chart_style == "2D Bar":
                # Build explicit data arrays with per-bar colors to avoid
                # any dataset/encode callback issues
                vis_bar_data = []
                ceil_bar_data = []
                for _, r in wdf.iterrows():
                    vv = r["visibility_sm"]
                    cv = r["ceiling_ft"]
                    if not pd.isna(vv):
                        vv_f = float(vv)
                        vis_bar_data.append({
                            "value": vv_f,
                            **({"itemStyle": {"color": "#D90429"}}
                               if vv_f < 3 else {})
                        })
                    else:
                        vis_bar_data.append(None)
                    if not pd.isna(cv):
                        cv_f = float(cv)
                        ceil_bar_data.append({
                            "value": cv_f,
                            **({"itemStyle": {"color": "#2EA043"}}
                               if cv_f >= 1000 else {})
                        })
                    else:
                        ceil_bar_data.append(None)

                options_weather = {
                    "backgroundColor": "transparent",
                    "legend": {"top": 4},
                    "tooltip": {"trigger": "axis"},
                    "toolbox": {"feature": {"saveAsImage": {}}},
                    "dataZoom": [
                        {"type": "inside", "throttle": 50},
                        {"type": "slider", "bottom": 8, "height": 14},
                    ],
                    "xAxis": {
                        "type": "category",
                        "name": "Time",
                        "data": times,
                        "axisLabel": {"color": "#c9d1d9"},
                    },
                    "yAxis": [
                        {"type": "value", "name": "Visibility (SM)",
                         "min": v_min, "max": v_max,
                         "axisLabel": {"color": "#c9d1d9"}},
                        {"type": "value", "name": "Ceiling (ft)",
                         "min": c_min, "max": c_max,
                         "axisLabel": {"color": "#c9d1d9"}},
                    ],
                    "series": [
                        {
                            "type": "bar",
                            "name": "Visibility (SM)",
                            "yAxisIndex": 0,
                            "itemStyle": {"color": "#58a6ff"},
                            "data": vis_bar_data,
                            "markLine": {
                                "silent": True,
                                "symbol": "none",
                                "lineStyle": {
                                    "color": "#FF4B4B",
                                    "type": "dashed",
                                    "width": 2
                                },
                                "label": {"formatter": "3 SM"},
                                "data": [{"yAxis": 3}]
                            },
                            "animation": True,
                            "animationDuration": 1000,
                        },
                        {
                            "type": "bar",
                            "name": "Ceiling (ft)",
                            "yAxisIndex": 1,
                            "itemStyle": {"color": "#D90429"},
                            "data": ceil_bar_data,
                            "markLine": {
                                "silent": True,
                                "symbol": "none",
                                "lineStyle": {
                                    "color": "#FF4B4B",
                                    "type": "dashed",
                                    "width": 2
                                },
                                "label": {"formatter": "1000 ft"},
                                "data": [{"yAxis": 1000}]
                            },
                            "animation": True,
                            "animationDuration": 1000,
                        },
                    ],
                }
                st_echarts(
                    options_weather,
                    height="340px",
                    theme=echarts_theme_dark(),
                )
            else:
                options_weather = {
                    "backgroundColor": "transparent",
                    "legend": {"top": 4},
                    "tooltip": {"trigger": "axis"},
                    "toolbox": {"feature": {"saveAsImage": {}}},
                    "dataset": dataset_2d,
                    "dataZoom": [
                        {"type": "inside", "throttle": 50},
                        {"type": "slider", "bottom": 8, "height": 14},
                    ],
                    "xAxis": {
                        "type": "category",
                        "name": "Time",
                        "axisLabel": {"color": "#c9d1d9"}
                    },
                    "yAxis": [
                        {"type": "value", "name": "Visibility (SM)",
                         "min": v_min, "max": v_max,
                         "axisLabel": {"color": "#c9d1d9"}},
                        {"type": "value", "name": "Ceiling (ft)",
                         "min": c_min, "max": c_max,
                         "axisLabel": {"color": "#c9d1d9"}},
                    ],
                    "series": [
                        {
                            "type": "line",
                            "name": "Visibility (SM)",
                            "yAxisIndex": 0,
                            "smooth": True,
                            "showSymbol": False,
                            "lineStyle": {"width": 2, "color": "#58a6ff"},
                            "encode": {
                                "x": "time",
                                "y": "Visibility (SM)"
                            },
                            "areaStyle": {
                                "opacity": 0.18,
                                "color": "rgba(88, 166, 255, .22)"
                            },
                            "markLine": {
                                "silent": True,
                                "symbol": "none",
                                "lineStyle": {
                                    "color": "#FF4B4B",
                                    "type": "dashed",
                                    "width": 2
                                },
                                "label": {"formatter": "3 SM"},
                                "data": [{"yAxis": 3}]
                            },
                            "animation": True,
                        },
                        {
                            "type": "line",
                            "name": "Ceiling (ft)",
                            "yAxisIndex": 1,
                            "smooth": True,
                            "showSymbol": False,
                            "lineStyle": {"width": 2, "color": "#2EA043"},
                            "encode": {
                                "x": "time",
                                "y": "Ceiling (ft)"
                            },
                            "areaStyle": {
                                "opacity": 0.15,
                                "color": "rgba(46, 160, 67, .20)"
                            },
                            "markLine": {
                                "silent": True,
                                "symbol": "none",
                                "lineStyle": {
                                    "color": "#FF4B4B",
                                    "type": "dashed",
                                    "width": 2
                                },
                                "label": {"formatter": "1000 ft"},
                                "data": [{"yAxis": 1000}]
                            },
                            "animation": True,
                        },
                    ],
                }
                st_echarts(
                    options_weather,
                    height="340px",
                    theme=echarts_theme_dark(),
                )

with col_right:
    if show_transcripts and pos_transcripts == "Right column":
        st.subheader("Transcripts")
        transcripts_box = st.container(border=True)
        with transcripts_box:
            if 'transcript' in df.columns:
                sample = (
                    df[['time_str', 'crew', 'transcript']]
                    .dropna(subset=['transcript'])
                    .head(50)
                    .reset_index(drop=True)
                )
                st.markdown(
                    "<div style='max-height:420px; overflow:auto;"
                    " padding-right:8px'>",
                    unsafe_allow_html=True,
                )
                for _, row in sample.iterrows():
                    crew = str(row.get('crew', '') or '').strip() or "Crew"
                    text = (
                        str(row.get('transcript', '') or '')
                        .strip()
                        .strip('"')
                    )
                    st.markdown(f"**[{row['time_str']}] {crew}**  ")
                    st.markdown(f"{text}")
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.caption("No transcript column found in CSV.")
        st.markdown("---")
    if show_context and pos_context == "Right column":
        st.subheader("Accident context 🛬")
    if show_timeline_panel:
        st.markdown("---")
        st.subheader("Línea de tiempo ✈️")
        events = load_timeline_md("Línea de tiempo.md")
        if events:
            st.markdown(
                "<div style='max-height:420px; overflow:auto;"
                " padding-right:8px'>",
                unsafe_allow_html=True,
            )
            for ev in events:
                st.markdown(f"- {ev}")
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.caption("No se encontró la línea de tiempo.")
        st.markdown(
            "- Weather: 1 SM visibility, 300' overcast; zero moonlight."
        )
        st.markdown(
            "- Direct cause: spatial disorientation; loss of control."
        )
        st.markdown(
            "- Contributing: below-minimum launch, coordination issues."
        )
        st.markdown("- Impact: water strike; non-survivable.")


# (Map rendering moved above, within the left column directly under charts.)


# 3D model now lives only in the sidebar preview (removed from main page)


# Transcripts are now in the right panel above


# Timeline (Spanish) at bottom — removed toggle from main page

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#FF4B4B;font-weight:700'>"
    "Dr Diego Malpica MD" "</div>",
    unsafe_allow_html=True,
)
st.markdown(
    "<div style='text-align:center;color:#FF4B4B'>"
    "Dirección de Medicina Aeroespacial" "</div>",
    unsafe_allow_html=True,
)
st.markdown(
    "<div style='text-align:center;color:#FF4B4B'>"
    "Fuerza Aeroespacial Colombiana" "</div>",
    unsafe_allow_html=True,
)
