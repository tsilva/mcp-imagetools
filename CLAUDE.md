# CLAUDE.md

MCP server providing image processing tools for Claude Code.

## Tools

| Tool | Description |
|------|-------------|
| `chromakey_to_transparent` | Convert green screen backgrounds to transparency with professional-quality edge blending |
| `compress_png` | Optimize PNG files using pngquant (graceful degradation if not installed) |
| `get_image_metadata` | Get format, dimensions, transparency info |
| `resize_image` | Resize by dimensions or scale factor with aspect ratio control |
| `convert_format` | Convert between PNG/JPEG/WebP/GIF/BMP |

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest tests/ -v

# Run server
uv run mcp-image-tools
```

## Adding to Claude Code

```bash
claude mcp add image-tools --scope user -- uv run --directory /path/to/mcp-image-tools mcp-image-tools
```

## Chromakey Algorithm

The chromakey tool uses Euclidean distance in RGB color space:
- Distance < tolerance: Full transparency (alpha = 0)
- Distance < tolerance*3: Graduated alpha for smooth edges
- Distance >= tolerance*3: Fully opaque

Default key color is `#00FF00` (green) with tolerance of 70.
