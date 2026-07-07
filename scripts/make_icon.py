"""🐍 이모지를 렌더링해 앱 아이콘(static/pydashboard.png + .icns)을 생성한다.

생성물은 repo 에 커밋되므로 보통 재실행할 필요 없다.
아이콘을 바꾸고 싶을 때만 실행:

    .venv/bin/python scripts/make_icon.py

요구사항: macOS + pyobjc (pywebview 의존성으로 이미 설치됨) + iconutil
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
PNG_PATH = BASE_DIR / "static" / "pydashboard.png"
ICNS_PATH = BASE_DIR / "static" / "pydashboard.icns"

EMOJI = "🐍"
MASTER_PX = 1024

# .iconset 규격: (파일명, 픽셀 크기)
ICONSET_SIZES = [
    ("icon_16x16.png", 16),
    ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32),
    ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512),
    ("icon_512x512@2x.png", 1024),
]


def render_emoji_png(emoji: str, px: int, out_path: pathlib.Path) -> None:
    """이모지를 정확히 px×px 투명 배경 PNG 로 렌더링한다."""
    import AppKit  # pyobjc — pywebview 의존성으로 설치됨
    from Foundation import NSMakePoint

    rep = AppKit.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, px, px, 8, 4, True, False, AppKit.NSCalibratedRGBColorSpace, 0, 0
    )
    ctx = AppKit.NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    AppKit.NSGraphicsContext.saveGraphicsState()
    AppKit.NSGraphicsContext.setCurrentContext_(ctx)

    # 시스템 폰트가 이모지를 Apple Color Emoji 로 자동 대체한다.
    attrs = {AppKit.NSFontAttributeName: AppKit.NSFont.systemFontOfSize_(px * 0.78)}
    text = AppKit.NSString.stringWithString_(emoji)
    bounds = text.sizeWithAttributes_(attrs)
    origin = NSMakePoint((px - bounds.width) / 2.0, (px - bounds.height) / 2.0)
    text.drawAtPoint_withAttributes_(origin, attrs)

    AppKit.NSGraphicsContext.restoreGraphicsState()
    png = rep.representationUsingType_properties_(AppKit.NSBitmapImageFileTypePNG, None)
    if not png.writeToFile_atomically_(str(out_path), True):
        raise RuntimeError(f"PNG 저장 실패: {out_path}")


def build_icns(master_png: pathlib.Path, out_icns: pathlib.Path) -> None:
    """마스터 PNG 를 sips 로 리사이즈해 .iconset → iconutil 로 .icns 생성."""
    with tempfile.TemporaryDirectory() as tmp:
        iconset = pathlib.Path(tmp) / "pydashboard.iconset"
        iconset.mkdir()
        for name, size in ICONSET_SIZES:
            target = iconset / name
            if size == MASTER_PX:
                shutil.copy(master_png, target)
            else:
                subprocess.run(
                    ["sips", "-z", str(size), str(size), str(master_png), "--out", str(target)],
                    check=True,
                    capture_output=True,
                )
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(out_icns)],
            check=True,
            capture_output=True,
        )


def main() -> int:
    render_emoji_png(EMOJI, MASTER_PX, PNG_PATH)
    build_icns(PNG_PATH, ICNS_PATH)
    print(f"생성 완료: {PNG_PATH} ({PNG_PATH.stat().st_size} bytes)")
    print(f"생성 완료: {ICNS_PATH} ({ICNS_PATH.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
