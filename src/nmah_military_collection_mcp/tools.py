import logging
from time import perf_counter
from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from .context import get_api_client
from .errors import CollectionError
from .image_assets import ImageAssetsResult, discover_image_assets
from .models import BranchLiteral, DecadeLiteral
from .query import BRANCH_ALIASES, build_search_request
from .scope import RECORD_TYPE, validate_record_scope

logger = logging.getLogger(__name__)


async def search_nmah_military_objects(
    query: str = "",
    branch: BranchLiteral | None = None,
    rows: Annotated[int, Field(ge=1, le=50)] = 10,
    offset: Annotated[int, Field(ge=0)] = 0,
    date: DecadeLiteral | None = None,
    has_images: bool = False,
    *,
    ctx: Context,
) -> dict:
    """Search National Museum of American History (NMAH) objects within the
    "Military and Society: Armed Forces History" set-name prefix.

    Args:
        query: Keyword expression. Omit for filter-only search.
        branch: Optional research group matched against title and object_type.
            Army includes USA, WAC, and WAAC as standalone words, bounded by field edges or
            characters outside ASCII letters, digits, and underscore. Army also includes
            Military Academy. Navy includes USN, U.S.N., USNR, Naval Academy,
            Midshipman, and Naval Reserve.
            Air Force includes USAF, Army Air Forces, USAAF, and Air Corps.
            Marine Corps includes USMC, U.S.M.C., Marines, and standalone Marine.
            Coast Guard includes USCG and U.S.C.G..
            Matching ignores case. All abbreviations and Marine require standalone
            words. Dots in abbreviations are literal. Other aliases use substring matching.
            Groups may overlap. Preserve historical names from source records.
            Leave unset when the user does not specify a service branch.
        rows: Number of records to return, from 1 to 50.
        offset: Zero-based starting record position. Defaults to 0.
        date: Optional catalog decade label, from 1770s through 2000s.
            Matches the indexed date facet, not necessarily the manufacturing date.
        has_images: Show only items indexed as having images when true.
            Uses online_media_type:Images in the Open Access API.
            Image URLs may be absent from the API response.
            This filter does not imply CC0 image rights.
            False leaves image availability unrestricted.
    """
    started = perf_counter()
    logger.debug("search_page rows=%d offset=%d", rows, offset)
    request = build_search_request(query, branch, rows, offset, date, has_images)
    try:
        page = await get_api_client(ctx).search(request)
    except CollectionError as exc:
        raise ToolError(str(exc)) from exc
    total_count, records = page.total_count, page.records
    logger.info(
        "tool_completed tool=search_nmah_military_objects returned=%d total=%d elapsed_ms=%.1f",
        len(records),
        total_count,
        (perf_counter() - started) * 1000,
    )
    return {
        "total_count": total_count,
        "returned": len(records),
        "offset": offset,
        "next_offset": offset + len(records)
        if records and offset + len(records) < total_count
        else None,
        "applied_query": request.query,
        "applied_filters": list(request.filters),
        "branch": branch,
        "date": date,
        "has_images": has_images,
        "matched_alias_candidates": BRANCH_ALIASES.get(branch, []),
        "objects": records,
    }


async def get_nmah_military_object_metadata(
    record_id: Annotated[str, Field(pattern=r"^nmah_[0-9]+$", max_length=64)],
    *,
    ctx: Context,
) -> dict:
    """Retrieve the complete museum metadata record for one NMAH military object.

    Verify NMAH ownership and the Armed Forces History set-name prefix before
    returning the unmodified content endpoint response record. Out-of-scope,
    missing, or unverifiable records produce a tool error. No fields are
    summarized or removed, and no IIIF or other sources are added.

    Args:
        record_id: Bare catalog record ID, such as nmah_463569. Use
            content.descriptiveNonRepeating.record_ID from a search result,
            not its top-level id, catalog number, or a website URL.

    Image URLs can be absent even when the record is indexed as having images.
    Metadata CC0 status does not establish the rights of individual images.
    """
    started = perf_counter()
    try:
        record = await get_api_client(ctx).get_content(f"{RECORD_TYPE}:{record_id}")
        validate_record_scope(record, record_id)
    except CollectionError as exc:
        raise ToolError(str(exc)) from exc
    logger.info(
        "tool_completed tool=get_nmah_military_object_metadata returned=1 elapsed_ms=%.1f",
        (perf_counter() - started) * 1000,
    )
    return record


async def get_nmah_military_object_image_assets(
    record_id: Annotated[str, Field(pattern=r"^nmah_[0-9]+$", max_length=64)],
    *,
    ctx: Context,
) -> ImageAssetsResult:
    """List official JPEG and TIFF resources for one NMAH military object.

    Verify the collection scope, inspect Open Access media, and check the public
    IIIF manifest for additional views or fallback resources. Rights are reported
    per image from its own usage.access. Missing access is reported as null and
    displayed as Usage Conditions Apply. Status partial means a discovery source
    could not be fully checked. Dimensions are source declarations.

    Args:
        record_id: Bare catalog record ID, such as nmah_463569.
    """
    started = perf_counter()
    api = get_api_client(ctx)
    repository_id = f"{RECORD_TYPE}:{record_id}"
    try:
        record = await api.get_content(repository_id)
        validate_record_scope(record, record_id)
    except CollectionError as exc:
        raise ToolError(str(exc)) from exc
    result = await discover_image_assets(
        api, repository_id, record_id, record["content"]["descriptiveNonRepeating"]
    )
    logger.log(
        logging.WARNING if result.status == "partial" else logging.INFO,
        "tool_completed tool=get_nmah_military_object_image_assets status=%s returned=%d warnings=%d elapsed_ms=%.1f",
        result.status,
        len(result.images),
        len(result.warnings),
        (perf_counter() - started) * 1000,
    )
    return result


def register_tools(server: FastMCP) -> None:
    for tool in (
        search_nmah_military_objects,
        get_nmah_military_object_metadata,
        get_nmah_military_object_image_assets,
    ):
        server.tool(tool, annotations={"readOnlyHint": True, "openWorldHint": True})
