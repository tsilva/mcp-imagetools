<div align="center">
  <img src="logo.png" alt="mcp-image-tools" width="512"/>

  # mcp-image-tools

  [![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
  [![MCP](https://img.shields.io/badge/MCP-1.2+-green.svg)](https://modelcontextprotocol.io)
  [![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

  **🖼️ Image processing tools for Claude Code — chromakey, resize, compress, and convert images via MCP 🔧**

  [Tools](#tools) · [Quick Start](#quick-start) · [Usage](#usage)
</div>

## Features

- ✨ **Chromakey to Transparent** — Professional green screen removal with graduated alpha blending
- 📐 **Resize** — Scale by dimensions or factor with aspect ratio control and Lanczos resampling
- 🗜️ **Compress** — PNG optimization via pngquant (graceful degradation if not installed)
- 🔄 **Convert** — Transform between PNG, JPEG, WebP, GIF, and BMP formats
- 📊 **Metadata** — Extract format, dimensions, and transparency info

## Quick Start

```bash
# Add to Claude Code
claude mcp add image-tools -- uv run --directory /path/to/mcp-image-tools mcp-image-tools
```

## Tools

| Tool | Description |
|------|-------------|
| `chromakey_to_transparent` | Convert green screen backgrounds to transparency with smooth edge blending |
| `resize_image` | Resize by width, height, or scale factor with Lanczos resampling |
| `compress_png` | Optimize PNG files using pngquant |
| `convert_format` | Convert between image formats (PNG/JPEG/WebP/GIF/BMP) |
| `get_image_metadata` | Get format, dimensions, mode, and transparency info |

## Requirements

- Python 3.10+
- [pngquant](https://pngquant.org/) (optional, for PNG compression)

## Installation

### From Source

```bash
git clone https://github.com/tsilva/mcp-image-tools.git
cd mcp-image-tools
uv sync
```

### Add to Claude Code

```bash
claude mcp add image-tools --scope user -- \
  uv run --directory /path/to/mcp-image-tools mcp-image-tools
```

## Usage

### Chromakey to Transparent

Remove green screen background with professional edge detection:

```python
# Default green (#00FF00) with tolerance 70
chromakey_to_transparent(
    input_path="/path/to/greenscreen.png",
    output_path="/path/to/transparent.png"
)

# Custom key color (blue screen)
chromakey_to_transparent(
    input_path="/path/to/bluescreen.png",
    output_path="/path/to/transparent.png",
    key_color="#0000FF",
    tolerance=50
)
```

**Algorithm:**
- Distance < tolerance → Full transparency (alpha = 0)
- Distance < tolerance×3 → Graduated alpha for smooth edges
- Distance ≥ tolerance×3 → Fully opaque

### Resize Image

```python
# Resize by width (maintains aspect ratio)
resize_image(
    input_path="/path/to/image.png",
    output_path="/path/to/resized.png",
    width=800
)

# Resize by scale factor
resize_image(
    input_path="/path/to/image.png",
    output_path="/path/to/half.png",
    scale=0.5
)

# Resize to exact dimensions
resize_image(
    input_path="/path/to/image.png",
    output_path="/path/to/thumbnail.png",
    width=100,
    height=100,
    maintain_aspect=False
)
```

### Compress PNG

```python
# Compress with default quality (80)
compress_png(input_path="/path/to/image.png")

# Compress to new file with custom quality
compress_png(
    input_path="/path/to/image.png",
    output_path="/path/to/compressed.png",
    quality=60
)
```

> **Note:** Requires [pngquant](https://pngquant.org/) installed. Gracefully skips compression if not available.

### Convert Format

```python
# PNG to JPEG
convert_format(
    input_path="/path/to/image.png",
    output_path="/path/to/image.jpg",
    quality=90
)

# JPEG to WebP
convert_format(
    input_path="/path/to/photo.jpg",
    output_path="/path/to/photo.webp"
)
```

### Get Image Metadata

```python
get_image_metadata(image_path="/path/to/image.png")
# Returns: format, mode, width, height, has_transparency, file_size_bytes
```

## Development

```bash
# Install with dev dependencies
uv sync --all-extras

# Run tests
uv run pytest tests/ -v

# Run server locally
uv run mcp-image-tools
```

## License

[MIT](LICENSE)
