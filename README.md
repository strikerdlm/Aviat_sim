## UH-60M Flight Replay Dashboard

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
- Optional internet for CDNs (D3, Leaflet). If offline, use the simple static server instructions below; the app has a CSV parsing fallback built-in.

### Run locally
1. Start a static server from the project root:
   - Python 3: `python3 -m http.server 8000 --directory /workspace`
   - Node: `npx http-server -p 8000 /workspace --silent`
2. Open `http://localhost:8000/dashboard.html` in your browser.

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

