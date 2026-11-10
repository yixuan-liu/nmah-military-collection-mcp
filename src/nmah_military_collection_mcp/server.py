"""Start the MCP server or expose the application to FastMCP Inspect."""

from nmah_military_collection_mcp.app import mcp as mcp
from nmah_military_collection_mcp.logging_config import configure_project_logging


def main() -> None:
    """Serve the MCP application over standard input and output."""
    configure_project_logging()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
