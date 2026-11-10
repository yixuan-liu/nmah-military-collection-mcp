from dataclasses import dataclass
from typing import Literal

BranchLiteral = Literal["Army", "Navy", "Air Force", "Marine Corps", "Coast Guard"]
DecadeLiteral = Literal[
    "1770s",
    "1780s",
    "1790s",
    "1800s",
    "1810s",
    "1820s",
    "1830s",
    "1840s",
    "1850s",
    "1860s",
    "1870s",
    "1880s",
    "1890s",
    "1900s",
    "1910s",
    "1920s",
    "1930s",
    "1940s",
    "1950s",
    "1960s",
    "1970s",
    "1980s",
    "1990s",
    "2000s",
]


@dataclass(frozen=True)
class SearchRequest:
    query: str
    filters: tuple[str, ...]
    rows: int
    offset: int


@dataclass(frozen=True)
class SearchPage:
    total_count: int
    records: list[dict]
