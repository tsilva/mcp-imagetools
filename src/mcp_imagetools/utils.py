"""Shared image processing utilities."""

import math
import shutil
import subprocess
from pathlib import Path


def parse_hex_color(hex_color: str) -> tuple[int, int, int]:
    """Parse hex color string to RGB tuple.

    Args:
        hex_color: Hex color string (e.g., "#00FF00" or "00FF00")

    Returns:
        RGB tuple (r, g, b) with values 0-255
    """
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        raise ValueError(f"Invalid hex color: {hex_color}")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def color_distance(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    """Calculate Euclidean distance between two RGB colors.

    Args:
        c1: First RGB tuple
        c2: Second RGB tuple

    Returns:
        Distance value (0 = identical, ~441 = max for black/white)
    """
    return math.sqrt(
        (c1[0] - c2[0])**2 +
        (c1[1] - c2[1])**2 +
        (c1[2] - c2[2])**2
    )


def is_pngquant_available() -> bool:
    """Check if pngquant CLI tool is installed."""
    return shutil.which("pngquant") is not None


def run_pngquant(image_path: Path, quality: int = 80) -> tuple[int, int]:
    """Compress PNG using pngquant.

    Args:
        image_path: Path to PNG file (modified in-place)
        quality: Quality level 1-100 (default: 80)

    Returns:
        Tuple of (original_size, compressed_size) in bytes
    """
    original_size = image_path.stat().st_size

    if not is_pngquant_available():
        return original_size, original_size

    quality_min = max(0, quality - 20)
    result = subprocess.run([
        "pngquant",
        "--quality", f"{quality_min}-{quality}",
        "--speed", "1",
        "--strip",
        "--force",
        "--output", str(image_path),
        str(image_path)
    ], capture_output=True)

    # Return codes: 0=success, 99=quality too low (still success)
    if result.returncode not in (0, 99):
        return original_size, original_size

    compressed_size = image_path.stat().st_size
    return original_size, compressed_size
