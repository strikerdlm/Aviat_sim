import sys
from pathlib import Path
from typing import List, Tuple, Optional

import numpy as np
import pandas as pd
from xml.etree import ElementTree as ET
from pyproj import Transformer

try:
    import pyvista as pv
except Exception as exc:
    raise SystemExit(
        "PyVista is required to run this simulation.\n"
        "Install dependencies with:\n"
        "  pip install -r requirements.txt"
    ) from exc


def parse_csv(csv_path: Path) -> pd.DataFrame:
    """
    Load and clean the recorded flight/instrument data.

    Returns a DataFrame with derived columns:
    - time_sec: seconds from start
    - ground_speed_ms: ground speed in meters per second
    - radar_alt_m: radar altitude in meters (clipped at >= 0)
    - vertical_speed_mps: vertical speed in meters per second
    """
    df = pd.read_csv(csv_path, engine="python")

    required_cols = {
        "Ground Speed": "ground_speed",
        "Local Hour": "hour",
        "Local Minute": "minute",
        "Local Second": "second",
    }
    for original in required_cols.keys():
        if original not in df.columns:
            raise ValueError(f"CSV missing required column: {original}")

    df = df.copy()
    df.rename(columns=required_cols, inplace=True)

    if "Altitude Radar" in df.columns:
        df["radar_alt_ft"] = pd.to_numeric(
            df["Altitude Radar"], errors="coerce"
        )
    else:
        df["radar_alt_ft"] = np.nan

    if "Vertical Speed" in df.columns:
        df["vertical_speed_fpm"] = pd.to_numeric(
            df["Vertical Speed"], errors="coerce"
        )
    else:
        df["vertical_speed_fpm"] = np.nan

    df["ground_speed_knots"] = pd.to_numeric(
        df["ground_speed"], errors="coerce"
    )
    df["hour"] = pd.to_numeric(df["hour"], errors="coerce")
    df["minute"] = pd.to_numeric(df["minute"], errors="coerce")
    df["second"] = pd.to_numeric(df["second"], errors="coerce")

    df.dropna(subset=["hour", "minute", "second"], inplace=True)
    df["abs_time_sec"] = df["hour"] * 3600 + df["minute"] * 60 + df["second"]
    df.sort_values("abs_time_sec", inplace=True)
    first_time = df["abs_time_sec"].iloc[0]
    df["time_sec"] = df["abs_time_sec"] - first_time

    df["ground_speed_knots"].fillna(0.0, inplace=True)
    df["ground_speed_ms"] = df["ground_speed_knots"] * 0.514444

    df["radar_alt_m"] = (
        (df["radar_alt_ft"].fillna(0.0) * 0.3048).clip(lower=0.0)
    )
    df["vertical_speed_mps"] = df["vertical_speed_fpm"].fillna(0.0) * 0.00508

    keep_cols = [
        "time_sec",
        "ground_speed_ms",
        "radar_alt_m",
        "vertical_speed_mps",
        "ground_speed_knots",
    ]
    return df[keep_cols].reset_index(drop=True)


def parse_kml_coordinates(kml_path: Path) -> List[Tuple[float, float, float]]:
    """
    Extract all coordinates from LineStrings in a KML file.

    Returns a list of (lon, lat, alt) tuples.
    Altitude is used as-is if present; otherwise defaults to 0.
    """
    tree = ET.parse(kml_path)
    root = tree.getroot()

    ns = {
        "kml": "http://www.opengis.net/kml/2.2",
        "gx": "http://www.google.com/kml/ext/2.2",
    }

    coordinates: List[Tuple[float, float, float]] = []
    for linestring in root.findall(".//kml:LineString", ns):
        coord_elem = linestring.find("kml:coordinates", ns)
        if coord_elem is None or coord_elem.text is None:
            continue
        raw = coord_elem.text.strip()
        if not raw:
            continue
        for triplet in raw.replace("\n", " ").split():
            parts = triplet.split(",")
            if len(parts) < 2:
                continue
            lon = float(parts[0])
            lat = float(parts[1])
            alt = float(parts[2]) if len(parts) > 2 and parts[2] != "" else 0.0
            coordinates.append((lon, lat, alt))

    if len(coordinates) < 2:
        raise ValueError(
            "KML contains fewer than two coordinates to form a path"
        )

    return coordinates


def project_lonlat_to_local_xy(
    lonlat: np.ndarray,
    origin_lon: float,
    origin_lat: float,
) -> np.ndarray:
    """
    Project WGS84 lon/lat to a local planar coordinate system (meters) centered
    on the origin using an azimuthal equidistant projection.
    """
    proj_out = (
        f"+proj=aeqd +lat_0={origin_lat} +lon_0={origin_lon} "
        f"+x_0=0 +y_0=0 +ellps=WGS84 +units=m +no_defs"
    )
    transformer = Transformer.from_crs("epsg:4326", proj_out, always_xy=True)
    xs, ys = transformer.transform(lonlat[:, 0], lonlat[:, 1])
    return np.column_stack([xs, ys])


def compute_arclength(points_xy: np.ndarray) -> np.ndarray:
    diffs = np.diff(points_xy, axis=0)
    seg_lengths = np.linalg.norm(diffs, axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg_lengths)])
    return s


def interpolate_polyline(
    points: np.ndarray,
    s: np.ndarray,
    s_query: np.ndarray,
) -> np.ndarray:
    """
    Interpolate a polyline parameterized by cumulative arclength s.
    """
    x = np.interp(s_query, s, points[:, 0])
    y = np.interp(s_query, s, points[:, 1])
    if points.shape[1] == 3:
        z = np.interp(s_query, s, points[:, 2])
        return np.column_stack([x, y, z])
    return np.column_stack([x, y])


def resample_path_by_speed(
    path_xy: np.ndarray,
    times: np.ndarray,
    ground_speed_ms: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Map a time series with speeds to positions along a path by distance
    traveled.

    Returns:
    - s_along: cumulative distance along the path for each time sample
    - xy_samples: positions along the path corresponding to s_along
    """
    s_path = compute_arclength(path_xy)
    total_path_len = float(s_path[-1])

    dt = np.diff(times, prepend=times[0])
    dt[0] = 0.0
    distances = ground_speed_ms * dt
    s_travel = np.cumsum(distances)
    s_travel = np.clip(s_travel, 0.0, total_path_len)

    xy_samples = interpolate_polyline(path_xy, s_path, s_travel)
    return s_travel, xy_samples


def compute_orientation(
    positions: np.ndarray,
    ground_speed_ms: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute yaw, pitch, and roll angles (degrees) for the model based on
    motion.

    - yaw: from horizontal track direction
    - pitch: from vertical slope dz/ds
    - roll: bank angle from horizontal path curvature and speed
    """
    pos = positions

    # Parameterize by uniform index to avoid non-monotonic time issues
    u = np.arange(pos.shape[0], dtype=float)
    dx_du = np.gradient(pos[:, 0], u)
    dy_du = np.gradient(pos[:, 1], u)
    dz_du = np.gradient(pos[:, 2], u)

    # Heading from track
    yaw = np.degrees(np.arctan2(dx_du, dy_du))

    # Slope-based pitch
    ds_du = np.maximum(np.hypot(dx_du, dy_du), 1e-6)
    dz_ds = dz_du / ds_du
    pitch = np.degrees(np.arctan2(dz_ds, 1.0))

    # Curvature-based roll using derivatives w.r.t. arc length
    dx_ds = dx_du / ds_du
    dy_ds = dy_du / ds_du
    d_dx_ds_du = np.gradient(dx_ds, u)
    d_dy_ds_du = np.gradient(dy_ds, u)
    d_dx_ds_ds = d_dx_ds_du / ds_du
    d_dy_ds_ds = d_dy_ds_du / ds_du
    denom = np.maximum((dx_ds**2 + dy_ds**2) ** 1.5, 1e-6)
    curvature = (dx_ds * d_dy_ds_ds - dy_ds * d_dx_ds_ds) / denom

    g = 9.80665
    roll = np.degrees(np.arctan2((ground_speed_ms**2) * curvature, g))

    return yaw, pitch, roll


def build_path_polydata(points_xyz: np.ndarray) -> pv.PolyData:
    num_points = points_xyz.shape[0]
    lines = np.hstack([num_points, np.arange(num_points)]).astype(np.int64)
    poly = pv.PolyData(points_xyz)
    poly.lines = lines
    return poly


def run_simulation(
    csv_path: Path,
    kml_path: Path,
    stl_path: Path,
    yaw_offset_deg: float = 0.0,
    pitch_offset_deg: float = 0.0,
    roll_offset_deg: float = 0.0,
    model_scale: float = 1.0,
    time_scale: float = 1.0,
    offscreen: bool = False,
    movie_path: Optional[Path] = None,
):
    df = parse_csv(csv_path)

    coords = parse_kml_coordinates(kml_path)
    lonlat = np.array([[lon, lat] for lon, lat, _alt in coords], dtype=float)
    origin_lon, origin_lat = lonlat[0, 0], lonlat[0, 1]
    xy = project_lonlat_to_local_xy(lonlat, origin_lon, origin_lat)

    times = df["time_sec"].to_numpy(dtype=float)
    ground_speed_ms = df["ground_speed_ms"].to_numpy(dtype=float)
    radar_alt_m = df["radar_alt_m"].to_numpy(dtype=float)

    s_travel, xy_samples = resample_path_by_speed(xy, times, ground_speed_ms)

    z_series = radar_alt_m
    positions = np.column_stack([xy_samples[:, 0], xy_samples[:, 1], z_series])
    yaw, pitch, roll = compute_orientation(positions, ground_speed_ms)

    try:
        mesh = pv.read(str(stl_path))
    except Exception as exc:
        raise SystemExit(f"Failed to read STL model at {stl_path}: {exc}")

    if model_scale != 1.0:
        mesh = mesh.scale(model_scale, inplace=False)

    mesh_center = np.asarray(mesh.center, dtype=float)

    path_poly = build_path_polydata(
        np.column_stack([xy, np.zeros_like(xy[:, 0])])
    )

    plotter = pv.Plotter(off_screen=offscreen)
    plotter.add_axes()
    plotter.set_background("black")
    plotter.add_mesh(
        path_poly,
        color="deepskyblue",
        line_width=3,
        name="path",
    )

    actor = plotter.add_mesh(
        mesh,
        color="gray",
        smooth_shading=True,
        name="uh60",
    )
    # Rotate about the model's geometric center without changing mesh points
    actor.SetOrigin(
        float(mesh_center[0]),
        float(mesh_center[1]),
        float(mesh_center[2]),
    )

    cam_pos = (positions[0, 0] + 120.0, positions[0, 1] + 120.0, 80.0)
    plotter.camera.position = cam_pos
    plotter.camera.focal_point = positions[0].tolist()
    plotter.camera.up = (0.0, 0.0, 1.0)

    def hud_text(i: int) -> str:
        gs = df["ground_speed_knots"].iat[i] if i < len(df) else 0.0
        alt = df["radar_alt_m"].iat[i] * 3.28084 if i < len(df) else 0.0
        vs = (
            df["vertical_speed_mps"].iat[i] * 196.850394
            if i < len(df)
            else 0.0
        )
        t = times[i] if i < len(times) else 0.0
        return (
            f"T+{t:6.1f}s\n"
            f"GS: {gs:6.1f} kt\n"
            f"RA: {alt:6.1f} ft\n"
            f"VS: {vs:6.0f} fpm\n"
            f"Yaw/Pitch/Roll: {yaw[i]:.1f}/"
            f"{pitch[i]:.1f}/{roll[i]:.1f} deg"
        )

    plotter.add_text(
        hud_text(0),
        position="upper_left",
        font_size=10,
        name="hud",
    )

    num_frames = len(times)

    def update_frame(i: int):
        x, y, z = positions[i]
        actor.SetPosition(float(x), float(y), float(z))
        actor.SetOrientation(
            float(roll[i] + roll_offset_deg),
            float(pitch[i] + pitch_offset_deg),
            float(yaw[i] + yaw_offset_deg),
        )
        plotter.remove_actor("hud")
        plotter.add_text(
            hud_text(i),
            position="upper_left",
            font_size=10,
            name="hud",
        )
        return

    def frame_generator():
        for i in range(num_frames):
            yield i

    plotter.add_text(
        "Black Hawk MOJO69 – 3D Path + HUD\n"
        "Keys: p Pause, q Quit",
        position="lower_left",
        font_size=10,
        name="help",
    )

    # Optional MP4 recording
    if movie_path is not None:
        # Requires imageio-ffmpeg (installed with imageio) or system ffmpeg
        plotter.open_movie(str(movie_path))

    # Render loop compatible with older PyVista versions (no Plotter.animate)
    plotter.show(auto_close=False)
    for i in frame_generator():
        update_frame(i)
        plotter.render()
        if movie_path is not None:
            plotter.write_frame()

    if movie_path is not None or offscreen:
        plotter.close()
    else:
        # Keep window open for interaction after animating
        plotter.show()


def main():
    workspace = Path(__file__).resolve().parent
    csv_path = workspace / "Data.csv"
    kml_path = workspace / "MOJO69 Flight Path.kml"
    stl_path = workspace / "UH-60_Blackhawk.stl"

    if not csv_path.exists():
        raise SystemExit(f"Missing CSV at {csv_path}")
    if not kml_path.exists():
        raise SystemExit(f"Missing KML at {kml_path}")
    if not stl_path.exists():
        raise SystemExit(f"Missing STL at {stl_path}")

    yaw_offset = 0.0
    pitch_offset = 0.0
    roll_offset = 0.0
    model_scale = 1.0
    time_scale = 1.0
    offscreen_flag = False

    out_movie: Optional[Path] = None

    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg.startswith("--yaw="):
                yaw_offset = float(arg.split("=", 1)[1])
            elif arg.startswith("--pitch="):
                pitch_offset = float(arg.split("=", 1)[1])
            elif arg.startswith("--roll="):
                roll_offset = float(arg.split("=", 1)[1])
            elif arg.startswith("--scale="):
                model_scale = float(arg.split("=", 1)[1])
            elif arg.startswith("--time-scale="):
                time_scale = float(arg.split("=", 1)[1])
            elif arg.startswith("--offscreen="):
                offscreen_str = arg.split("=", 1)[1].strip().lower()
                offscreen_flag = offscreen_str in {"1", "true", "yes", "on"}
            elif arg.startswith("--movie="):
                out_movie = Path(arg.split("=", 1)[1]).expanduser().resolve()

    run_simulation(
        csv_path=csv_path,
        kml_path=kml_path,
        stl_path=stl_path,
        yaw_offset_deg=yaw_offset,
        pitch_offset_deg=pitch_offset,
        roll_offset_deg=roll_offset,
        model_scale=model_scale,
        time_scale=time_scale,
        offscreen=offscreen_flag,
        movie_path=out_movie,
    )


if __name__ == "__main__":
    main()
