"""MCP server for image processing tools."""

import json
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP
from PIL import Image

from .utils import parse_hex_color, color_distance, is_pngquant_available, run_pngquant

mcp = FastMCP("mcp-image-tools")


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
        input_path: Path to input image
        output_path: Path to save transparent PNG
        key_color: Hex color of background to remove (default: #00FF00 green)
        tolerance: Color matching tolerance 0-255 (default: 70)
    """
    input_file = Path(input_path).resolve()
    output_file = Path(output_path).resolve()

    if not input_file.exists():
        return json.dumps({"error": f"Input file not found: {input_file}"})

    try:
        key_rgb = parse_hex_color(key_color)
    except ValueError as e:
        return json.dumps({"error": str(e)})

    img = Image.open(input_file)
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    pixels = img.load()
    kr, kg, kb = key_rgb
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

    output_file.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_file, format='PNG')

    return json.dumps({
        "success": True,
        "output_path": str(output_file),
        "dimensions": {"width": img.width, "height": img.height},
        "key_color": key_color,
        "tolerance": tolerance,
        "pixels_processed": pixels_processed,
        "pixels_made_transparent": pixels_transparent
    }, indent=2)


@mcp.tool()
def compress_png(
    input_path: str,
    output_path: Optional[str] = None,
    quality: int = 80
) -> str:
    """Compress PNG using pngquant (if available).

    Gracefully degrades if pngquant is not installed.

    Args:
        input_path: Path to PNG file
        output_path: Output path (default: overwrite input)
        quality: Quality level 1-100 (default: 80)
    """
    input_file = Path(input_path).resolve()

    if not input_file.exists():
        return json.dumps({"error": f"Input file not found: {input_file}"})

    if output_path:
        output_file = Path(output_path).resolve()
        # Copy to output location first
        import shutil
        output_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(input_file, output_file)
        target_file = output_file
    else:
        target_file = input_file

    if not is_pngquant_available():
        return json.dumps({
            "success": True,
            "compressed": False,
            "reason": "pngquant not installed",
            "output_path": str(target_file),
            "original_size": target_file.stat().st_size
        }, indent=2)

    original_size, compressed_size = run_pngquant(target_file, quality)
    reduction = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0

    return json.dumps({
        "success": True,
        "compressed": original_size != compressed_size,
        "output_path": str(target_file),
        "original_size": original_size,
        "compressed_size": compressed_size,
        "reduction_percent": round(reduction, 1)
    }, indent=2)


@mcp.tool()
def get_image_metadata(image_path: str) -> str:
    """Get metadata about an image file.

    Args:
        image_path: Path to image file
    """
    file_path = Path(image_path).resolve()

    if not file_path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})

    try:
        img = Image.open(file_path)

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
        input_path: Path to input image
        output_path: Path to save resized image
        width: Target width in pixels
        height: Target height in pixels
        scale: Scale factor (e.g., 0.5 for half size, 2.0 for double)
        maintain_aspect: Keep aspect ratio when only width or height given (default: True)
        resample: Resampling filter: nearest, bilinear, bicubic, lanczos (default: lanczos)
    """
    input_file = Path(input_path).resolve()
    output_file = Path(output_path).resolve()

    if not input_file.exists():
        return json.dumps({"error": f"Input file not found: {input_file}"})

    resample_filters = {
        "nearest": Image.Resampling.NEAREST,
        "bilinear": Image.Resampling.BILINEAR,
        "bicubic": Image.Resampling.BICUBIC,
        "lanczos": Image.Resampling.LANCZOS
    }

    if resample.lower() not in resample_filters:
        return json.dumps({"error": f"Invalid resample filter. Use: {list(resample_filters.keys())}"})

    img = Image.open(input_file)
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

    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Determine format from extension
    ext = output_file.suffix.lower()
    format_map = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.webp': 'WEBP', '.gif': 'GIF', '.bmp': 'BMP'}
    save_format = format_map.get(ext, img.format or 'PNG')

    # Handle transparency when saving to JPEG
    if save_format == 'JPEG' and resized.mode == 'RGBA':
        resized = resized.convert('RGB')

    resized.save(output_file, format=save_format)

    return json.dumps({
        "success": True,
        "output_path": str(output_file),
        "original_dimensions": {"width": original_width, "height": original_height},
        "new_dimensions": {"width": new_width, "height": new_height},
        "resample": resample
    }, indent=2)


@mcp.tool()
def convert_format(
    input_path: str,
    output_path: str,
    quality: int = 95
) -> str:
    """Convert image between formats (PNG, JPEG, WebP, GIF, BMP).

    Output format is determined by the output_path extension.

    Args:
        input_path: Path to input image
        output_path: Path to save converted image (extension determines format)
        quality: Quality for lossy formats like JPEG/WebP 1-100 (default: 95)
    """
    input_file = Path(input_path).resolve()
    output_file = Path(output_path).resolve()

    if not input_file.exists():
        return json.dumps({"error": f"Input file not found: {input_file}"})

    ext = output_file.suffix.lower()
    format_map = {
        '.jpg': 'JPEG',
        '.jpeg': 'JPEG',
        '.png': 'PNG',
        '.webp': 'WEBP',
        '.gif': 'GIF',
        '.bmp': 'BMP'
    }

    if ext not in format_map:
        return json.dumps({"error": f"Unsupported format: {ext}. Use: {list(format_map.keys())}"})

    output_format = format_map[ext]

    img = Image.open(input_file)
    original_format = img.format

    # Handle transparency when converting to non-transparent formats
    if output_format in ('JPEG', 'BMP') and img.mode == 'RGBA':
        # Composite onto white background
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    elif output_format == 'JPEG' and img.mode != 'RGB':
        img = img.convert('RGB')

    output_file.parent.mkdir(parents=True, exist_ok=True)

    save_kwargs = {}
    if output_format in ('JPEG', 'WEBP'):
        save_kwargs['quality'] = quality

    img.save(output_file, format=output_format, **save_kwargs)

    return json.dumps({
        "success": True,
        "output_path": str(output_file),
        "original_format": original_format,
        "new_format": output_format,
        "file_size_bytes": output_file.stat().st_size
    }, indent=2)


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
