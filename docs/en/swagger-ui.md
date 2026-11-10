# Unofficial Swagger reference for Smithsonian Open Access

This independently maintained Swagger UI presents five GET operations from the
[official Smithsonian Open Access API documentation](https://edan.si.edu/openaccess/apidocs/).

[中文版](../zh/swagger-ui.md)

## Open the UI

From the project root, serve the documentation directory on loopback:

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory docs
```

Open [http://127.0.0.1:8765/reference/smithsonian/swagger/](http://127.0.0.1:8765/reference/smithsonian/swagger/).

All rendering assets and the specification are local. Opening the [Swagger page](../reference/smithsonian/swagger/index.html) directly can also render the reference without fetching the specification; loopback HTTP is recommended for consistent browser behavior. Reading the UI requires no API key or Internet connection. Executing a request requires a key, network access, and the upstream API's CORS permission for the browser origin. CORS behavior and live execution are not certified by static specification validation. No proxy is included; use the existing server-side API client if browser access is blocked.

## API references

- [Official Open Access API documentation](https://edan.si.edu/openaccess/apidocs/) covers the operations, request parameters, and response examples.
- [Official EDAN JSON format](https://edan.si.edu/openaccess/docs/more.html) covers repository fields and includes a parseable example.
- [EDAN metadata model 1.09](https://sirismm.si.edu/siris/EDAN_IMM_OBJECT_RECORDS_1.09.pdf) explains type-specific content; it is not treated as a strict modern JSON schema.
- [openapi.json](../reference/smithsonian/swagger/openapi.json) defines the OpenAPI 3.0.3 representation used by this UI.
- Response models for `/content/{id}` and `/search` are permissive representations of source examples, not new guarantees of field presence. The invalid placeholder for `content` is shown as `{}` with an explicit explanation.
- The source does not define the response body for `/stats`, `/terms/{category}`, or category search. These operations intentionally do not invent schemas or example counts.
- The source states that sorting defaults to relevancy but lists only `id`, `newest`, `updated`, and `random` as accepted values. The spec lists those four and says to omit `sort` for the default; it does not set a default outside its enum.
- The current official API page documents optional `fqs` for both search operations. Both accept a JSON-encoded array as a string. `/search` accepts an optional `q`; category search requires `q`.
- `Permission: edan` is retained as prose, not invented as an OAuth scope.
- This is the general Smithsonian API. The UI does not automatically add NMAH, Armed Forces History, image, date, or branch filters.

## Authentication and execution

The source documents an `api_key` query parameter; OpenAPI models it as an `apiKey` security scheme. Click **Authorize** and enter your own key only if you intend to execute a request. Keys are not read from `.env` or Codex configuration and are not included in any file. Authorization is not persisted across refreshes. Query keys can appear in request URLs and generated cURL examples; do not share those requests with credentials intact.

No request runs on load. Only GET submission is enabled, Try it out is inactive initially, URL-based configuration overrides are disabled, and the external Swagger validator service is disabled. Those settings do not imply that API requests are offline or free from upstream quotas.

## Files and maintenance

| File | Purpose |
| --- | --- |
| `openapi.json` | Canonical editable API definition |
| `openapi-spec.js` | Generated mirror for offline rendering |
| `index.html` | English documentation page |
| `swagger-initializer.js` | Explicit Swagger UI configuration |
| `sync-spec.mjs` | Generate or check the mirror |
| `vendor-manifest.json` | Pinned package identity, registry integrity, and asset hashes |
| `vendor/swagger-ui-5.34.1/` | Official unmodified distribution assets and license notices |

After editing the definition:

```sh
node docs/reference/smithsonian/swagger/sync-spec.mjs
node docs/reference/smithsonian/swagger/sync-spec.mjs --check
```

Validate with an OpenAPI validator in a separate temporary environment before publishing. The initial build uses `@apidevtools/swagger-parser@13.1.0`; no Node package or Python dependency is added to the MCP project. Static validation and rendering checks do not verify live service behavior.

## Standards and references

- [OpenAPI Specification 3.0.3](https://spec.openapis.org/oas/v3.0.3.html)
- [Swagger UI installation](https://swagger.io/docs/open-source-tools/swagger-ui/usage/installation/)
- [Swagger UI configuration](https://swagger.io/docs/open-source-tools/swagger-ui/usage/configuration/)
- [Official Swagger UI repository](https://github.com/swagger-api/swagger-ui)
- [Smithsonian API documentation](https://edan.si.edu/openaccess/apidocs/)

Swagger UI is pinned to **5.34.1**. Its Apache 2.0 license, NOTICE, and bundled third-party notices are retained under `vendor/swagger-ui-5.34.1/`. The Smithsonian source material retains its original attribution; the vendored UI license does not relicense that material.

See the [English API and media guide](smithsonian-api-and-media.md) or the [Chinese guide](../zh/smithsonian-api-and-media.md) for how the MCP uses the API.
