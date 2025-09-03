## UH‑60M Flight Briefing — Streamlit App

This Streamlit application was prepared for the “VIII Congreso Internacional de la Escuela de Helicópteros para las Fuerzas Armadas”. It provides an interactive flight briefing and analysis experience with synchronized instruments, charts, transcripts, and contextual panels.

### Scientific context and sources
The information presented is a scientific analysis of the documents released by U.S. Special Operations Command (2015): “MARSOC/LAANG UH‑60 helicopter incident [FOIA documents]”. See the primary source here: [SOCOM FOIA — MARSOC/LAANG UH‑60 Helicopter Incident](https://www.socom.mil/FOIA/Pages/MARSOC-LAANG-UH-60-Helicopter-Incident.aspx).

### Author
- Diego Malpica, MD — Colombian Air Force (FAC) Research Team  
  ORCID: [https://orcid.org/0000-0002-2257-4940](https://orcid.org/0000-0002-2257-4940)

### Disclaimers
- This analysis does not constitute the view of the Colombian Aerospace Force (Fuerza Aeroespacial Colombiana, FAC).
- This is an academic exercise for the congress and for learning exclusively. It is not official guidance, policy, or an operational recommendation.

### Quick start (Streamlit)
1. Ensure Python 3.9+ is installed.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Place the required data files next to `app.py` (repository root by default):
   - `Data.csv`
   - `MOJO69 Flight Path.kml`
   - `UH-60_Blackhawk.stl` (optional, for the 3D model)
   - `icon.png` (optional)
4. Run the app:
   - `streamlit run app.py`
5. Your browser should open automatically. If not, visit the URL shown in the terminal (typically `http://localhost:8501`).

---

### Legacy HTML dashboard (dashboard.html)
The repository also contains a static web dashboard (`dashboard.html`). The following sections describe and document that legacy interface.

This project replays a UH-60M flight with synchronized instruments, charts, a timeline, transcripts, and a live map. Playback is synchronized to the time fields in `Data.csv` (Local Hour, Local Minute, Local Second).

### Features
- Gauges: TAS, Radio Altimeter, Vertical Speed, Engine Torques (1 & 2)
- Time-synced charts with selectable axes and smoothing
- Transcript list and contextual event highlights
- Interactive timeline with playback controls and markers
- Map with georeferenced flight path from `MOJO69 Flight Path.kml`

### Data mapping
- Local time: `Local Hour`, `Local Minute`, `Local Second`
- TAS: `TAS`
- Radio Altimeter: `Altitude Radar` (used exclusively for ALT; clamped to 0 if invalid)
- Vertical Speed: `Vertical Speed`
- Ground Speed: `Ground Speed`
- Engine Torques: `Eng 1 Torque`, `Eng 2 Torque`

### Requirements
- Modern browser (Chrome/Edge/Firefox/Safari)
- Required data files next to `dashboard.html`: `Data.csv` and `MOJO69 Flight Path.kml`
- One of the following installed and on your PATH (environment must be ready before running):
  - Python 3.9+ (recommended for the simplest built-in HTTP server)
  - Node.js 18+ and npm 9+
- Internet access if using CDN assets (D3, Leaflet) and online map tiles. If offline, see the notes below for using a local static server and local copies of CDN assets; the app includes a CSV parsing fallback when PapaParse is unavailable.

### Quick start (CLI server)
1. Open a terminal and change to the repository root (this folder).
2. Verify your environment is ready:
   - Python: `python3 --version` (or on Windows PowerShell: `py -3 --version`)
   - Node/npm (optional): `node -v && npm -v`
3. Start a local HTTP server from the project root (pick ONE option):
   - Python (Linux/macOS): `python3 -m http.server 8000 --directory .`
   - Python (Windows PowerShell): `py -3 -m http.server 8000 --directory .`
   - Node via npx: `npx http-server -p 8000 . --silent`
     - If `npx` is blocked or unavailable: `npm i -g http-server` then `http-server -p 8000 . --silent`
4. In your browser, open: `http://localhost:8000/dashboard.html`
   - Ensure `Data.csv` and `MOJO69 Flight Path.kml` are located beside `dashboard.html` (repo root by default).

### Usage
- Press Play (▶) to start/stop playback; Spacebar toggles play/pause.
- Drag the time slider or click the chart area to seek.
- Use Left/Right arrows to step 1s; hold Shift for 10s.
- Change playback speed with the Speed selector.
- Choose chart left/right metrics and adjust smoothing as desired.

### Files
- `dashboard.html` — UI layout and external libs.
- `dashboard.css` — dark theme and layout styles.
- `dashboard.js` — instruments, playback, charts, transcript, and map logic.
- `Data.csv` — time series measurements and transcripts.
- `MOJO69 Flight Path.kml` — flight path coordinates for map polyline.
- `Línea de tiempo.md` — timeline events used for markers and highlights (optional).

### Notes on instruments
- ALT gauge reads the radio altimeter (`Altitude Radar`) only. If the value is missing or negative, ALT displays 0.
- TAS gauge is knots from `TAS`.
- Charts and live stats mirror the same fields as the gauges.

### Troubleshooting
- Server won’t start or port busy:
  - Choose another port, e.g., `python3 -m http.server 8080 --directory .` then open `http://localhost:8080/dashboard.html`.
- `python3` not found on Windows:
  - Use `py -3 -m http.server 8000 --directory .` instead.
- `npx` prompts or is blocked by policy:
  - Install once globally: `npm i -g http-server` and run `http-server -p 8000 . --silent`, or use Python’s built-in server.
- Blank page or controls don’t respond:
  - Load via `http://` using a local server (not `file://`).
  - Check the browser console for errors loading `Data.csv` or `MOJO69 Flight Path.kml`.
- CSV parsing issues offline:
  - The app includes a fallback CSV parser; ensure `Data.csv` is in the same directory as `dashboard.html`.
- Map not showing:
  - Requires Leaflet CDN; ensure internet connectivity or replace the CDN URLs with local copies.

### License
This repository includes third-party components under their respective licenses:
- g3 gauges (`g3-master/dist/*`)
- D3 and Leaflet via CDN

