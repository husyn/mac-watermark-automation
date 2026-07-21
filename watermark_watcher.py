#!/usr/bin/env python3
"""
Local macOS image-watermark automation.

Watches an Incoming folder, applies either a PNG-logo or text watermark,
writes the result to Watermarked, then archives the source in Originals.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import shutil
import signal
import sys
import time
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_AVAILABLE = True
except Exception:
    HEIF_AVAILABLE = False


SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff",
    ".bmp", ".heic", ".heif", ".avif"
}
TEMP_SUFFIXES = {".part", ".download", ".crdownload", ".tmp"}

stop_requested = False


def request_stop(_signum: int, _frame: object) -> None:
    global stop_requested
    stop_requested = True


def load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    defaults: dict[str, Any] = {
        "incoming_folder": "Incoming",
        "output_folder": "Watermarked",
        "originals_folder": "Originals",
        "failed_folder": "Failed",
        "mode": "auto",
        "logo_file": "watermark.png",
        "text": "YOUR WATERMARK",
        "position": "bottom-right",
        "opacity": 0.55,
        "margin_percent": 0.025,
        "logo_width_percent": 0.20,
        "text_size_percent": 0.045,
        "text_color": [255, 255, 255],
        "text_stroke_color": [0, 0, 0],
        "text_stroke_width_percent": 0.003,
        "output_suffix": "_watermarked",
        "jpeg_quality": 92,
        "webp_quality": 92,
        "poll_seconds": 2,
        "overwrite_output": True,
    }
    merged = {**defaults, **config}

    mode = str(merged["mode"]).lower()
    if mode not in {"auto", "logo", "text"}:
        raise ValueError("mode must be auto, logo, or text")

    position = str(merged["position"]).lower()
    allowed_positions = {
        "top-left", "top-center", "top-right",
        "center-left", "center", "center-right",
        "bottom-left", "bottom-center", "bottom-right",
    }
    if position not in allowed_positions:
        raise ValueError(f"Unsupported position: {position}")

    merged["opacity"] = max(0.0, min(1.0, float(merged["opacity"])))
    merged["margin_percent"] = max(0.0, float(merged["margin_percent"]))
    merged["logo_width_percent"] = max(0.01, min(1.0, float(merged["logo_width_percent"])))
    merged["text_size_percent"] = max(0.005, min(0.5, float(merged["text_size_percent"])))
    merged["text_stroke_width_percent"] = max(
        0.0, min(0.1, float(merged["text_stroke_width_percent"]))
    )
    merged["jpeg_quality"] = max(1, min(100, int(merged["jpeg_quality"])))
    merged["webp_quality"] = max(1, min(100, int(merged["webp_quality"])))
    merged["poll_seconds"] = max(0.5, float(merged["poll_seconds"]))
    return merged


def resolve_path(base: Path, configured_path: str) -> Path:
    path = Path(os.path.expanduser(configured_path))
    return path if path.is_absolute() else base / path


def configure_logging(logs_dir: Path) -> logging.Logger:
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("watermark_automation")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        logs_dir / "watermark.log",
        maxBytes=5_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger


def find_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def calculate_position(
    canvas_size: tuple[int, int],
    item_size: tuple[int, int],
    position: str,
    margin: int,
) -> tuple[int, int]:
    canvas_w, canvas_h = canvas_size
    item_w, item_h = item_size

    x_map = {
        "left": margin,
        "center": (canvas_w - item_w) // 2,
        "right": canvas_w - item_w - margin,
    }
    y_map = {
        "top": margin,
        "center": (canvas_h - item_h) // 2,
        "bottom": canvas_h - item_h - margin,
    }

    vertical, horizontal = position.split("-", 1) if "-" in position else ("center", "center")
    if position == "center":
        vertical, horizontal = "center", "center"

    x = max(0, x_map[horizontal])
    y = max(0, y_map[vertical])
    return x, y


def apply_logo(
    base_rgba: Image.Image,
    logo_path: Path,
    config: dict[str, Any],
) -> Image.Image:
    if not logo_path.exists():
        raise FileNotFoundError(f"Logo file not found: {logo_path}")

    with Image.open(logo_path) as opened_logo:
        logo = opened_logo.convert("RGBA")

    target_width = max(1, round(base_rgba.width * config["logo_width_percent"]))
    scale = target_width / logo.width
    target_height = max(1, round(logo.height * scale))

    max_height = max(1, round(base_rgba.height * 0.45))
    if target_height > max_height:
        scale = max_height / logo.height
        target_width = max(1, round(logo.width * scale))
        target_height = max_height

    logo = logo.resize((target_width, target_height), Image.Resampling.LANCZOS)

    alpha = logo.getchannel("A").point(
        lambda value: round(value * config["opacity"])
    )
    logo.putalpha(alpha)

    margin = round(min(base_rgba.size) * config["margin_percent"])
    xy = calculate_position(base_rgba.size, logo.size, config["position"], margin)

    overlay = Image.new("RGBA", base_rgba.size, (0, 0, 0, 0))
    overlay.alpha_composite(logo, dest=xy)
    return Image.alpha_composite(base_rgba, overlay)


def apply_text(base_rgba: Image.Image, config: dict[str, Any]) -> Image.Image:
    text = str(config["text"]).strip()
    if not text:
        raise ValueError("Text watermark is empty")

    font_size = max(10, round(min(base_rgba.size) * config["text_size_percent"]))
    font = find_font(font_size)
    stroke_width = max(
        1, round(min(base_rgba.size) * config["text_stroke_width_percent"])
    )

    fill_rgb = tuple(int(v) for v in config["text_color"][:3])
    stroke_rgb = tuple(int(v) for v in config["text_stroke_color"][:3])
    alpha = round(255 * config["opacity"])

    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = measure.textbbox(
        (0, 0),
        text,
        font=font,
        stroke_width=stroke_width,
    )
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    margin = round(min(base_rgba.size) * config["margin_percent"])
    x, y = calculate_position(
        base_rgba.size,
        (text_w, text_h),
        config["position"],
        margin,
    )
    # Compensate for font bounding-box offsets.
    draw_xy = (x - bbox[0], y - bbox[1])

    overlay = Image.new("RGBA", base_rgba.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.text(
        draw_xy,
        text,
        font=font,
        fill=(*fill_rgb, alpha),
        stroke_width=stroke_width,
        stroke_fill=(*stroke_rgb, alpha),
    )
    return Image.alpha_composite(base_rgba, overlay)


def output_details(source: Path, suffix: str) -> tuple[str, str]:
    ext = source.suffix.lower()
    stem = source.stem + suffix

    if ext in {".jpg", ".jpeg", ".heic", ".heif", ".avif"}:
        return stem + ".jpg", "JPEG"
    if ext == ".png":
        return stem + ".png", "PNG"
    if ext == ".webp":
        return stem + ".webp", "WEBP"
    if ext in {".tif", ".tiff"}:
        return stem + ".tif", "TIFF"
    if ext == ".bmp":
        return stem + ".png", "PNG"
    return stem + ".jpg", "JPEG"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def save_image(
    image_rgba: Image.Image,
    destination: Path,
    image_format: str,
    config: dict[str, Any],
    exif_bytes: bytes | None,
    icc_profile: bytes | None,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_name(f".{destination.name}.tmp")

    save_kwargs: dict[str, Any] = {}
    image_to_save = image_rgba

    if image_format == "JPEG":
        image_to_save = image_rgba.convert("RGB")
        save_kwargs.update(
            quality=config["jpeg_quality"],
            optimize=True,
            progressive=True,
        )
    elif image_format == "PNG":
        save_kwargs.update(optimize=True)
    elif image_format == "WEBP":
        save_kwargs.update(
            quality=config["webp_quality"],
            method=6,
        )
    elif image_format == "TIFF":
        save_kwargs.update(compression="tiff_lzw")

    if icc_profile and image_format in {"JPEG", "PNG", "WEBP", "TIFF"}:
        save_kwargs["icc_profile"] = icc_profile
    if exif_bytes and image_format in {"JPEG", "WEBP", "TIFF"}:
        save_kwargs["exif"] = exif_bytes

    try:
        image_to_save.save(temp_path, format=image_format, **save_kwargs)
        os.replace(temp_path, destination)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def process_image(
    source: Path,
    output_dir: Path,
    originals_dir: Path,
    failed_dir: Path,
    base_dir: Path,
    config: dict[str, Any],
    logger: logging.Logger,
) -> None:
    try:
        with Image.open(source) as opened:
            icc_profile = opened.info.get("icc_profile")
            exif = opened.getexif()
            transposed = ImageOps.exif_transpose(opened)
            base_rgba = transposed.convert("RGBA")

        exif_bytes: bytes | None = None
        if exif:
            # The pixels are now physically oriented, so reset Orientation.
            exif[274] = 1
            exif_bytes = exif.tobytes()

        logo_path = resolve_path(base_dir, str(config["logo_file"]))
        mode = str(config["mode"]).lower()
        use_logo = mode == "logo" or (mode == "auto" and logo_path.exists())

        if use_logo:
            result = apply_logo(base_rgba, logo_path, config)
            method = f"logo ({logo_path.name})"
        else:
            result = apply_text(base_rgba, config)
            method = f'text ("{config["text"]}")'

        output_name, image_format = output_details(
            source, str(config["output_suffix"])
        )
        destination = output_dir / output_name
        if not config["overwrite_output"]:
            destination = unique_path(destination)

        save_image(
            result,
            destination,
            image_format,
            config,
            exif_bytes,
            icc_profile,
        )

        archived_source = unique_path(originals_dir / source.name)
        shutil.move(str(source), str(archived_source))
        logger.info(
            "Processed %s using %s -> %s",
            source.name,
            method,
            destination.name,
        )
    except Exception as exc:
        failed_target = unique_path(failed_dir / source.name)
        try:
            shutil.move(str(source), str(failed_target))
        except Exception:
            failed_target = source

        error_file = failed_dir / f"{failed_target.name}.error.txt"
        error_file.write_text(
            f"File: {failed_target}\nError: {type(exc).__name__}: {exc}\n",
            encoding="utf-8",
        )
        logger.exception("Failed to process %s", source.name)


def eligible_files(incoming_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in incoming_dir.iterdir():
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        if path.suffix.lower() in TEMP_SUFFIXES:
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.name.lower())


def run(config_path: Path, once: bool) -> int:
    base_dir = config_path.parent.resolve()
    config = load_config(config_path)

    incoming_dir = resolve_path(base_dir, str(config["incoming_folder"]))
    output_dir = resolve_path(base_dir, str(config["output_folder"]))
    originals_dir = resolve_path(base_dir, str(config["originals_folder"]))
    failed_dir = resolve_path(base_dir, str(config["failed_folder"]))
    logs_dir = base_dir / "Logs"

    for directory in (
        incoming_dir, output_dir, originals_dir, failed_dir, logs_dir
    ):
        directory.mkdir(parents=True, exist_ok=True)

    logger = configure_logging(logs_dir)

    if not HEIF_AVAILABLE:
        logger.warning(
            "HEIC/HEIF support is unavailable. Other formats will still work."
        )

    lock_path = base_dir / ".watcher.lock"
    lock_handle = lock_path.open("w", encoding="utf-8")
    try:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        logger.error("Another watermark watcher is already running.")
        return 2

    lock_handle.write(str(os.getpid()))
    lock_handle.flush()

    logger.info(
        "Watcher started. Incoming=%s | Output=%s | Mode=%s",
        incoming_dir,
        output_dir,
        config["mode"],
    )

    # A file must have the same size and modified time in two scans before it
    # is processed. This avoids reading a file while Finder is still copying it.
    observed: dict[Path, tuple[int, int]] = {}

    try:
        while not stop_requested:
            current_paths = set(eligible_files(incoming_dir))

            for stale_path in list(observed):
                if stale_path not in current_paths:
                    observed.pop(stale_path, None)

            for source in current_paths:
                try:
                    stat_result = source.stat()
                except FileNotFoundError:
                    continue

                signature = (stat_result.st_size, stat_result.st_mtime_ns)
                previous = observed.get(source)
                if previous == signature:
                    process_image(
                        source,
                        output_dir,
                        originals_dir,
                        failed_dir,
                        base_dir,
                        config,
                        logger,
                    )
                    observed.pop(source, None)
                else:
                    observed[source] = signature

            if once:
                # Give files one extra stability scan in one-shot mode.
                if current_paths and observed:
                    time.sleep(config["poll_seconds"])
                    for source in list(eligible_files(incoming_dir)):
                        try:
                            stat_result = source.stat()
                        except FileNotFoundError:
                            continue
                        signature = (stat_result.st_size, stat_result.st_mtime_ns)
                        if observed.get(source) == signature:
                            process_image(
                                source,
                                output_dir,
                                originals_dir,
                                failed_dir,
                                base_dir,
                                config,
                                logger,
                            )
                    observed.clear()
                break

            time.sleep(config["poll_seconds"])
    finally:
        logger.info("Watcher stopped.")
        fcntl.flock(lock_handle, fcntl.LOCK_UN)
        lock_handle.close()

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automatically watermark images.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("config.json"),
        help="Path to config.json",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process existing files once, then exit.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    arguments = parse_args()
    try:
        raise SystemExit(run(arguments.config.resolve(), arguments.once))
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        raise SystemExit(1)
