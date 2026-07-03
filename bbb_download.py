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


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def merge_side_by_side(
    deskshare_path: Path,
    webcams_path: Path,
    output_path: Path,
) -> None:
    filter_complex = (
        "[0:v]scale=1280:720:force_original_aspect_ratio=decrease,"
        "pad=1280:720:(ow-iw)/2:(oh-ih)/2[v0];"
        "[1:v]scale=640:720:force_original_aspect_ratio=decrease,"
        "pad=640:720:(ow-iw)/2:(oh-ih)/2[v1];"
        "[v0][v1]hstack=inputs=2[v]"
    )
    command = [
        "ffmpeg",
        "-y",
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
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(output_path),
    ]
    print("Merging videos with ffmpeg...")
    subprocess.run(command, check=True)


def convert_webcams_only(webcams_path: Path, output_path: Path) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(webcams_path),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(output_path),
    ]
    print("Converting webcams video to MP4...")
    subprocess.run(command, check=True)


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
    parser.add_argument("url", help="BBB playback URL with meetingId parameter")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help="Output directory (default: ./downloads/<meetingId>/)",
    )
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="Download raw video files only, skip ffmpeg merge",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        info = parse_playback_url(args.url)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    output_dir = args.output_dir or Path("downloads") / info.meeting_id
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Meeting ID: {info.meeting_id}")
    print(f"Output directory: {output_dir.resolve()}")

    try:
        webcams_path, deskshare_path = download_recording(info, output_dir)
    except (FileNotFoundError, requests.RequestException) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.no_merge:
        print("Download complete (--no-merge).")
        return 0

    if not ffmpeg_available():
        print(
            "ffmpeg not found in PATH. Raw files were downloaded.\n"
            "Install ffmpeg and rerun without --no-merge, or merge manually.",
            file=sys.stderr,
        )
        return 1

    try:
        if deskshare_path:
            merged_path = output_dir / f"{info.meeting_id}_merged.mp4"
            merge_side_by_side(deskshare_path, webcams_path, merged_path)
            print(f"Merged video saved to {merged_path.resolve()}")
        else:
            single_path = output_dir / f"{info.meeting_id}.mp4"
            convert_webcams_only(webcams_path, single_path)
            print(f"Video saved to {single_path.resolve()}")
    except subprocess.CalledProcessError as exc:
        print(f"ffmpeg failed with exit code {exc.returncode}", file=sys.stderr)
        return 1

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
