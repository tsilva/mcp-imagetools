"""Tests for mcp-image-tools."""

import json
import tempfile
from pathlib import Path

import pytest
from PIL import Image as PILImage


def create_test_image(path: Path, color: tuple = (0, 255, 0), size: tuple = (100, 100), mode: str = 'RGB'):
    """Create a solid color test image."""
    img = PILImage.new(mode, size, color)
    img.save(path)
    return img


def create_chromakey_test_image(path: Path):
    """Create an image with green background and red foreground."""
    img = PILImage.new('RGB', (100, 100), (0, 255, 0))  # Green background
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

            result = chromakey_to_transparent(str(input_path), str(output_path))

            metadata = json.loads(result)
            assert "output_path" in metadata
            assert metadata["pixels_made_transparent"] > 0

            # Verify output file exists and has correct content
            assert output_path.exists()
            img = PILImage.open(output_path)
            assert img.mode == 'RGBA'

            # Check that green pixels became transparent
            pixels = img.load()
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

            result = chromakey_to_transparent(str(input_path), str(output_path), key_color="#0000FF")

            metadata = json.loads(result)
            assert metadata["key_color"] == "#0000FF"
            assert output_path.exists()

    def test_file_not_found(self):
        from mcp_image_tools.server import chromakey_to_transparent

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.png"
            result = chromakey_to_transparent("/nonexistent/image.png", str(output_path))
            metadata = json.loads(result)
            assert "error" in metadata


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
            img = PILImage.new('RGBA', (50, 50), (255, 0, 0, 128))
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

            result = resize_image(str(input_path), str(output_path), width=100)

            metadata = json.loads(result)
            assert metadata["dimensions"]["width"] == 100
            assert metadata["dimensions"]["height"] == 50  # Aspect ratio maintained

            # Verify output file
            assert output_path.exists()
            img = PILImage.open(output_path)
            assert img.size == (100, 50)

    def test_resize_by_scale(self):
        from mcp_image_tools.server import resize_image

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.png"
            output_path = Path(tmpdir) / "output.png"
            create_test_image(input_path, size=(100, 100))

            result = resize_image(str(input_path), str(output_path), scale=2.0)

            metadata = json.loads(result)
            assert metadata["dimensions"]["width"] == 200
            assert metadata["dimensions"]["height"] == 200

            img = PILImage.open(output_path)
            assert img.size == (200, 200)

    def test_resize_to_jpeg(self):
        from mcp_image_tools.server import resize_image

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.png"
            output_path = Path(tmpdir) / "output.jpg"
            create_test_image(input_path, size=(100, 100))

            result = resize_image(str(input_path), str(output_path), width=50)

            metadata = json.loads(result)
            assert metadata["format"] == "JPEG"
            assert output_path.exists()

    def test_file_not_found(self):
        from mcp_image_tools.server import resize_image

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.png"
            result = resize_image("/nonexistent/image.png", str(output_path), width=100)
            metadata = json.loads(result)
            assert "error" in metadata


class TestConvertFormat:
    """Test format conversion."""

    def test_png_to_jpeg(self):
        from mcp_image_tools.server import convert_format

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.png"
            output_path = Path(tmpdir) / "output.jpg"
            create_test_image(input_path)

            result = convert_format(str(input_path), str(output_path))

            metadata = json.loads(result)
            assert metadata["format"] == "JPEG"
            assert metadata["original_format"] == "PNG"

            img = PILImage.open(output_path)
            assert img.format == "JPEG"

    def test_handles_transparency_to_jpeg(self):
        from mcp_image_tools.server import convert_format

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.png"
            output_path = Path(tmpdir) / "output.jpg"
            # Create RGBA image with transparency
            img = PILImage.new('RGBA', (50, 50), (255, 0, 0, 128))
            img.save(input_path)

            result = convert_format(str(input_path), str(output_path))

            # Should convert without error (transparency composited on white)
            metadata = json.loads(result)
            assert metadata["format"] == "JPEG"
            assert output_path.exists()

    def test_invalid_format(self):
        from mcp_image_tools.server import convert_format

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.png"
            output_path = Path(tmpdir) / "output.xyz"
            create_test_image(input_path)

            result = convert_format(str(input_path), str(output_path))

            metadata = json.loads(result)
            assert "error" in metadata


class TestCompressPng:
    """Test PNG compression."""

    def test_compress_saves_to_output(self):
        from mcp_image_tools.server import compress_png

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.png"
            output_path = Path(tmpdir) / "output.png"
            create_test_image(input_path, size=(100, 100))

            result = compress_png(str(input_path), str(output_path))

            metadata = json.loads(result)
            assert "original_size" in metadata
            assert metadata["format"] == "PNG"
            assert output_path.exists()

            # Verify output is valid PNG
            img = PILImage.open(output_path)
            assert img.format == "PNG"

    def test_file_not_found(self):
        from mcp_image_tools.server import compress_png

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.png"
            result = compress_png("/nonexistent/image.png", str(output_path))
            metadata = json.loads(result)
            assert "error" in metadata


class TestAbsolutePathValidation:
    """Test that all tools require absolute paths."""

    def test_chromakey_rejects_relative_input(self):
        from mcp_image_tools.server import chromakey_to_transparent
        result = chromakey_to_transparent("relative/input.png", "/absolute/output.png")
        metadata = json.loads(result)
        assert "error" in metadata
        assert "absolute path" in metadata["error"]

    def test_chromakey_rejects_relative_output(self):
        from mcp_image_tools.server import chromakey_to_transparent
        result = chromakey_to_transparent("/absolute/input.png", "relative/output.png")
        metadata = json.loads(result)
        assert "error" in metadata
        assert "absolute path" in metadata["error"]

    def test_compress_png_rejects_relative_paths(self):
        from mcp_image_tools.server import compress_png
        result = compress_png("relative/input.png", "/absolute/output.png")
        metadata = json.loads(result)
        assert "error" in metadata
        assert "absolute path" in metadata["error"]

    def test_get_image_metadata_rejects_relative_path(self):
        from mcp_image_tools.server import get_image_metadata
        result = get_image_metadata("relative/image.png")
        metadata = json.loads(result)
        assert "error" in metadata
        assert "absolute path" in metadata["error"]

    def test_resize_image_rejects_relative_paths(self):
        from mcp_image_tools.server import resize_image
        result = resize_image("relative/input.png", "/absolute/output.png", width=100)
        metadata = json.loads(result)
        assert "error" in metadata
        assert "absolute path" in metadata["error"]

    def test_convert_format_rejects_relative_paths(self):
        from mcp_image_tools.server import convert_format
        result = convert_format("relative/input.png", "/absolute/output.jpg")
        metadata = json.loads(result)
        assert "error" in metadata
        assert "absolute path" in metadata["error"]


class TestSameInputOutputPath:
    """Test that tools work when input and output paths are the same."""

    def test_resize_image_same_path(self):
        from mcp_image_tools.server import resize_image

        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = Path(tmpdir) / "image.png"
            create_test_image(img_path, size=(200, 100))

            # Resize in place
            result = resize_image(str(img_path), str(img_path), scale=0.5)

            metadata = json.loads(result)
            assert "error" not in metadata
            assert metadata["dimensions"]["width"] == 100
            assert metadata["dimensions"]["height"] == 50
            # Compare resolved paths to handle symlinks like /var -> /private/var on macOS
            assert Path(metadata["output_path"]).resolve() == img_path.resolve()

            # Verify the file was actually modified
            img = PILImage.open(img_path)
            assert img.size == (100, 50)

    def test_convert_format_same_path_png(self):
        from mcp_image_tools.server import convert_format

        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = Path(tmpdir) / "image.png"
            create_test_image(img_path, size=(100, 100))

            # Re-save as PNG (no-op format but should work)
            result = convert_format(str(img_path), str(img_path))

            metadata = json.loads(result)
            assert "error" not in metadata
            assert metadata["format"] == "PNG"
            # Compare resolved paths to handle symlinks like /var -> /private/var on macOS
            assert Path(metadata["output_path"]).resolve() == img_path.resolve()
            assert img_path.exists()

    def test_chromakey_same_path(self):
        from mcp_image_tools.server import chromakey_to_transparent

        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = Path(tmpdir) / "image.png"
            create_chromakey_test_image(img_path)

            # Chromakey in place
            result = chromakey_to_transparent(str(img_path), str(img_path))

            metadata = json.loads(result)
            assert "error" not in metadata
            assert metadata["pixels_made_transparent"] > 0
            # Compare resolved paths to handle symlinks like /var -> /private/var on macOS
            assert Path(metadata["output_path"]).resolve() == img_path.resolve()

            # Verify the file was actually modified with transparency
            img = PILImage.open(img_path)
            assert img.mode == 'RGBA'
            pixels = img.load()
            # Corner should be transparent (was green)
            assert pixels[0, 0][3] == 0

    def test_compress_png_same_path(self):
        from mcp_image_tools.server import compress_png

        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = Path(tmpdir) / "image.png"
            create_test_image(img_path, size=(100, 100))

            # Compress in place
            result = compress_png(str(img_path), str(img_path))

            metadata = json.loads(result)
            assert "error" not in metadata
            assert metadata["format"] == "PNG"
            # Compare resolved paths to handle symlinks like /var -> /private/var on macOS
            assert Path(metadata["output_path"]).resolve() == img_path.resolve()
            assert img_path.exists()

            # Verify it's still a valid PNG
            img = PILImage.open(img_path)
            assert img.format == "PNG"

    def test_same_path_preserves_content_on_success(self):
        """Verify that same-path operations preserve expected content."""
        from mcp_image_tools.server import resize_image

        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = Path(tmpdir) / "image.png"
            # Create a distinctive image (red)
            create_test_image(img_path, color=(255, 0, 0), size=(100, 100))

            result = resize_image(str(img_path), str(img_path), scale=0.5)

            metadata = json.loads(result)
            assert "error" not in metadata

            # Verify the resized image still has red content
            img = PILImage.open(img_path)
            assert img.size == (50, 50)
            pixels = img.load()
            # Center pixel should still be red
            r, g, b = pixels[25, 25][:3]
            assert r > 200 and g < 50 and b < 50


class TestWorkflow:
    """Test end-to-end workflows."""

    def test_resize_then_convert(self):
        """Test: resize_image → convert_format (chaining)."""
        from mcp_image_tools.server import resize_image, convert_format

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.png"
            resized_path = Path(tmpdir) / "resized.png"
            final_path = Path(tmpdir) / "final.jpg"
            create_test_image(input_path, size=(200, 200))

            # Resize
            resize_image(str(input_path), str(resized_path), width=100)
            assert resized_path.exists()

            # Convert
            result = convert_format(str(resized_path), str(final_path))
            metadata = json.loads(result)
            assert metadata["format"] == "JPEG"

            # Verify final result
            img = PILImage.open(final_path)
            assert img.format == "JPEG"
            assert img.size == (100, 100)
