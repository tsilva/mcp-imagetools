# CLAUDE.md

MCP server providing image processing tools for Claude Code.

## Tools

**All paths must be absolute** (e.g., `/Users/me/image.png`, not `./image.png`).

| Tool | Description |
|------|-------------|
| `chromakey_to_transparent` | Convert green screen to transparency |
| `compress_png` | Optimize PNG using pngquant |
| `resize_image` | Resize by dimensions or scale |
| `convert_format` | Convert between formats (extension determines output format) |
| `get_image_metadata` | Get format, dimensions, transparency info |

All processing tools take `input_path` and `output_path` parameters and return JSON metadata.

## Example

```python
resize_image("/path/to/photo.png", "/path/to/thumb.png", width=200)
convert_format("/path/to/thumb.png", "/path/to/thumb.jpg")
```

## Development

```bash
uv sync                       # Install dependencies
uv run pytest tests/ -v       # Run tests
uv run mcp-image-tools        # Run server
```

## Adding to Claude Code

```bash
claude mcp add image-tools --scope user -- uv run --directory /path/to/mcp-image-tools mcp-image-tools
```

## Chromakey Algorithm

Uses Euclidean distance in RGB color space:
- Distance < tolerance: Full transparency (alpha = 0)
- Distance < tolerance*3: Graduated alpha for smooth edges
- Distance >= tolerance*3: Fully opaque

Default: `#00FF00` (green) with tolerance of 70.
