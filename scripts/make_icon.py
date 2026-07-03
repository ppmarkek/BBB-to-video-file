"""Regenerate assets/logo.ico from assets/logo.png."""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PNG = ROOT / "assets" / "logo.png"
ICO = ROOT / "assets" / "logo.ico"


def main() -> None:
    img = Image.open(PNG).convert("RGBA")
    base = img.resize((256, 256), Image.Resampling.LANCZOS)
    base.save(
        ICO,
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )
    print(f"Wrote {ICO}")


if __name__ == "__main__":
    main()
