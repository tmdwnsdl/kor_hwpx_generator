from fastmcp import FastMCP
from renderer import render_html
from command_processor import process_command
from hwpx_renderer import render_hwpx_real

mcp = FastMCP("hwpx-mcp")


@mcp.tool()
def preview_html(doc_json: dict) -> str:
    return render_html(doc_json)


@mcp.tool()
def edit_document(doc_json: dict, command: str) -> dict:
    return process_command(doc_json, command)


@mcp.tool()
def generate_hwpx(doc_json: dict) -> str:
    return render_hwpx_real(doc_json)


if __name__ == "__main__":
    mcp.run()