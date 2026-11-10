import json
import logging
from time import perf_counter
from urllib.parse import quote

import httpx

from .config import API_BASE_URL, get_api_key
from .errors import ImageManifestError, SmithsonianAPIError
from .models import SearchPage, SearchRequest

logger = logging.getLogger(__name__)


class SmithsonianAPIClient:
    """Send Open Access requests and validate their envelopes."""

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def _get(
        self,
        kind: str,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        started = perf_counter()
        try:
            response = await self._http.get(url, params=params, headers=headers)
        except httpx.RequestError as exc:
            logger.warning(
                "upstream_failed endpoint=%s error_type=%s elapsed_ms=%.1f",
                kind,
                type(exc).__name__,
                (perf_counter() - started) * 1000,
            )
            raise
        level = (
            logging.WARNING
            if response.is_error and response.status_code != 404
            else logging.DEBUG
        )
        logger.log(
            level,
            "upstream_response endpoint=%s status=%d elapsed_ms=%.1f",
            kind,
            response.status_code,
            (perf_counter() - started) * 1000,
        )
        return response

    async def _request(self, endpoint: str, *, params: dict | None = None) -> dict:
        api_key = get_api_key()
        if not api_key:
            raise SmithsonianAPIError(
                "Set SMITHSONIAN_API_KEY in the server environment."
            )
        kind = "search" if endpoint == "search" else "content"
        try:
            response = await self._get(
                kind,
                f"{API_BASE_URL}/{endpoint}",
                params=params,
                headers={"X-Api-Key": api_key},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if endpoint.startswith("content/") and exc.response.status_code == 404:
                raise SmithsonianAPIError(
                    "The requested Smithsonian record was not found."
                ) from exc
            raise SmithsonianAPIError(
                f"Smithsonian returned HTTP {exc.response.status_code}."
            ) from exc
        except httpx.RequestError as exc:
            raise SmithsonianAPIError(
                "Could not reach Smithsonian Open Access."
            ) from exc
        try:
            payload = response.json()
            if payload.get("status") != 200 or payload.get("responseCode") != 1:
                logger.warning("upstream_unsuccessful endpoint=%s", kind)
                raise SmithsonianAPIError(
                    f"Smithsonian returned an unsuccessful {kind} response."
                )
            result = payload["response"]
            if not isinstance(result, dict):
                raise ValueError("Unexpected response type.")
            return result
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            logger.warning("upstream_invalid_response endpoint=%s", kind)
            qualifier = (
                "an unexpected response"
                if kind == "search"
                else "an unverifiable content response"
            )
            raise SmithsonianAPIError(
                f"Smithsonian returned {qualifier} structure."
            ) from exc

    async def search(self, request: SearchRequest) -> SearchPage:
        result = await self._request(
            "search",
            params={
                "q": request.query,
                "fqs": json.dumps(request.filters),
                "rows": request.rows,
                "start": request.offset,
                "sort": "id",
            },
        )
        total, records = result.get("rowCount"), result.get("rows")
        if not isinstance(total, int) or not isinstance(records, list):
            logger.warning("upstream_invalid_response endpoint=search")
            raise SmithsonianAPIError(
                "Smithsonian returned an unexpected response structure."
            )
        return SearchPage(total, records)

    async def get_content(self, repository_id: str) -> dict:
        return await self._request(f"content/{quote(repository_id, safe='')}")

    @staticmethod
    def image_manifest_url(repository_id: str) -> str:
        return f"https://ids.si.edu/ids/manifest/{quote(repository_id, safe=':')}"

    async def get_image_manifest(self, repository_id: str) -> dict | None:
        """Read a public object manifest without Open Access credentials."""
        try:
            response = await self._get(
                "iiif_manifest", self.image_manifest_url(repository_id)
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ImageManifestError(
                f"Could not check the IIIF manifest: HTTP {exc.response.status_code}."
            ) from exc
        except httpx.RequestError as exc:
            raise ImageManifestError(
                "Could not reach the Smithsonian IIIF service."
            ) from exc
        try:
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError("Expected a JSON object.")
            return result
        except ValueError as exc:
            logger.warning("upstream_invalid_response endpoint=iiif_manifest")
            raise ImageManifestError("The IIIF manifest is not a JSON object.") from exc
