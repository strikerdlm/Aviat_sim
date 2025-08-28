# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

Project purpose
- Replay a UH-60M (MOJO 69) flight with synchronized cockpit instruments, charts, timeline, transcripts, and a live map in the browser (dashboard.html).
- Optionally render a 3D flight visualization using PyVista from the same data (simulate_blackhawk.py).
- Includes a Windows screen recording CLI (screen_recorder.py) for capturing sessions to MP4 via ffmpeg.

Common commands
- Python environment (Windows PowerShell)
  - Create venv and install dependencies
    ```powershell path=null start=null
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    ```

- Run the browser dashboard (from repo root)
  - Start a simple static server and open dashboard
    ```powershell path=null start=null
    python -m http.server 8000
    # then open http://localhost:8000/dashboard.html
    ```
  - Notes
    - Required files next to dashboard.html: Data.csv (time-series + transcripts), MOJO69 Flight Path.kml (map path).
    - CDN dependencies: D3, Leaflet, and PapaParse are loaded from the internet. If offline, replace those <script>/<link> tags with local copies; CSV parsing has a built-in fallback when PapaParse is unavailable.

- 3D flight visualization (PyVista)
  - Render interactive animation using Data.csv, KML, and STL model
    ```powershell path=null start=null
    # default interactive run
    python .\simulate_blackhawk.py

    # off-screen render and save to MP4 (requires imageio-ffmpeg or system ffmpeg)
    python .\simulate_blackhawk.py --offscreen=1 --movie=blackhawk.mp4

    # orientation/scale tweaks (degrees) and model scale
    python .\simulate_blackhawk.py --yaw=10 --pitch=0 --roll=0 --scale=1.0
    ```
  - Inputs expected in repo root: Data.csv, MOJO69 Flight Path.kml, UH-60_Blackhawk.stl

- Windows screen recorder (ffmpeg wrapper)
  - Quick check for ffmpeg
    ```powershell path=null start=null
    python .\screen_recorder.py check-ffmpeg
    ```
  - List windows and audio devices
    ```powershell path=null start=null
    python .\screen_recorder.py list-windows
    python .\screen_recorder.py list-audio-devices
    ```
  - Record examples
    ```powershell path=null start=null
    # Full desktop, 30 fps
    python .\screen_recorder.py record --mode desktop --fps 30 --output desktop.mp4

    # Specific window by title
    python .\screen_recorder.py record --mode window --window-title "Calculator" --output calc.mp4

    # Rectangular region
    python .\screen_recorder.py record --mode region --x 100 --y 200 --width 1280 --height 720 --output region.mp4

    # With microphone audio
    python .\screen_recorder.py record --mode desktop --audio-device "Microphone (Realtek(R) Audio)" --output with_mic.mp4
    ```

- g3 instrument library (only if you need to modify the bundled gauges)
  - The dashboard uses the prebuilt bundle at g3-master/dist/g3.min.js. To rebuild the library:
    ```powershell path=null start=null
    pushd .\g3-master
    npm ci
    npm run build
    popd
    ```

- Linting and tests
  - No linter configuration or test suite is present in this repository.

High-level architecture
- Web dashboard (dashboard.html, dashboard.js, dashboard.css)
  - Goals: synchronized visualization of flight metrics, timeline, transcripts, and a map.
  - Data sources
    - Data.csv: time-aligned records including Local Hour/Minute/Second, TAS, Altitude Radar, Vertical Speed, Ground Speed, Eng 1/2 Torque, Transcripts, Crew.
    - MOJO69 Flight Path.kml: KML LineString(s) for the map path.
    - Optional timeline markers from “Línea de tiempo.md” (if present), parsed as lines like “- HH:MM:SS — text”.
  - Key client-side flows
    - CSV loading: prefers PapaParse via CDN; falls back to a built-in CSV parser if offline.
    - Timebase: computes absolute seconds from Local Hour/Minute/Second and sorts rows; the slider range (tMin–tMax) drives playback and scrubbing.
    - Instruments: gauges are created with the g3 library (g3-master/dist/g3.min.js). The controller is fed via sendMetrics(), which dispatches current values (tas, altitude, vs, tq1, tq2). Altitude uses radio altimeter only; negative/invalid values clamp to 0 for the ALT gauge.
    - Charts: D3-rendered dual-axis line chart with selectable metrics (altitude/tas/gs/vs/tq1/tq2) and optional moving-average smoothing. Cursor syncs to slider time with dots marking current values.
    - Transcript pane: shows lines near the current time window (±10s), highlighting the current-second entry; a “comms bubble” displays the most recent line as an overlay.
    - Timeline markers: positioned along the slider based on parsed times; updated event description fades in/out in sync.
    - Map: Leaflet draws the KML polyline; a circle marker advances along the path using a simple index interpolation across the time range. Online tile server: Carto “dark_all”.

- Python 3D visualization (simulate_blackhawk.py)
  - Pipeline
    1) Read Data.csv and derive time_sec, ground_speed_ms, radar_alt_m (clamped ≥ 0), vertical_speed_mps.
    2) Parse KML LineString coordinates; project WGS84 lon/lat to local XY (meters) via an azimuthal equidistant projection centered on the first point (pyproj).
    3) Resample positions along the path by integrating distance traveled from ground speed over time, then interpolate XY; Z comes from radar altitude.
    4) Compute orientation: yaw from track, pitch from vertical slope, roll from curvature and speed; render with PyVista, adding a HUD and optional MP4 capture.
  - Dependencies: numpy, pandas, pyproj, pyvista, vtk, imageio/imageio-ffmpeg (see requirements.txt).

- g3 gauge library (g3-master)
  - Third-party JS library for instrument panels. The dashboard consumes the prebuilt dist bundle; local development (npm run build) uses rollup.

Notes and caveats
- Offline use: dashboard relies on CDN JS/CSS (D3, Leaflet, PapaParse) and online map tiles; replace with local assets if network access is restricted (map tiles won’t load without internet unless you supply a local tile source).
- Data placement: keep Data.csv and MOJO69 Flight Path.kml in the repo root next to dashboard.html (or update fetch paths accordingly).
- Platform: commands above assume Windows PowerShell; adapt path separators as needed on other platforms.

