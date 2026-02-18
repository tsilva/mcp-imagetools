"""MCP server for image processing tools."""

import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Generator

from mcp.server.fastmcp import FastMCP
from PIL import Image as PILImage

from .utils import parse_hex_color, color_distance, is_pngquant_available, run_pngquant

mcp = FastMCP("mcp-image-tools")


def validate_absolute_path(path: str, param_name: str) -> tuple[Path, str | None]:
    """Validate that a path is absolute. Returns (resolved Path, error_json) where error_json is None if valid."""
    p = Path(path)
    if not p.is_absolute():
        return p, json.dumps({"error": f"{param_name} must be an absolute path, got: {path}"})
    return p.resolve(), None


def save_image_to_path(img: PILImage.Image, output_path: Path, format: str, **save_kwargs) -> dict:
    """Save PIL image to disk and return metadata."""
    img.save(output_path, format=format, **save_kwargs)
    size_bytes = output_path.stat().st_size
    return {
        "output_path": str(output_path),
        "format": format,
        "size_bytes": size_bytes,
        "dimensions": {"width": img.width, "height": img.height}
    }


@contextmanager
def safe_output_path(input_path: Path, output_path: Path) -> Generator[Path, None, None]:
    """Context manager for safe file operations where input and output may be the same.

    Yields the path to write to. If input and output are the same, yields a temp file
    and handles atomic replacement on success, cleanup on failure.
    """
    same_path = input_path.resolve() == output_path.resolve()

    if not same_path:
        yield output_path
        return

    # Same path - use temp file in same directory for atomic move
    fd, temp_path_str = tempfile.mkstemp(suffix=output_path.suffix, dir=output_path.parent)
    os.close(fd)
    temp_path = Path(temp_path_str)

    try:
        yield temp_path
        # Success - atomic replace
        shutil.move(str(temp_path), str(output_path))
    finally:
        # Cleanup temp file if still exists (failure case)
        if temp_path.exists():
            temp_path.unlink()


@mcp.tool()
def chromakey_to_transparent(
    input_path: str,
    output_path: str,
    key_color: str = "#00FF00",
    tolerance: int = 70
) -> str:
    """Convert chromakey (green screen) background to transparency.

    Uses professional-quality edge detection with graduated alpha blending
    to avoid "halo" artifacts around edges.

    Args:
        input_path: Absolute path to input image
        output_path: Absolute path to save transparent PNG
        key_color: Hex color of background to remove (default: #00FF00 green)
        tolerance: Color matching tolerance 0-255 (default: 70)
    """
    input_file, err = validate_absolute_path(input_path, "input_path")
    if err:
        return err
    output_file, err = validate_absolute_path(output_path, "output_path")
    if err:
        return err

    if not input_file.exists():
        return json.dumps({"error": f"Input file not found: {input_file}"})

    try:
        key_rgb = parse_hex_color(key_color)
    except ValueError as e:
        return json.dumps({"error": str(e)})

    img = PILImage.open(input_file)
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    pixels = img.load()
    pixels_processed = 0
    pixels_transparent = 0

    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = pixels[x, y]
            distance = color_distance((r, g, b), key_rgb)

            if distance < tolerance:
                # Full transparency for close matches
                pixels[x, y] = (r, g, b, 0)
                pixels_transparent += 1
            elif distance < tolerance * 3:
                # Graduated alpha for smooth edges
                alpha = int(255 * (distance - tolerance) / (tolerance * 2))
                pixels[x, y] = (r, g, b, min(255, alpha))
            pixels_processed += 1

    with safe_output_path(input_file, output_file) as actual_output:
        result = save_image_to_path(img, actual_output, "PNG")
    result["output_path"] = str(output_file)
    result.update({
        "key_color": key_color,
        "tolerance": tolerance,
        "pixels_processed": pixels_processed,
        "pixels_made_transparent": pixels_transparent
    })
    return json.dumps(result, indent=2)


@mcp.tool()
def compress_png(
    input_path: str,
    output_path: str,
    quality: int = 80
) -> str:
    """Compress PNG using pngquant (if available).

    Gracefully degrades if pngquant is not installed.

    Args:
        input_path: Absolute path to PNG file
        output_path: Absolute path to save compressed PNG
        quality: Quality level 1-100 (default: 80)
    """
    input_file, err = validate_absolute_path(input_path, "input_path")
    if err:
        return err
    output_file, err = validate_absolute_path(output_path, "output_path")
    if err:
        return err

    if not input_file.exists():
        return json.dumps({"error": f"Input file not found: {input_file}"})

    with safe_output_path(input_file, output_file) as actual_output:
        # Copy to output path first
        shutil.copy(input_file, actual_output)
        original_size = actual_output.stat().st_size

        if is_pngquant_available():
            original_size, compressed_size = run_pngquant(actual_output, quality)
            compressed = original_size != compressed_size
        else:
            compressed_size = original_size
            compressed = False

    reduction = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0

    metadata = {
        "output_path": str(output_file),
        "format": "PNG",
        "compressed": compressed,
        "original_size": original_size,
        "size_bytes": compressed_size,
        "reduction_percent": round(reduction, 1)
    }

    if not is_pngquant_available():
        metadata["note"] = "pngquant not installed - returning original"

    return json.dumps(metadata, indent=2)


@mcp.tool()
def get_image_metadata(image_path: str) -> str:
    """Get metadata about an image file.

    Args:
        image_path: Absolute path to image file
    """
    file_path, err = validate_absolute_path(image_path, "image_path")
    if err:
        return err

    if not file_path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})

    try:
        img = PILImage.open(file_path)

        has_transparency = False
        if img.mode == 'RGBA':
            # Check if any pixel has alpha < 255
            extrema = img.getextrema()
            if len(extrema) >= 4:
                has_transparency = extrema[3][0] < 255
        elif img.mode == 'P':
            has_transparency = 'transparency' in img.info

        return json.dumps({
            "path": str(file_path),
            "format": img.format,
            "mode": img.mode,
            "width": img.width,
            "height": img.height,
            "has_transparency": has_transparency,
            "file_size_bytes": file_path.stat().st_size
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def resize_image(
    input_path: str,
    output_path: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    scale: Optional[float] = None,
    maintain_aspect: bool = True,
    resample: str = "lanczos"
) -> str:
    """Resize an image by dimensions or scale factor.

    Args:
        input_path: Absolute path to input image
        output_path: Absolute path to save resized image
        width: Target width in pixels
        height: Target height in pixels
        scale: Scale factor (e.g., 0.5 for half size, 2.0 for double)
        maintain_aspect: Keep aspect ratio when only width or height given (default: True)
        resample: Resampling filter: nearest, bilinear, bicubic, lanczos (default: lanczos)
    """
    input_file, err = validate_absolute_path(input_path, "input_path")
    if err:
        return err
    output_file, err = validate_absolute_path(output_path, "output_path")
    if err:
        return err

    if not input_file.exists():
        return json.dumps({"error": f"Input file not found: {input_file}"})

    resample_filters = {
        "nearest": PILImage.Resampling.NEAREST,
        "bilinear": PILImage.Resampling.BILINEAR,
        "bicubic": PILImage.Resampling.BICUBIC,
        "lanczos": PILImage.Resampling.LANCZOS
    }

    if resample.lower() not in resample_filters:
        return json.dumps({"error": f"Invalid resample filter. Use: {list(resample_filters.keys())}"})

    # Determine output format from extension
    ext_to_format = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP", ".gif": "GIF", ".bmp": "BMP"}
    output_ext = output_file.suffix.lower()
    output_format = ext_to_format.get(output_ext, "PNG")

    img = PILImage.open(input_file)
    original_width, original_height = img.size

    # Determine new dimensions
    if scale is not None:
        new_width = int(original_width * scale)
        new_height = int(original_height * scale)
    elif width is not None and height is not None:
        new_width, new_height = width, height
    elif width is not None:
        new_width = width
        if maintain_aspect:
            new_height = int(original_height * (width / original_width))
        else:
            new_height = original_height
    elif height is not None:
        new_height = height
        if maintain_aspect:
            new_width = int(original_width * (height / original_height))
        else:
            new_width = original_width
    else:
        return json.dumps({"error": "Specify width, height, or scale"})

    resized = img.resize((new_width, new_height), resample_filters[resample.lower()])

    # Handle transparency when saving to JPEG
    if output_format == "JPEG" and resized.mode == "RGBA":
        background = PILImage.new("RGB", resized.size, (255, 255, 255))
        background.paste(resized, mask=resized.split()[3])
        resized = background
    elif output_format == "JPEG" and resized.mode != "RGB":
        resized = resized.convert("RGB")

    save_kwargs = {"quality": 95} if output_format in ("JPEG", "WEBP") else {}

    with safe_output_path(input_file, output_file) as actual_output:
        result = save_image_to_path(resized, actual_output, output_format, **save_kwargs)
    result["output_path"] = str(output_file)
    result.update({
        "original_dimensions": {"width": original_width, "height": original_height},
        "resample": resample
    })
    return json.dumps(result, indent=2)


@mcp.tool()
def convert_format(
    input_path: str,
    output_path: str,
    quality: int = 95
) -> str:
    """Convert image between formats (PNG, JPEG, WebP, GIF, BMP).

    Output format is determined by the output_path extension.

    Args:
        input_path: Absolute path to input image
        output_path: Absolute path to save converted image (extension determines format)
        quality: Quality for lossy formats like JPEG/WebP 1-100 (default: 95)
    """
    input_file, err = validate_absolute_path(input_path, "input_path")
    if err:
        return err
    output_file, err = validate_absolute_path(output_path, "output_path")
    if err:
        return err

    if not input_file.exists():
        return json.dumps({"error": f"Input file not found: {input_file}"})

    # Determine output format from extension
    ext_to_format = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP", ".gif": "GIF", ".bmp": "BMP"}
    output_ext = output_file.suffix.lower()
    output_format = ext_to_format.get(output_ext)

    if output_format is None:
        return json.dumps({"error": f"Unsupported output extension: {output_ext}. Use: .png, .jpg, .jpeg, .webp, .gif, .bmp"})

    img = PILImage.open(input_file)
    original_format = img.format

    # Handle transparency when converting to non-transparent formats
    if output_format in ("JPEG", "BMP") and img.mode == "RGBA":
        # Composite onto white background
        background = PILImage.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    elif output_format == "JPEG" and img.mode != "RGB":
        img = img.convert("RGB")

    save_kwargs = {}
    if output_format in ("JPEG", "WEBP"):
        save_kwargs["quality"] = quality

    with safe_output_path(input_file, output_file) as actual_output:
        result = save_image_to_path(img, actual_output, output_format, **save_kwargs)
    result["output_path"] = str(output_file)
    result["original_format"] = original_format
    return json.dumps(result, indent=2)


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
