#!/usr/bin/env python3
"""Download and merge BigBlueButton recording videos from a playback URL."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from tqdm import tqdm


@dataclass(frozen=True)
class RecordingInfo:
    host: str
    meeting_id: str
    scheme: str

    @property
    def base_url(self) -> str:
        return f"{self.scheme}://{self.host}/presentation/{self.meeting_id}"


def parse_playback_url(url: str) -> RecordingInfo:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")

    meeting_ids = parse_qs(parsed.query).get("meetingId")
    if not meeting_ids or not meeting_ids[0].strip():
        raise ValueError("URL must contain meetingId query parameter")

    return RecordingInfo(
        host=parsed.netloc,
        meeting_id=meeting_ids[0].strip(),
        scheme=parsed.scheme,
    )


def resolve_media_url(base_url: str, relative_paths: tuple[str, ...]) -> str | None:
    for relative_path in relative_paths:
        url = f"{base_url}/{relative_path}"
        try:
            response = requests.head(url, timeout=30, allow_redirects=True)
        except requests.RequestException:
            continue
        if response.status_code == 200:
            return url
    return None


def download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length", 0))
        with open(dest, "wb") as handle, tqdm(
            total=total or None,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            desc=dest.name,
        ) as progress:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
                    progress.update(len(chunk))


def resolve_ffmpeg() -> str | None:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        bundled = Path(get_ffmpeg_exe())
        if bundled.is_file():
            return str(bundled)
    except ImportError:
        pass

    path = shutil.which("ffmpeg")
    if path:
        return path

    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent

    for candidate in (base / "ffmpeg.exe", base / "ffmpeg" / "ffmpeg.exe"):
        if candidate.is_file():
            return str(candidate)

    return None


@dataclass(frozen=True)
class VideoEncoder:
    encoder_id: str
    label: str
    args: tuple[str, ...]


def cpu_encoder() -> VideoEncoder:
    return VideoEncoder(
        "cpu",
        "CPU (libx264)",
        ("-c:v", "libx264", "-preset", "medium", "-crf", "23"),
    )


def detect_video_encoder(ffmpeg: str) -> VideoEncoder:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    encoders = f"{result.stdout}\n{result.stderr}"
    if "h264_nvenc" in encoders:
        return VideoEncoder(
            "nvenc",
            "GPU NVIDIA NVENC",
            ("-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "23"),
        )
    if "h264_amf" in encoders:
        return VideoEncoder(
            "amf",
            "GPU AMD AMF",
            (
                "-c:v",
                "h264_amf",
                "-quality",
                "balanced",
                "-rc",
                "cqp",
                "-qp_i",
                "23",
                "-qp_p",
                "23",
            ),
        )
    if "h264_qsv" in encoders:
        return VideoEncoder(
            "qsv",
            "GPU Intel QSV",
            ("-c:v", "h264_qsv", "-global_quality", "23"),
        )
    return cpu_encoder()


def select_video_encoder(ffmpeg: str, force_cpu: bool) -> VideoEncoder:
    if force_cpu:
        return cpu_encoder()
    return detect_video_encoder(ffmpeg)


AUDIO_ARGS = ("-c:a", "aac", "-b:a", "192k")


def run_ffmpeg(command: list[str]) -> None:
    subprocess.run(command, check=True)


def convert_to_mp4(
    input_path: Path,
    ffmpeg: str,
    encoder: VideoEncoder,
    *,
    allow_cpu_fallback: bool = True,
) -> Path:
    output_path = input_path.with_suffix(".mp4")
    if input_path.suffix.lower() == ".mp4":
        return input_path

    command = [
        ffmpeg,
        "-y",
        "-nostdin",
        "-i",
        str(input_path),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        *encoder.args,
        *AUDIO_ARGS,
        str(output_path),
    ]
    print(f"Converting {input_path.name} to MP4 ({encoder.label})...")
    try:
        run_ffmpeg(command)
    except subprocess.CalledProcessError:
        if allow_cpu_fallback and encoder.encoder_id != "cpu":
            print(f"{encoder.label} failed, falling back to CPU...")
            return convert_to_mp4(
                input_path,
                ffmpeg,
                cpu_encoder(),
                allow_cpu_fallback=False,
            )
        raise

    input_path.unlink()
    return output_path


def ensure_mp4(path: Path, ffmpeg: str, encoder: VideoEncoder) -> Path:
    if path.suffix.lower() == ".mp4":
        return path
    return convert_to_mp4(path, ffmpeg, encoder)


def merge_side_by_side(
    deskshare_path: Path,
    webcams_path: Path,
    output_path: Path,
    ffmpeg: str,
    encoder: VideoEncoder,
    *,
    allow_cpu_fallback: bool = True,
) -> None:
    filter_complex = (
        "[0:v]scale=1280:720:force_original_aspect_ratio=decrease,"
        "pad=1280:720:(ow-iw)/2:(oh-ih)/2[v0];"
        "[1:v]scale=640:720:force_original_aspect_ratio=decrease,"
        "pad=640:720:(ow-iw)/2:(oh-ih)/2[v1];"
        "[v0][v1]hstack=inputs=2[v]"
    )
    command = [
        ffmpeg,
        "-y",
        "-nostdin",
        "-i",
        str(deskshare_path),
        "-i",
        str(webcams_path),
        "-filter_complex",
        filter_complex,
        "-map",
        "[v]",
        "-map",
        "1:a?",
        *encoder.args,
        *AUDIO_ARGS,
        str(output_path),
    ]
    print(f"Merging videos with ffmpeg ({encoder.label})...")
    try:
        run_ffmpeg(command)
    except subprocess.CalledProcessError:
        if allow_cpu_fallback and encoder.encoder_id != "cpu":
            print(f"{encoder.label} failed, falling back to CPU...")
            merge_side_by_side(
                deskshare_path,
                webcams_path,
                output_path,
                ffmpeg,
                cpu_encoder(),
                allow_cpu_fallback=False,
            )
            return
        raise


def download_recording(
    info: RecordingInfo,
    output_dir: Path,
) -> tuple[Path, Path | None]:
    webcams_url = resolve_media_url(
        info.base_url,
        ("video/webcams.webm", "video/webcams.mp4"),
    )
    if not webcams_url:
        raise FileNotFoundError("Webcams video not found (tried webm and mp4)")

    deskshare_url = resolve_media_url(
        info.base_url,
        ("deskshare/deskshare.webm", "deskshare/deskshare.mp4"),
    )

    webcams_ext = Path(urlparse(webcams_url).path).suffix
    webcams_path = output_dir / f"webcams{webcams_ext}"
    print(f"Downloading webcams from {webcams_url}")
    download_file(webcams_url, webcams_path)

    deskshare_path: Path | None = None
    if deskshare_url:
        deskshare_ext = Path(urlparse(deskshare_url).path).suffix
        deskshare_path = output_dir / f"deskshare{deskshare_ext}"
        print(f"Downloading deskshare from {deskshare_url}")
        download_file(deskshare_url, deskshare_path)
    else:
        print("Warning: deskshare video not found; only webcams will be available")

    return webcams_path, deskshare_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download BigBlueButton recordings and merge them into MP4",
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="BBB playback URL with meetingId parameter",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help="Output directory (default: ./downloads/<meetingId>/)",
    )
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="Convert to MP4 only, skip merged side-by-side video",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process one URL and exit (no prompt for more links)",
    )
    parser.add_argument(
        "--cpu",
        action="store_true",
        help="Force CPU encoding (disable GPU acceleration)",
    )
    return parser


def prompt_for_url(*, first: bool = False) -> str:
    if first:
        print("BBB Recording Downloader")
        print()
        print("Вставьте ссылку на playback BigBlueButton и нажмите Enter.")
        print("Пример:")
        print("  https://bbb-lb.tsi.lv/playback/presentation/2.0/playback.html?meetingId=...")
        print()
    else:
        print()
        print("Готово. Вставьте следующую ссылку или нажмите Enter для выхода.")
    return input("URL: ").strip()


def should_stop_urls(url: str) -> bool:
    return not url or url.lower() in {"q", "quit", "exit", "выход"}


def wait_for_exit() -> None:
    if getattr(sys, "frozen", False):
        try:
            input("\nНажмите Enter для выхода...")
        except EOFError:
            pass


def process_recording(
    url: str,
    output_dir: Path | None,
    no_merge: bool,
    force_cpu: bool,
) -> int:
    try:
        info = parse_playback_url(url)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    target_dir = output_dir or Path("downloads") / info.meeting_id
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"Meeting ID: {info.meeting_id}")
    print(f"Output directory: {target_dir.resolve()}")

    try:
        webcams_path, deskshare_path = download_recording(info, target_dir)
    except (FileNotFoundError, requests.RequestException) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    ffmpeg = resolve_ffmpeg()
    if not ffmpeg:
        print(
            "ffmpeg not found. Install it or rebuild the app with bundled ffmpeg.\n"
            "Try: winget install ffmpeg",
            file=sys.stderr,
        )
        return 1

    print(f"Using ffmpeg: {ffmpeg}")
    encoder = select_video_encoder(ffmpeg, force_cpu)
    print(f"Video encoder: {encoder.label}")

    try:
        webcams_path = ensure_mp4(webcams_path, ffmpeg, encoder)
        print(f"Webcams MP4: {webcams_path.resolve()}")
        if deskshare_path:
            deskshare_path = ensure_mp4(deskshare_path, ffmpeg, encoder)
            print(f"Deskshare MP4: {deskshare_path.resolve()}")
    except subprocess.CalledProcessError as exc:
        print(f"ffmpeg failed with exit code {exc.returncode}", file=sys.stderr)
        return 1

    if no_merge:
        print("MP4 conversion complete (--no-merge).")
        return 0

    try:
        if deskshare_path:
            merged_path = target_dir / f"{info.meeting_id}_merged.mp4"
            merge_side_by_side(
                deskshare_path,
                webcams_path,
                merged_path,
                ffmpeg,
                encoder,
            )
            print(f"Merged video saved to {merged_path.resolve()}")
        else:
            print(f"Video saved to {webcams_path.resolve()}")
    except subprocess.CalledProcessError as exc:
        print(f"ffmpeg failed with exit code {exc.returncode}", file=sys.stderr)
        return 1

    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    interactive = not args.once and (
        getattr(sys, "frozen", False) or sys.stdin.isatty()
    )

    exit_code = 0
    url = args.url
    first_prompt = url is None

    while True:
        if url is None:
            url = prompt_for_url(first=first_prompt)
            first_prompt = False
            if should_stop_urls(url):
                break

        exit_code = process_recording(
            url,
            args.output_dir,
            args.no_merge,
            args.cpu,
        )
        print("Done." if exit_code == 0 else "Finished with errors.")

        if not interactive:
            break

        url = None

    if interactive or getattr(sys, "frozen", False):
        wait_for_exit()

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
