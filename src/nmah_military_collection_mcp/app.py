from collections.abc import Callable

import httpx
from fastmcp import FastMCP

from .context import RequestIDMiddleware, make_lifespan
from .tools import register_tools

SERVER_INSTRUCTIONS = (
    "Use search_nmah_military_objects to search National Museum of American History "
    "(NMAH) objects within the Military and Society: Armed Forces History set-name prefix. "
    "Put object names and descriptive terms in query; omit query for filter-only search. "
    "Use has_images=true for records indexed as having images. Image URLs may be absent "
    "from the API response, and this filter does not imply CC0 image rights. "
    "Preserve source dates and historical names; branch groups are research filters, "
    "not verified service attribution. Use next_offset with the same filters for pagination. "
    "Use get_nmah_military_object_metadata with content.descriptiveNonRepeating.record_ID "
    "from a search result to retrieve the complete museum record. "
    "This tool accepts bare IDs such as nmah_463569 and verifies the same collection scope. "
    "It returns source metadata without interpretation or additional IIIF retrieval. "
    "Use get_nmah_military_object_image_assets with the same record_id to discover "
    "official JPEG and TIFF links. Check usage_label per image and report any partial "
    "discovery warnings. This tool lists resources; local downloads are handled separately."
)


def create_app(
    *, client_factory: Callable[[], httpx.AsyncClient] | None = None
) -> FastMCP:
    """Assemble the tools and their dependencies."""
    server = FastMCP(
        "NMAH Military Collection",
        instructions=SERVER_INSTRUCTIONS,
        lifespan=make_lifespan(client_factory),
        middleware=[RequestIDMiddleware()],
    )
    register_tools(server)
    return server


mcp = create_app()
