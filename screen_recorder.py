import argparse
import datetime
import os
import re
import subprocess
import sys
from typing import List, Optional, Tuple


def build_default_output_path(output: Optional[str]) -> str:
    if output:
        return os.path.abspath(output)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.abspath(f"recording_{timestamp}.mp4")


def ffmpeg_available(ffmpeg_bin: str) -> bool:
    try:
        subprocess.run(
            [ffmpeg_bin, "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return True
    except FileNotFoundError:
        return False


def list_audio_devices(ffmpeg_bin: str) -> Tuple[List[str], str]:
    """Return (devices, raw_output). Uses ffmpeg dshow device
    listing on Windows.
    """
    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-list_devices",
        "true",
        "-f",
        "dshow",
        "-i",
        "dummy",
    ]
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stderr = proc.stderr or ""

    devices: List[str] = []
    in_audio = False
    # Typical lines:
    # [dshow @ 0000021c2b7ad700] DirectShow audio devices
    # (some may be both video and audio devices)
    # [dshow @ 0000021c2b7ad700]  "Microphone (Realtek(R) Audio)"
    # [dshow @ 0000021c2b7ad700]     Alternative name "@device_sw\\{...}"
    for line in stderr.splitlines():
        if "DirectShow audio devices" in line:
            in_audio = True
            continue
        if "DirectShow video devices" in line and in_audio:
            break
        if in_audio:
            m = re.search(r"^\[dshow [^\]]+\]\s+\"(.+?)\"", line)
            if m:
                devices.append(m.group(1))
    return devices, stderr


def enumerate_windows() -> List[Tuple[int, str]]:
    """Enumerate visible top-level windows: returns list of
    (hwnd, title). Windows-only.
    """
    if sys.platform != "win32":
        return []

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    EnumWindows = user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, wintypes.HWND, wintypes.LPARAM
    )
    IsWindowVisible = user32.IsWindowVisible
    GetWindowTextLengthW = user32.GetWindowTextLengthW
    GetWindowTextW = user32.GetWindowTextW
    GetWindowRect = user32.GetWindowRect

    class RECT(ctypes.Structure):
        _fields_ = (
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        )

    windows: List[Tuple[int, str]] = []

    def callback(hwnd, lParam):
        try:
            if not IsWindowVisible(hwnd):
                return True
            length = GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buff = ctypes.create_unicode_buffer(length + 1)
            GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value.strip()
            if not title:
                return True
            rect = RECT()
            if GetWindowRect(hwnd, ctypes.byref(rect)) == 0:
                return True
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            if width <= 0 or height <= 0:
                return True
            windows.append((int(hwnd), title))
        except Exception:
            # Ignore problematic windows
            return True
        return True

    EnumWindows(EnumWindowsProc(callback), 0)
    # Deduplicate by title while keeping order
    seen = set()
    unique: List[Tuple[int, str]] = []
    for hwnd, title in windows:
        key = title
        if key in seen:
            continue
        seen.add(key)
        unique.append((hwnd, title))
    return unique


def build_ffmpeg_command(
    ffmpeg_bin: str,
    mode: str,
    fps: int,
    show_cursor: bool,
    window_title: Optional[str],
    region: Optional[Tuple[int, int, int, int]],
    audio_device: Optional[str],
    crf: int,
    preset: str,
    audio_bitrate_kbps: int,
    duration: Optional[float],
    output_path: str,
) -> List[str]:
    cmd: List[str] = [ffmpeg_bin, "-y"]

    if duration and duration > 0:
        cmd += ["-t", str(duration)]

    # Video input (gdigrab)
    cmd += [
        "-f",
        "gdigrab",
        "-framerate",
        str(fps),
        "-draw_mouse",
        "1" if show_cursor else "0",
    ]
    if mode == "desktop":
        cmd += ["-i", "desktop"]
    elif mode == "window":
        if not window_title:
            raise ValueError("--window-title is required when --mode window")
        cmd += ["-i", f"title={window_title}"]
    elif mode == "region":
        if not region:
            raise ValueError(
                "--x/--y/--width/--height are required when --mode region"
            )
        x, y, w, h = region
        cmd += [
            "-offset_x",
            str(x),
            "-offset_y",
            str(y),
            "-video_size",
            f"{w}x{h}",
            "-i",
            "desktop",
        ]
    else:
        raise ValueError(f"Unknown mode: {mode}")

    # Optional audio input (dshow)
    if audio_device:
        cmd += ["-f", "dshow", "-i", f"audio={audio_device}"]

    # Encoding settings
    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
    ]
    if audio_device:
        cmd += ["-c:a", "aac", "-b:a", f"{audio_bitrate_kbps}k"]
    else:
        # No audio
        cmd += ["-an"]

    # Better mp4 streaming compatibility
    cmd += ["-movflags", "+faststart", output_path]
    return cmd


def run_ffmpeg(cmd: List[str], show_output: bool) -> int:
    print("Starting recording... Press Ctrl+C to stop.")
    try:
        if show_output:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        else:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        try:
            return proc.wait()
        except KeyboardInterrupt:
            if proc.poll() is None and proc.stdin:
                try:
                    proc.stdin.write(b"q")
                    proc.stdin.flush()
                except Exception:
                    pass
            return proc.wait()
    except FileNotFoundError:
        print(
            (
                "Error: ffmpeg not found. "
                "Please install ffmpeg and add it to PATH."
            ),
            file=sys.stderr,
        )
        return 1


def cmd_record(args: argparse.Namespace) -> int:
    ffmpeg_bin = args.ffmpeg or "ffmpeg"
    if not ffmpeg_available(ffmpeg_bin):
        print(
            "ffmpeg is not available. Install from "
            "https://ffmpeg.org/download.html and ensure it's on PATH.",
            file=sys.stderr,
        )
        return 1

    output_path = build_default_output_path(args.output)
    if os.path.isdir(output_path):
        print(
            "Output path is a directory. Provide a file path ending with .mp4",
            file=sys.stderr,
        )
        return 1

    region = None
    if args.mode == "region":
        for name in ("x", "y", "width", "height"):
            if getattr(args, name) is None:
                print(
                    (
                        "--x, --y, --width and --height are required "
                        "for region mode"
                    ),
                    file=sys.stderr,
                )
                return 1
        region = (int(args.x), int(args.y), int(args.width), int(args.height))

    try:
        cmd = build_ffmpeg_command(
            ffmpeg_bin=ffmpeg_bin,
            mode=args.mode,
            fps=int(args.fps),
            show_cursor=not bool(args.hide_cursor),
            window_title=args.window_title,
            region=region,
            audio_device=args.audio_device,
            crf=int(args.crf),
            preset=args.preset,
            audio_bitrate_kbps=int(args.audio_bitrate),
            duration=float(args.duration) if args.duration else None,
            output_path=output_path,
        )
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

    rc = run_ffmpeg(
        cmd,
        show_output=bool(args.show_ffmpeg),
    )
    if rc == 0:
        print(f"Saved to: {output_path}")
    return rc


def cmd_list_windows(_: argparse.Namespace) -> int:
    if sys.platform != "win32":
        print(
            "Window enumeration is only supported on Windows.",
            file=sys.stderr,
        )
        return 1
    wins = enumerate_windows()
    if not wins:
        print("No visible windows found.")
        return 0
    for idx, (_, title) in enumerate(wins, 1):
        print(f"{idx:3d}. {title}")
    print(
        "\nTip: Use the exact title with --window-title when recording a "
        "window."
    )
    return 0


def cmd_list_audio_devices(args: argparse.Namespace) -> int:
    ffmpeg_bin = args.ffmpeg or "ffmpeg"
    if not ffmpeg_available(ffmpeg_bin):
        print(
            "ffmpeg is not available. Install from "
            "https://ffmpeg.org/download.html and ensure it's on PATH.",
            file=sys.stderr,
        )
        return 1
    devices, raw = list_audio_devices(ffmpeg_bin)
    if devices:
        print("Audio devices:")
        for idx, name in enumerate(devices, 1):
            print(f"{idx:3d}. {name}")
        print("\nTip: Pass one of these names to --audio-device")
        return 0
    print("Could not parse audio devices from ffmpeg output. Raw output:")
    print(raw)
    return 0


def cmd_check_ffmpeg(args: argparse.Namespace) -> int:
    ffmpeg_bin = args.ffmpeg or "ffmpeg"
    if ffmpeg_available(ffmpeg_bin):
        out = subprocess.run(
            [ffmpeg_bin, "-version"],
            capture_output=True,
            text=True,
        )
        streams_text = out.stdout or out.stderr or ""
        if streams_text:
            first_line = streams_text.splitlines()[0]
        else:
            first_line = "ffmpeg found"
        print(first_line)
        return 0
    print(
        "ffmpeg not found. Download: "
        "https://www.gyan.dev/ffmpeg/builds/ or "
        "https://ffmpeg.org/download.html and add to PATH."
    )
    return 1


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Record desktop/window/region to MP4 using ffmpeg (Windows)."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # record
    p_rec = sub.add_parser("record", help="Record a screen target to MP4")
    p_rec.add_argument(
        "--mode",
        choices=["desktop", "window", "region"],
        default="desktop",
    )
    p_rec.add_argument(
        "--window-title",
        help="Exact window title (for --mode window)",
    )
    p_rec.add_argument(
        "--x",
        type=int,
        help="Left offset (for --mode region)",
    )
    p_rec.add_argument(
        "--y",
        type=int,
        help="Top offset (for --mode region)",
    )
    p_rec.add_argument(
        "--width",
        type=int,
        help="Region width (for --mode region)",
    )
    p_rec.add_argument(
        "--height",
        type=int,
        help="Region height (for --mode region)",
    )
    p_rec.add_argument("--fps", type=int, default=30)
    p_rec.add_argument(
        "--hide-cursor",
        action="store_true",
        help="Do not draw the cursor in the recording",
    )
    p_rec.add_argument(
        "--audio-device",
        help="DirectShow audio device name (use list-audio-devices)",
    )
    p_rec.add_argument(
        "--crf",
        type=int,
        default=23,
        help="x264 CRF quality (lower=better; 18-28 typical)",
    )
    p_rec.add_argument(
        "--preset",
        choices=[
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
            "slow",
            "slower",
            "veryslow",
        ],
        default="veryfast",
        help="x264 speed/quality tradeoff",
    )
    p_rec.add_argument(
        "--audio-bitrate",
        type=int,
        default=160,
        help="Audio bitrate kbps when capturing audio",
    )
    p_rec.add_argument(
        "--duration",
        type=float,
        help="Stop after N seconds (optional)",
    )
    p_rec.add_argument(
        "--output",
        help="Output .mp4 path (default: recording_TIMESTAMP.mp4)",
    )
    p_rec.add_argument(
        "--show-ffmpeg",
        action="store_true",
        help="Show ffmpeg console output",
    )
    p_rec.add_argument(
        "--ffmpeg",
        help="Path to ffmpeg.exe (or use ffmpeg from PATH)",
    )
    p_rec.set_defaults(func=cmd_record)

    # list-windows
    p_w = sub.add_parser(
        "list-windows",
        help="List visible window titles (Windows)",
    )
    p_w.set_defaults(func=cmd_list_windows)

    # list-audio-devices
    p_a = sub.add_parser(
        "list-audio-devices",
        help="List DirectShow audio capture devices via ffmpeg",
    )
    p_a.add_argument(
        "--ffmpeg",
        help="Path to ffmpeg.exe (optional; defaults to ffmpeg in PATH)",
    )
    p_a.set_defaults(func=cmd_list_audio_devices)

    # check-ffmpeg
    p_c = sub.add_parser(
        "check-ffmpeg",
        help="Check if ffmpeg is available",
    )
    p_c.add_argument(
        "--ffmpeg",
        help="Path to ffmpeg.exe (optional; defaults to ffmpeg in PATH)",
    )
    p_c.set_defaults(func=cmd_check_ffmpeg)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
