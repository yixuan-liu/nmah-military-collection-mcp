# Smithsonian API, EDAN records, and image verification

[中文版](../zh/smithsonian-api-and-media.md) · [Architecture](architecture.md) · [Swagger UI guide](swagger-ui.md)

The search tool calls `GET /search` with `q` and `fqs`. The metadata tool calls `GET /content/{id}` and checks the returned record against the same collection scope. See the [tool flows](architecture.md).

The following references cover the API and EDAN data model. The [OpenAPI definition](../reference/smithsonian/swagger/openapi.json) powers the local Swagger UI.

| Reference | What it describes | Development use |
| --- | --- | --- |
| [Official Open Access API documentation](https://edan.si.edu/openaccess/apidocs/) | Content, search, category search, statistics, and terms endpoints | Operations and parameters |
| [Official EDAN JSON format](https://edan.si.edu/openaccess/docs/more.html) | EDAN record envelope, identifiers, and version fields | Identity and parsing boundaries |
| [EDAN_IMM_OBJECT_RECORDS_1.09.md](https://sirismm.si.edu/siris/EDAN_IMM_OBJECT_RECORDS_1.09.pdf) | Object metadata model, version 1.09, dated December 18, 2019 | Field meaning and source semantics |

## Other API operations

### Vocabulary discovery

`/terms/:category` supplies allowed categories and optional `starts_with`. Use it to discover vocabulary, then test candidate mappings inside the military scope. The source does not advertise `q`, `fqs`, museum scoping, or facet counts for this endpoint; `set_name` is not an allowed category.

Initially this can be an internal maintenance capability. Do not inject the entire vocabulary into a tool docstring. A global term may have no scoped matches, and a populated main topic does not establish exhaustive conflict coverage.

### Sorting, statistics, and record types

- The current `sort=id` supports pagination checks under stable conditions; the first page is not a ranked list of important artifacts. The source calls relevancy the default but lists only `id`, `newest`, `updated`, and `random` as allowed explicit values. Verify omission-based relevance behavior before adding an explicit value.
- `/stats` describes CC0 object/media statistics. Do not substitute global figures for a scoped military search count.
- `/category/:cat/search` exposes three broad subject categories, not the custom A–L taxonomy, branches, or conflicts.
- `type` and `row_group` partition upstream records. The current fixed `type:edanmdm` does not need archival expansion solely because the general API supports it.
- The documented `rows` range is 0–1000. The MCP's 1–50 limit is a context-budget choice, not an API compatibility bug.

## EDAN JSON record identity and envelope

| Source field | Meaning | Recommended use |
| --- | --- | --- |
| Top-level `id` | EDAN record identifier | API lookup; treat as opaque |
| Top-level `url` | Repository normalization key, such as `edanmdm:nmah_1119480` | API lookup, not an ordinary web URL |
| `content.descriptiveNonRepeating.record_ID` | Home-system record identifier | User-facing identity and linking |
| `content.descriptiveNonRepeating.guid` | DOI/ARK identifier | Source citation; preserve as provided |
| `content.freetext.identifier` | Labeled catalog/accession identifiers | Preserve roles rather than collapsing them into one ID |

Raw output currently retains this information, but each client must interpret it independently. A typed response can expose these identities clearly while retaining the raw record for verification.

`lastTimeUpdated`, `docSignature`, and `version` can support future cache invalidation or change detection; they do not establish that this project stores retrievable revision history. The documented ID-generation scheme is not a reason for clients to depend on its internal format.

Distinguish API-envelope `status=200` from record publication `status=0`. They belong to different layers and must not share an interpretation merely because the property name is identical.

## EDAN metadata model: three responsibilities

| Section | Source purpose | Suggested handling |
| --- | --- | --- |
| `descriptiveNonRepeating` | Identity, source, title, media, metadata rights | Record identity and media structure |
| `indexedStructured` | Normalized search/facet access points | Filter values and matching evidence |
| `freetext` | Labeled display text | Preserve descriptions, dates, roles, and source meaning |

A small parsing layer can respect these boundaries without creating a tool for each section.

### Preserve labels rather than converting observations into conclusions

```json
{
  "label": "associated date",
  "content": "1859"
}
```

This is not automatically `manufacture_year=1859`. A person in `name` is not necessarily a maker: roles include Maker, Sitter, Creator, and others. Summaries should retain labels and values rather than extracting only the first text entry and losing its role.

### Date examples are not an exhaustive enumeration

The document gives examples such as `1870s` and `1910s`. A previously saved `nmah_1341785` response contains `indexedStructured.date=["1914-1918"]`. The current 1770s–2000s parameter is a product-level decade selector, not the complete catalog date grammar.

Keep the existing interface initially, with clear limitations. Range expansion requires API verification and must not turn a date string into an inferred manufacturing date.

### Set Name denotes logical grouping

Set Name includes collections and logical groups, with an exhibition among the examples. It can scope searches but is not an authoritative organization chart. Records can belong to multiple sets.

Display `setName` lives in `freetext`, while the project uses the verified search field `set_name`. JSON paths and searchable field names are not a mechanical one-to-one mapping; searchable filters cannot be inferred solely from membership in `indexedStructured`.

### Keep metadata, media, and object rights separate

```text
metadata_usage
media[].usage
object_rights
```

The source separates metadata licensing, each media item's usage, and rights in the object. Do not collapse these into an ambiguous `is_cc0`. Missing information should remain unknown, not automatically public or restricted.

The current `online_media_type:Images` filter means that images are indexed. It guarantees neither a download URL in the search response nor CC0 media.

### Exhibition and provenance

Use explicit `onPhysicalExhibit` and `exhibition` information where present. Images do not imply display, and missing display data does not imply storage. The source also distinguishes current/future exhibition information from a historical exhibition archive.

Preserve `creditLine`, record/media `preferred_citation`, and `related_record` information in a future detail view. A credit line is not necessarily full provenance; shared identifiers or related records do not independently establish an ownership history.

Taxonomic, geological, and stratigraphic sections describe the general model. A military service does not need to model all of them merely because they appear in the specification.

## Search parameters and response fields

Both search operations accept `fqs` as a JSON-encoded array string. See the [API reference](https://edan.si.edu/openaccess/apidocs/). The EDAN documents use illustrative placeholders and XML field requirements. Observed Open Access JSON can differ, including numeric strings in timestamp fields and sections that remain in the body after removal in the revision history. Use real responses to verify parser assumptions.

## Image filters and media verification

The counts and record checks below were recorded on **2026-11-08**.

### Conclusion

Use `online_media_type:Images` in the Open Access API when users request objects with images. Do not copy the website's `online_visual_material:true` expression into the API and assume equivalent behavior.

The existing `query.py` already maps the tool's `has_images=True` to `online_media_type:Images`. Retain that mapping. An image index flag does not guarantee an image URL in the response or a CC0 image license.

### Scope and live counts

The scope fixes `q=*`, `type=edanmdm`, and `row_group=objects`, with NMAH, the Armed Forces History set-name prefix, and Insignias combined in `fqs`. Count checks used `rows=1`; the preceding Swagger first-page checks used `rows=10`. Counts are `response.rowCount`, not the number of returned rows.

| API filters within the fixed scope | Total matches | First record |
| --- | ---: | --- |
| `online_media_type:Images` | 19,962 | `nmah_463569` |
| Above plus `online_visual_material:true` | 1 | `nmah_439653` |
| Above plus `online_visual_material:false` | 19,961 | `nmah_463569` |
| Above plus `media_usage:CC0` | 1 | `nmah_439653` |

Within this scope and snapshot, the visual-material and CC0 filters returned the same single record. No official definition of the former field's internal computation was established. This is not proof of universal equivalence or of a specific restriction affecting every excluded record.

The preceding Swagger comparison returned 19,962 and 1 respectively from both `/search` and `/category/history_culture/search`. The first ten IDs and their order matched for the Images query. The complete result sets were not compared record by record.

### Record-level comparison: nmah_463569

The title is `insignia`, with object name `Insignia; Navy; Ribbon, Hat`, catalog number `1982.0590.01`, and associated date 1917–1918. An associated date is not necessarily a manufacture date. Its set name is `Military and Society: Armed Forces History, Naval`.

| Check | Observation |
| --- | --- |
| Website search with `edan_q=nmah_463569` and `online_visual_material:true` | One result; Show only items with images is checked |
| API search with `q=nmah_463569`, no image filter | One result |
| API with `online_media_type:Images` | One result |
| API with `online_visual_material:true` | Zero results |
| API with `online_visual_material:false` | One result |
| Website object page | Image loads; Usage Conditions Apply |
| `content/edanmdm:nmah_463569` | Images appears in `indexedStructured.online_media_type`; `descriptiveNonRepeating.online_media` is absent |
| Object-level IIIF Manifest | One canvas with an image resource and image service |

### Image location and rights

The media ID is `NMAH-AHB2010q67926`. The object page loads:

<https://ids.si.edu/ids/deliveryService?id=NMAH-AHB2010q67926&max=600>

The browser confirmed a successfully loaded 600 × 450 thumbnail. The object-level Manifest declares a 3000 × 2250 image and supplies:

<https://ids.si.edu/ids/iiif/NMAH-AHB2010q67926/full/full/0/default.jpg>

The full-size JPEG was not downloaded or fully decoded during this check; its dimensions are Manifest-declared. Image resources are under `sequences[].canvases[].images[].resource`, with the image service under `resource.service`. The website's IIIF button links to a media-level Manifest; the object-level Manifest associates the record with the same media ID.

The page labels the image Usage Conditions Apply and states that reuse is restricted. The Manifest's `license` points to Smithsonian Terms of Use. `metadata_usage.access=CC0` in the API concerns metadata, not the image.

Official developer guidance explains that objects with copyright or other limitations can have CC0 metadata without media files supplied through Open Access. This is consistent with this record's website image and missing API media URLs. The specific restriction was not established; it should not automatically be described as copyright.

### MCP recommendations

1. Retain the image-only mapping to `online_media_type:Images`.
2. Represent image indexing, API media URLs, public IIIF availability, and media rights separately. Do not collapse them into one inferred `is_cc0` or `has_image` value.
3. Inspect `descriptiveNonRepeating.online_media.media` first. If absent, an object-level public IIIF Manifest can provide a fallback. Empty or failed retrieval means unknown or unavailable, not proof that no image exists.
4. Add `media_usage:CC0` only when users explicitly request CC0 media, and still inspect individual media rights. Public viewing does not imply unrestricted reuse.
5. Clients may use IIIF as a fallback when they need media. The metadata tool returns the museum record as supplied.

### Reproducible request

The example reads the key from the environment and supplies it as a request header. It does not print credentials. `fqs` is a JSON-encoded array string; the HTTP client handles URL encoding. The terminal prefix wildcard remains unescaped.

```python
import json
import os
import httpx

filters = [
    "unit_code:NMAH",
    r"set_name:Military\ and\ Society\:\ Armed\ Forces\ History*",
    'object_type:"Insignias"',
    "online_media_type:Images",
]
params = {
    "q": "*",
    "start": 0,
    "rows": 10,
    "type": "edanmdm",
    "row_group": "objects",
    "fqs": json.dumps(filters),
}
response = httpx.get(
    "https://api.si.edu/openaccess/api/v1.0/search",
    params=params,
    headers={"X-Api-Key": os.environ["SMITHSONIAN_API_KEY"]},
    timeout=30,
)
response.raise_for_status()
data = response.json()
print(data["response"]["rowCount"])
```

### Evidence and limitations

- [Content response](../evidence/image-filter-validation-2026-11-08/nmah_463569-content.json)
- [Object-level Manifest](../evidence/image-filter-validation-2026-11-08/nmah_463569-manifest.json)

These JSON files are parsed and formatted copies of live responses, not original HTTP byte archives. They do not include full response headers or exact request timestamps. Counts and website observations are transcribed from this session's tool results; full search responses and browser screenshots were not retained. Counts are a dated snapshot, not a future guarantee.

### Official sources

- [NMAH object page](https://americanhistory.si.edu/collections/object/nmah_463569)
- [NMAH image-only search for this record](https://americanhistory.si.edu/collections/search?edan_q=nmah_463569&edan_fq%5B%5D=online_visual_material%3Atrue)
- [Object-level IIIF Manifest](https://ids.si.edu/ids/manifest/edanmdm:nmah_463569)
- [Media-level Manifest linked by the object page](https://ids.si.edu/ids/manifest/NMAH-AHB2010q67926)
- [Official developer guidance](https://www.si.edu/openaccess/devtools)
- [Official API documentation](https://edan.si.edu/openaccess/apidocs/)
