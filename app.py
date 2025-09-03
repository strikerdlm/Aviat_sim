# flake8: noqa
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
    page_title="VIII Congreso Internacional de la Escuela de Helicópteros para las Fuerzas Armadas",
    page_icon=("icon.png" if os.path.exists("icon.png") else "🚁"),
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    "<h1 style='margin-bottom:6px'>"
    "VIII Congreso Internacional de la Escuela de Helicópteros "
    "para las Fuerzas Armadas"
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

    # NVG/SD article as clean Markdown (Spanish)
    article_md = """
### Revisión operativa para pilotos: NVG y Desorientación Espacial (SD) en helicópteros militares

#### Resumen ejecutivo (para aviadores)
- Riesgo: volar con NVG multiplica por >5 la tasa de accidentes vs día VMC; 43% de los accidentes con SD ocurren con NVG (Braithwaite, 1998).
- Limitaciones clave NVG (ANVIS‑9): agudeza ~20/40, FOV ~40°, sensibilidad al contraste ~50% de lo normal, profundidad degradada.
- Carga de trabajo: máxima bajo NVG; 75% reporta dolor cervical crónico; cada 30° de giro de cabeza suma ~50–100 N al cuello (Parush, 2011).
- Ilusiones: >90% de pilotos helo han vivido ilusiones bajo NVG; “leans”, horizonte falso, somatográvicas y pérdida de horizonte son las más reportadas.
- Mitigación: mínimos meteorológicos estrictos, planificación de obstáculos/cables, escaneo NVG disciplinado + cross‑check de instrumentos, CRM activo, procedimientos IIMC sin demora, uso de ayudas (autopiloto/HTAWS/HMD si equipado).
- Entrenamiento: refrescos SD/NVG regulares (NATO 4–5 años); la experiencia en NVG mejora detección, navegación y evita SD.

#### 1. Por qué importa
- La SD mata. En helicópteros militares ~27% de accidentes involucran SD, y los eventos SD son desproporcionadamente fatales (Braithwaite, 1998; NATO HFM‑118, 2008).
- Con NVG la tasa de accidentes es >5× mayor vs día VMC (9.0 vs 1.66 por 100.000 h), y 43% de los accidentes con SD suceden en vuelos con NVG (Braithwaite, 1998).
- Casuística reciente subraya el peligro:
  - Eglin 2015 (entrenamiento NVG): 11 fallecidos; vuelo bajo 300 ft techo y 1 SM vis, por debajo de mínimos de 1000/3; no transición oportuna a instrumentos (USSOCOM, 2015).
  - Pave Hawk 2018 (combate): 7 fallecidos; impacto con cable de acero de 3/8” entre torres de 341 ft.
  - CV‑22 2010 (infiltración nocturna): 4 fallecidos, 16 heridos.

#### 2. Qué te dan (y qué no) tus ANVIS‑9
- Agudeza: ~20/40 bajo condiciones óptimas; 3–4× menos detalle que a luz diurna. Cables y obstáculos pequeños pueden pasar desapercibidos.
- Contraste: ~50% de lo normal; empeora con menos iluminación. En noche oscura crece el ruido de imagen.
- Campo de visión: ~40° circular; visión “sorbete”. Necesita barrido constante de cabeza para construir SA.
- Profundidad/distancia: imagen “plana”; tendencia a subestimar distancias y razón de cierre. Apóyate en referencias confiables (RA, HTAWS si equipado).
- Alineación: desajustes de 1–2 mrad o diferencias de brillo entre tubos producen fatiga, molestias y errores de profundidad. Ajuste/foco en test lane mejora significativamente la agudeza.

#### 3. Ilusiones que más muerden con NVG
- Leans (viraje inadvertido), horizonte falso (nubes/luces), pérdida de horizonte, somatográvicas (aceleración = falsa actitud), Coriolis con movimientos de cabeza.
- Autocinesis (luces “moviéndose” en la oscuridad), brownout/whiteout y “falsa estacionariedad”.
- Más del 70% de pilotos reportan estas ilusiones; 25% se confunde al entrar IMC inadvertidamente (Lai, 2021). Bajo NVG, >90% ha vivido ilusiones específicas NVG.

#### 4. Carga de trabajo y fisiología
- NVG = mayor workload percibido en simuladores. Mantener escaneo externo, instrumentos, navegación y CRM incrementa la tarea (Parush, 2011).
- Físico: 75% reporta dolor cervical; cada 30° de giro añade ~50–100 N de compresión cervical. Gestiona tiempos, posturas, contrapesos y límites de movimiento.
- Endurance: algunas unidades cuentan 1 h NVG = 1.5 h a efectos de fatiga. Planifica en consecuencia.

#### 5. Patrones de accidente y lecciones
- Eglin 2015: combinación letal de violar mínimos (regla) y fallas de decisión bajo estrés (no ejecutar IIMC a tiempo), sumado a gradiente de autoridad y CRM débil.
- Tendencias: pérdida súbita de referencias (agua, noche sin luna, meteorología degradada), obstáculos invisibles (cables), y sobrecarga/fragmentación de atención.

#### 6. Factores desencadenantes típicos (red flags)
- Noche sin luna / sobre agua / meteorología marginal (neblina, techo bajo, vis reducida).
- Fijación en la imagen NVG y pobre cross‑check de instrumentos.
- Cabeceo/aceleración en despegues/idas al aire sin horizonte visible (somatográvicas).
- Head‑work excesivo por FOV estrecho; fatiga cervical y de atención.
- Gradiente de autoridad: nadie cuestiona decisiones riesgosas.

#### 7. Barreras operacionales que funcionan

##### Planificación
- Mínimos: adhesión estricta a mínimos NVG publicados. Si no se cumplen: NO‑GO o IFR.
- Ruta y obstáculos: estudio detallado de cables/torres; usa datos actualizados y márgenes verticales. Evita “wire environments” con NVG si no son imprescindibles.
- Iluminación: evalúa fase lunar, nubosidad, reflectividad del terreno/agua.
- Endurance/fatiga: ajusta duración y roles de tripulación (rotaciones, descansos).

##### Ejecución
- Escaneo NVG disciplinado: barridos de cabeza lentos y deliberados; evita fijación. Integra una “cruz” de instrumentos agresiva.
- Velocidad/altitud: ajusta perfiles para la visibilidad real NVG y contraste del terreno. Mantén “guardrails” de RA/HTAWS si equipado.
- CRM: briefea “callouts” de desorientación y transferencia de controles. Promueve “challenge and response” sin barreras de jerarquía.
- Automatización: si está disponible, usa SAS/autopiloto (attitude/altitude/heading hold) como red de seguridad; configura modos y límites antes de entrar a DVE.

##### Recuperación IIMC/SD
- Reconocer temprano: “no veo horizonte/referencias” = gatillo. 
- Acción inmediata: transición a instrumentos y ejecutar el procedimiento IIMC estandarizado de la unidad (actitud, potencia, rumbo, ascenso seguro, comunicar, coordinar). Considera activar modos de estabilización/recuperación si disponibles.
- CRM en voz alta: anuncia “IIMC”, transfiere/acepta controles con claridad, el PN vigila instrumentos/altitud/obstáculos, el PM gestiona comunicaciones y navegación.

#### 8. Tecnología y ayudas
- HMD/simbología en el visor: horizonte artificial y FPM en la línea de visión reducen dependencia de referencias externas.
- HTAWS/RA/alertas de banco: barreras contra CFIT y deslizamiento de actitud.
- Autopiloto/SAS: “botón de nivelación” o modos de retención como ayuda de último recurso, si equipado.
- TSAS (táctil): cueing vibrotáctil ha permitido mantener actitud incluso sin visión tras breve entrenamiento; reduce workload (Rupert, 2000).
- Mejoras NVG: fusiones I² + IR y visores digitales amplían FOV/calidad, pero requieren entrenamiento específico.

#### 9. Entrenamiento y política
- Entrenamiento SD/NVG periódico (NATO: cada 4–5 años) con demostraciones prácticas de ilusiones y escenarios NVG/DVE.
- La pericia en NVG importa: usuarios experimentados detectan mejor blancos, navegan y evitan SD (Parush, 2011).
- Integra experiencias reales de tripulación a los escenarios de simulador (entradas IIMC sobre agua, noche sin luna, cables).

#### 10. Reglas de oro NVG/SD
- Si no hay mínimos NVG, no hay misión NVG.
- Planifica como si los cables no existieran en la imagen NVG: márgenes y alternativas.
- Escanea fuera con la cabeza; verifica dentro con instrumentos. Siempre.
- Al primer indicio de pérdida de referencias: instrumentos e IIMC, sin demoras.
- Usa la automatización para estabilizar; no para delegar el pensamiento.
- CRM sin jerarquías: cualquiera puede decir “alto/abortar”.
- Bravo por el “no‑go”: es una decisión de seguridad, no de capacidad.
- La fatiga no perdona en NVG: gestiona tiempos y cuellos.

#### Anexo: briefing de 60 segundos NVG/SD (tripulación)
- Amenazas clave hoy: iluminación, meteo, cables/obstáculos, segmentos de agua/terreno oscuro.
- Mínimos NVG y criterios de abortaje: explícitos.
- Roles: quién vuela, quién monitorea, quién comunica; callouts de SD/IIMC.
- Modos de automatización que usaremos y límites configurados (altitud mínima RA/HTAWS).
- Señales de SD que autorizan transferencia de controles inmediata.
- Plan B/C: IFR pop‑up/derrota de escape/alternos.

#### Cierre
Volar con NVG incrementa el riesgo por limitaciones físicas del sistema y del piloto. El antídoto operativo es simple pero exigente: planificación conservadora, mínimos claros, escaneo disciplinado con instrumentos, CRM activo y recuperación IIMC inmediata cuando toque. Las ayudas tecnológicas y el entrenamiento recurrente suman capas, pero no sustituyen la disciplina básica. Con estas barreras en capas, reducimos la probabilidad de SD y mejoramos el margen cuando la noche “se come” el horizonte.

#### Referencias
- Braithwaite, M. G., Douglass, P. K., Durnford, S. J., & Lucas, G. (1998). The hazard of spatial disorientation during helicopter flight using night vision devices. Aviation, Space, and Environmental Medicine, 69(11), 1038–1044.
- Braithwaite, M. G., Dunford, S. J., Crowley, J. S., Rosado, N. R., & Albano, J. P. (1998). Spatial disorientation in U.S. Army rotary-wing operations. Aviation, Space, and Environmental Medicine, 69, 1031–1037.
- Malpica, Diego. Colombian Air Force (FAC) Research Team. (2025). Spatial disorientation in Colombian Air Force personnel: A cross-sectional analysis. Unpublished internal analysis.
- Eglin Air Force Base. (2015). Black Hawk crash investigation findings released. U.S. Air Force. [eglin.af.mil](https://www.eglin.af.mil/News/Article-Display/Article/813958/black-hawk-crash-investigation-findings-released/)
- Genco, L. V., & Demitry, C. (1998). Evaluation of night vision goggle: Visual acuity degradation while wearing the FV-9 laser eye protection spectacle (USAARL Report No. 98-17). U.S. Army Aeromedical Research Laboratory. [DTIC](https://apps.dtic.mil/sti/citations/ADA349473)
- Gil‑Cabrera, J., Tornero Aguilera, J. F., Sanchez‑Tena, M. Á., Alvarez‑Peregrina, C., Valbuena‑Iglesias, C., & Clemente‑Suárez, V. J. (2020). Aviation-associated spatial disorientation and incidence of visual illusions survey in military pilots. The International Journal of Aerospace Psychology. [https://doi.org/10.1080/24721840.2020.1841562](https://doi.org/10.1080/24721840.2020.1841562)
- Lewkowicz, R., & Biernacki, M. P. (2020). A survey of spatial disorientation incidence in Polish military pilots. International Journal of Occupational Medicine and Environmental Health, 33(6), 791–810. [https://doi.org/10.13075/ijomeh.1896.01621](https://doi.org/10.13075/ijomeh.1896.01621)
- NATO HFM-118 Task Group. (2008). Spatial disorientation training – demonstration and avoidance (RTO-TR-HFM-118). NATO Research and Technology Organisation. [PDF](https://apps.dtic.mil/sti/tr/pdf/ADA493605.pdf)
- Parush, A., Gauthier, M. S., Arseneau, L., & Tang, D. (2011). The human factors of night vision goggles: Perceptual, cognitive, and physical factors that influence performance and safety. Reviews of Human Factors and Ergonomics, 7(1), 1–60. [https://doi.org/10.1177/1557234X11410392](https://doi.org/10.1177/1557234X11410392)
- Poisson, R. J., III, & Miller, M. E. (2014). Spatial disorientation mishap trends in the U.S. Air Force 1993–2013. Aviation, Space, and Environmental Medicine, 85(9), 919–924. [https://doi.org/10.3357/ASEM.3971.2014](https://doi.org/10.3357/ASEM.3971.2014)
- Rogers, B., & Anstis, S. (1972). Intensity versus adaptation and the Pulfrich stereophenomenon. Vision Research, 12(5), 909–928.
- Rupert, A. H. (2000). Tactile situation awareness system: Proprioceptive prostheses for sensory deficiencies. Aviation, Space, and Environmental Medicine, 71(9, Suppl.), A92–A99. [PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6305736/)
- Shappell, S. A., & Wiegmann, D. A. (2000). The Human Factors Analysis and Classification System—HFACS (DOT/FAA/AM-00/7). Federal Aviation Administration Office of Aviation Medicine. [PDF](https://apps.dtic.mil/sti/tr/pdf/ADA567751.pdf)
- Shappell, S. A., & Wiegmann, D. A. (2001). Applying reason: The human factors analysis and classification system (HFACS). Human Factors and Aerospace Safety, 1(1), 59–86.
- Tu, M.-Y., Cheng, C.-C., Hsin, Y.-H., Huang, W.-W., Li, F.-L., Hu, J.-M., Chiang, K.-T., & Lai, C.-Y. (2021). Analysis of in-flight spatial disorientation among military pilots in Taiwan. Journal of Medical Sciences, 41(1), 22–28. [https://doi.org/10.4103/jmedsci.jmedsci_94_20](https://doi.org/10.4103/jmedsci.jmedsci_94_20)
- U.S. Marine Corps Forces Special Operations Command. (2015). MARSOC identifies seven Marines who died in accident. United States Marine Corps. [marines.mil](https://www.marines.mil/News/News-Display/article/580497/marsoc-identifies-seven-marines-who-died-in-accident/)
- Wiley, R. W., & Holly, D. C. (1976). Human visual capabilities in the infrared spectrum (AFAMRL-TR-76-98). Air Force Aerospace Medical Research Laboratory.
"""
    st.markdown(article_md)

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
