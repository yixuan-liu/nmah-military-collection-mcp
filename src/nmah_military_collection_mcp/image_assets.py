from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from .api_client import SmithsonianAPIClient
from .errors import ImageManifestError

SourceURL = Annotated[str, Field(json_schema_extra={"format": "uri"})]
Dimension = Annotated[int, Field(ge=1)]

MEDIA_LABELS = {
    "High-resolution JPEG": "jpeg",
    "High-resolution TIFF": "tiff",
}
IIIF_IMAGE_PATH = "/ids/iiif/"
FULL_JPEG = "/full/full/0/default.jpg"


class ImageResource(BaseModel):
    source: Literal["open_access", "iiif"]
    format: Literal["jpeg", "tiff"]
    url: SourceURL
    declared_width: Dimension | None
    declared_height: Dimension | None


class ImageAsset(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "if": {"properties": {"media_access": {"const": "CC0"}}},
            "then": {"properties": {"usage_label": {"const": "CC0"}}},
            "else": {
                "properties": {"usage_label": {"const": "Usage Conditions Apply"}}
            },
        }
    )

    media_id: str | None
    media_access: str | None
    usage_label: Literal["CC0", "Usage Conditions Apply"]
    resources: Annotated[list[ImageResource], Field(min_length=1)]


class ImageAssetsResult(BaseModel):
    record_id: Annotated[str, Field(pattern=r"^nmah_[0-9]+$", max_length=64)]
    status: Literal["resolved", "partial", "no_assets"]
    manifest_url: SourceURL | None
    manifest_license_url: SourceURL | None
    images: list[ImageAsset]
    warnings: list[str]


def _official_url(value: object) -> str | None:
    if not isinstance(value, str) or not value or any(c.isspace() for c in value):
        return None
    try:
        parts = urlsplit(value)
        host = parts.hostname or ""
        if (
            parts.scheme == "https"
            and (host == "si.edu" or host.endswith(".si.edu"))
            and parts.username is None
            and parts.port in (None, 443)
        ):
            return value
    except ValueError:
        pass
    return None


def _dimension(value: object) -> int | None:
    return value if type(value) is int and value > 0 else None


async def discover_image_assets(
    api: SmithsonianAPIClient, repository_id: str, record_id: str, descriptive: dict
) -> ImageAssetsResult:
    manifest_url = api.image_manifest_url(repository_id)
    license_url = None
    warnings: list[str] = []
    resources: dict[str, list[ImageResource]] = {}
    access_by_id: dict[str, str | None] = {}
    unidentified: list[tuple[str | None, list[ImageResource]]] = []

    def add_resource(media_id: str, item: ImageResource) -> None:
        group = resources.setdefault(media_id, [])
        if not any(existing.url == item.url for existing in group):
            group.append(item)

    online = descriptive.get("online_media")
    media = online.get("media", []) if isinstance(online, dict) else []
    if (online is not None and not isinstance(online, dict)) or not isinstance(
        media, list
    ):
        warnings.append("Open Access media has an unexpected structure.")
        media = []
    for item in media:
        if not isinstance(item, dict):
            warnings.append("An Open Access media entry has an unexpected structure.")
            continue
        if item.get("type") != "Images":
            continue
        media_id = item.get("idsId") or item.get("id")
        media_id = (
            media_id.removeprefix("media:") if isinstance(media_id, str) else None
        )
        media_id = media_id or None
        usage = item.get("usage")
        access = usage.get("access") if isinstance(usage, dict) else None
        access = access if isinstance(access, str) else None
        if media_id is not None:
            if media_id in access_by_id and access_by_id[media_id] != access:
                access_by_id[media_id] = None
            else:
                access_by_id[media_id] = access

        candidates = item.get("resources", [])
        if not isinstance(candidates, list):
            warnings.append(
                "An Open Access image has an unexpected resources structure."
            )
            continue
        anonymous_resources = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                warnings.append(
                    "An Open Access image resource has an unexpected structure."
                )
                continue
            label = candidate.get("label")
            image_format = MEDIA_LABELS.get(label) if isinstance(label, str) else None
            if image_format is None:
                continue
            url = _official_url(candidate.get("url"))
            if url is None:
                warnings.append(
                    "An Open Access image resource has no valid Smithsonian URL."
                )
                continue
            resource = ImageResource(
                source="open_access",
                format=image_format,
                url=url,
                declared_width=_dimension(candidate.get("width")),
                declared_height=_dimension(candidate.get("height")),
            )
            if media_id is None:
                anonymous_resources.append(resource)
            else:
                add_resource(media_id, resource)
        if anonymous_resources:
            unidentified.append((access, anonymous_resources))

    try:
        manifest = await api.get_image_manifest(repository_id)
        if manifest is not None:
            license_url = _official_url(manifest.get("license"))
            for image in _manifest_images(manifest):
                url = _official_url(image.get("@id"))
                if url is None:
                    warnings.append("An IIIF image has no valid Smithsonian URL.")
                    continue
                parts = urlsplit(url)
                media_id = parts.path.removeprefix(IIIF_IMAGE_PATH).removesuffix(
                    FULL_JPEG
                )
                if (
                    parts.hostname != "ids.si.edu"
                    or not parts.path.startswith(IIIF_IMAGE_PATH)
                    or not parts.path.endswith(FULL_JPEG)
                    or not media_id
                    or "/" in media_id
                ):
                    warnings.append("An IIIF image uses an unsupported full JPEG URL.")
                    continue
                add_resource(
                    media_id,
                    ImageResource(
                        source="iiif",
                        format="jpeg",
                        url=url,
                        declared_width=_dimension(image.get("width")),
                        declared_height=_dimension(image.get("height")),
                    ),
                )
    except ImageManifestError as exc:
        warnings.append(str(exc))
    except (KeyError, TypeError, ValueError):
        warnings.append("The IIIF manifest has an unsupported image structure.")

    groups = [
        (media_id, access_by_id.get(media_id), items)
        for media_id, items in resources.items()
    ]
    groups.extend((None, access, items) for access, items in unidentified)
    images = [
        ImageAsset(
            media_id=media_id,
            media_access=access,
            usage_label="CC0" if access == "CC0" else "Usage Conditions Apply",
            resources=items,
        )
        for media_id, access, items in groups
    ]
    return ImageAssetsResult(
        record_id=record_id,
        status="partial" if warnings else "resolved" if images else "no_assets",
        manifest_url=manifest_url,
        manifest_license_url=license_url,
        images=images,
        warnings=list(dict.fromkeys(warnings)),
    )


def _manifest_images(manifest: dict):
    """Yield Presentation 2 image resources in manifest order."""

    def entries(container, key):
        items = container[key]
        if not isinstance(items, list):
            raise TypeError(key)
        return items

    for sequence in entries(manifest, "sequences"):
        for canvas in entries(sequence, "canvases"):
            for image in entries(canvas, "images"):
                resource = image["resource"]
                if not isinstance(resource, dict):
                    raise TypeError("resource")
                yield resource
