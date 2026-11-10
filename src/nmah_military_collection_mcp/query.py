from .models import BranchLiteral, DecadeLiteral, SearchRequest
from .scope import build_scope_filters

BRANCH_ALIASES: dict[str, list[str]] = {
    "Army": ["Army", "USA", "WAC", "WAAC", "Military Academy"],
    "Navy": [
        "Navy",
        "USN",
        "U.S.N.",
        "USNR",
        "Naval Academy",
        "Midshipman",
        "Naval Reserve",
    ],
    "Air Force": ["Air Force", "USAF", "Army Air Forces", "USAAF", "Air Corps"],
    "Marine Corps": ["Marine Corps", "USMC", "Marines", "Marine", "U.S.M.C."],
    "Coast Guard": ["Coast Guard", "USCG", "U.S.C.G."],
}


def case_insensitive_pattern(term: str) -> str:
    """Build a case-insensitive pattern for the fixed ASCII aliases."""
    return "".join(
        f"[{char.upper()}{char.lower()}]"
        if char.isalpha()
        else "[.]"
        if char == "."
        else char
        for char in term
    )


def build_branch_filter(branch: BranchLiteral) -> str:
    """Match aliases in either field, requiring ASCII word boundaries for abbreviations and Marine."""
    patterns = []
    for alias in BRANCH_ALIASES[branch]:
        term = case_insensitive_pattern(alias)
        if alias in {
            "USA",
            "USN",
            "USAF",
            "USAAF",
            "USMC",
            "USCG",
            "Marine",
            "U.S.N.",
            "USNR",
            "U.S.C.G.",
            "U.S.M.C.",
            "WAC",
            "WAAC",
        }:
            patterns.append(f"(.*[^A-Za-z0-9_])?{term}([^A-Za-z0-9_].*)?")
        else:
            patterns.append(f".*{term}.*")
    pattern = "(" + "|".join(patterns) + ")"
    return f"(title:/{pattern}/ OR object_type:/{pattern}/)"


def build_search_request(
    query: str,
    branch: BranchLiteral | None,
    rows: int,
    offset: int,
    date: DecadeLiteral | None,
    has_images: bool,
) -> SearchRequest:
    """Build the upstream query without performing network operations."""
    filters = build_scope_filters()
    if branch is not None:
        filters.append(build_branch_filter(branch))
    if date is not None:
        filters.append(f'date:"{date}"')
    if has_images:
        filters.append("online_media_type:Images")
    return SearchRequest(query.strip() or "*", tuple(filters), rows, offset)
