"""Exercise the MCP tool boundary with patched SDK and image-decoder versions."""

import asyncio
import json

from PIL import Image

from mcp_imagetools.server import mcp


def test_registered_tools_return_matching_text_and_structured_metadata(tmp_path):
    source = tmp_path / "source.png"
    resized = tmp_path / "resized.png"
    Image.new("RGB", (8, 6), "red").save(source)

    async def exercise():
        names = {tool.name for tool in await mcp.list_tools()}
        assert names == {
            "chromakey_to_transparent",
            "compress_png",
            "get_image_metadata",
            "resize_image",
            "convert_format",
        }
        result = await mcp.call_tool(
            "resize_image", {"input_path": str(source), "output_path": str(resized), "width": 4}
        )
        text = json.loads(result.content[0].text)
        assert text == json.loads(result.structured_content["result"])
        assert text["dimensions"] == {"width": 4, "height": 3}
        result = await mcp.call_tool(
            "get_image_metadata", {"image_path": str(resized)}
        )
        assert json.loads(result.content[0].text) == json.loads(result.structured_content["result"])
        assert json.loads(result.structured_content["result"])["format"] == "PNG"

    asyncio.run(exercise())
    with Image.open(resized) as result:
        assert result.size == (4, 3)
        assert result.getpixel((0, 0)) == (255, 0, 0)


def test_malformed_image_is_rejected_through_the_registered_tool(tmp_path):
    source = tmp_path / "malformed.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\ntruncated-header")

    async def exercise():
        result = await mcp.call_tool("get_image_metadata", {"image_path": str(source)})
        metadata = json.loads(result.structured_content["result"])
        assert metadata == json.loads(result.content[0].text)
        assert metadata["error"]
        assert "width" not in metadata

    asyncio.run(exercise())
    assert list(tmp_path.iterdir()) == [source]
