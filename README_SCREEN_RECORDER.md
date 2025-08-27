## Windows Screen Recorder (Python + ffmpeg)

A small Python CLI to record the full desktop, a specific window, or a rectangular region to MP4. Uses ffmpeg under the hood.

### Prerequisites

- Windows 10/11
- Python 3.9+
- ffmpeg installed and on PATH (or pass `--ffmpeg C:\\path\\to\\ffmpeg.exe`)
  - Download builds: `https://www.gyan.dev/ffmpeg/builds/` or `https://ffmpeg.org/download.html`

### Quick check

```bash
python screen_recorder.py check-ffmpeg
```

### List windows and audio devices

```bash
python screen_recorder.py list-windows
python screen_recorder.py list-audio-devices
```

### Record examples

- Full desktop, 30 fps, cursor shown:
```bash
python screen_recorder.py record --mode desktop --fps 30 --output desktop.mp4
```

- A specific window by title (use `list-windows` to find it):
```bash
python screen_recorder.py record --mode window --window-title "Calculator" --output calc.mp4
```

- A rectangular region at (x=100, y=200), size 1280x720:
```bash
python screen_recorder.py record --mode region --x 100 --y 200 --width 1280 --height 720 --output region.mp4
```

- With microphone audio (pick a device name from `list-audio-devices`):
```bash
python screen_recorder.py record --mode desktop --audio-device "Microphone (Realtek(R) Audio)" --output with_mic.mp4
```

Press Ctrl+C to stop. The script sends `q` to ffmpeg for a clean finish.

### Encoding controls

- `--crf` (default 23): lower = higher quality and larger file (18–28 typical)
- `--preset` (default veryfast): faster → larger files; slower → smaller files
- `--audio-bitrate` (default 160): kbps for AAC audio when `--audio-device` is set
- `--duration`: optional fixed length recording in seconds

### Notes

- Window capture uses ffmpeg `gdigrab` with `title=...`. The title must match exactly.
- Region capture uses `gdigrab` offsets; coordinates follow your current display scaling.
- System audio capture typically requires a loopback/virtual device (e.g., "Stereo Mix" or VB-CABLE). Use `list-audio-devices` to discover available inputs.


