"""Tests for mcp-image-tools."""

import json
import tempfile
from pathlib import Path

import pytest
from PIL import Image


def create_test_image(path: Path, color: tuple = (0, 255, 0), size: tuple = (100, 100), mode: str = 'RGB'):
    """Create a solid color test image."""
    img = Image.new(mode, size, color)
    img.save(path)
    return img


def create_chromakey_test_image(path: Path):
    """Create an image with green background and red foreground."""
    img = Image.new('RGB', (100, 100), (0, 255, 0))  # Green background
    # Draw a red square in the center
    pixels = img.load()
    for y in range(30, 70):
        for x in range(30, 70):
            pixels[x, y] = (255, 0, 0)
    img.save(path)
    return img


class TestUtils:
    """Test utility functions."""

    def test_parse_hex_color_with_hash(self):
        from mcp_image_tools.utils import parse_hex_color
        assert parse_hex_color("#00FF00") == (0, 255, 0)

    def test_parse_hex_color_without_hash(self):
        from mcp_image_tools.utils import parse_hex_color
        assert parse_hex_color("FF0000") == (255, 0, 0)

    def test_parse_hex_color_invalid(self):
        from mcp_image_tools.utils import parse_hex_color
        with pytest.raises(ValueError):
            parse_hex_color("invalid")

    def test_color_distance_identical(self):
        from mcp_image_tools.utils import color_distance
        assert color_distance((0, 0, 0), (0, 0, 0)) == 0

    def test_color_distance_different(self):
        from mcp_image_tools.utils import color_distance
        # Black to white should be sqrt(255^2 * 3) ≈ 441.67
        distance = color_distance((0, 0, 0), (255, 255, 255))
        assert 441 < distance < 442


class TestChromakeyToTransparent:
    """Test chromakey transparency conversion."""

    def test_converts_green_to_transparent(self):
        from mcp_image_tools.server import chromakey_to_transparent

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.png"
            output_path = Path(tmpdir) / "output.png"

            create_chromakey_test_image(input_path)

            result = json.loads(chromakey_to_transparent(
                str(input_path),
                str(output_path)
            ))

            assert result["success"] is True
            assert output_path.exists()

            # Verify transparency was applied
            output_img = Image.open(output_path)
            assert output_img.mode == 'RGBA'

            # Check that green pixels became transparent
            pixels = output_img.load()
            # Corner should be transparent (was green)
            assert pixels[0, 0][3] == 0
            # Center should be opaque (was red)
            assert pixels[50, 50][3] == 255

    def test_custom_key_color(self):
        from mcp_image_tools.server import chromakey_to_transparent

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.png"
            output_path = Path(tmpdir) / "output.png"

            # Create blue background image
            create_test_image(input_path, color=(0, 0, 255))

            result = json.loads(chromakey_to_transparent(
                str(input_path),
                str(output_path),
                key_color="#0000FF"
            ))

            assert result["success"] is True
            assert result["key_color"] == "#0000FF"


class TestGetImageMetadata:
    """Test image metadata extraction."""

    def test_gets_png_metadata(self):
        from mcp_image_tools.server import get_image_metadata

        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = Path(tmpdir) / "test.png"
            create_test_image(img_path, size=(200, 150))

            result = json.loads(get_image_metadata(str(img_path)))

            assert result["format"] == "PNG"
            assert result["width"] == 200
            assert result["height"] == 150

    def test_detects_transparency(self):
        from mcp_image_tools.server import get_image_metadata

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create image with transparency
            img_path = Path(tmpdir) / "transparent.png"
            img = Image.new('RGBA', (50, 50), (255, 0, 0, 128))
            img.save(img_path)

            result = json.loads(get_image_metadata(str(img_path)))

            assert result["has_transparency"] is True

    def test_file_not_found(self):
        from mcp_image_tools.server import get_image_metadata

        result = json.loads(get_image_metadata("/nonexistent/image.png"))
        assert "error" in result


class TestResizeImage:
    """Test image resizing."""

    def test_resize_by_width(self):
        from mcp_image_tools.server import resize_image

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.png"
            output_path = Path(tmpdir) / "output.png"

            create_test_image(input_path, size=(200, 100))

            result = json.loads(resize_image(
                str(input_path),
                str(output_path),
                width=100
            ))

            assert result["success"] is True
            assert result["new_dimensions"]["width"] == 100
            assert result["new_dimensions"]["height"] == 50  # Aspect ratio maintained

    def test_resize_by_scale(self):
        from mcp_image_tools.server import resize_image

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.png"
            output_path = Path(tmpdir) / "output.png"

            create_test_image(input_path, size=(100, 100))

            result = json.loads(resize_image(
                str(input_path),
                str(output_path),
                scale=2.0
            ))

            assert result["success"] is True
            assert result["new_dimensions"]["width"] == 200
            assert result["new_dimensions"]["height"] == 200


class TestConvertFormat:
    """Test format conversion."""

    def test_png_to_jpeg(self):
        from mcp_image_tools.server import convert_format

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.png"
            output_path = Path(tmpdir) / "output.jpg"

            create_test_image(input_path)

            result = json.loads(convert_format(str(input_path), str(output_path)))

            assert result["success"] is True
            assert result["new_format"] == "JPEG"
            assert output_path.exists()

    def test_handles_transparency_to_jpeg(self):
        from mcp_image_tools.server import convert_format

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.png"
            output_path = Path(tmpdir) / "output.jpg"

            # Create RGBA image with transparency
            img = Image.new('RGBA', (50, 50), (255, 0, 0, 128))
            img.save(input_path)

            result = json.loads(convert_format(str(input_path), str(output_path)))

            assert result["success"] is True
            # Should convert without error (transparency composited on white)
