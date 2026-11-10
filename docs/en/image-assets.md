# NMAH military object image assets

[中文版](../zh/image-assets.md) · [Documentation index](README.md)

`get_nmah_military_object_image_assets` is a read-only tool. Pass a bare `record_id` from `content.descriptiveNonRepeating.record_ID` in a search result. The tool checks the record ID, NMAH unit, EDAN object type, and Armed Forces History set-name prefix before checking IIIF. Invalid input and unavailable or out-of-scope records raise tool errors.

## Input schema

For example, pass `{"record_id": "nmah_446333"}`.

```json
{
  "properties": {
    "record_id": {
      "maxLength": 64,
      "pattern": "^nmah_[0-9]+$",
      "type": "string",
      "description": "Bare catalog record ID, such as nmah_463569."
    }
  },
  "required": [
    "record_id"
  ],
  "type": "object",
  "additionalProperties": false
}
```

## Output schema

`images` groups resources by media ID when available. For the same image, Open Access high-resolution JPEG and TIFF resources appear before IIIF candidates. The tool checks the public Smithsonian IIIF Presentation 2 Manifest for matching or additional views. Each resource carries its own declared dimensions. The schema blocks are exported from FastMCP Inspect.

<details>
<summary>Full output JSON Schema</summary>

```json
{
  "properties": {
    "record_id": {
      "maxLength": 64,
      "pattern": "^nmah_[0-9]+$",
      "type": "string"
    },
    "status": {
      "enum": [
        "resolved",
        "partial",
        "no_assets"
      ],
      "type": "string"
    },
    "manifest_url": {
      "anyOf": [
        {
          "format": "uri",
          "type": "string"
        },
        {
          "type": "null"
        }
      ]
    },
    "manifest_license_url": {
      "anyOf": [
        {
          "format": "uri",
          "type": "string"
        },
        {
          "type": "null"
        }
      ]
    },
    "images": {
      "items": {
        "else": {
          "properties": {
            "usage_label": {
              "const": "Usage Conditions Apply"
            }
          }
        },
        "if": {
          "properties": {
            "media_access": {
              "const": "CC0"
            }
          }
        },
        "properties": {
          "media_id": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ]
          },
          "media_access": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ]
          },
          "usage_label": {
            "enum": [
              "CC0",
              "Usage Conditions Apply"
            ],
            "type": "string"
          },
          "resources": {
            "items": {
              "properties": {
                "source": {
                  "enum": [
                    "open_access",
                    "iiif"
                  ],
                  "type": "string"
                },
                "format": {
                  "enum": [
                    "jpeg",
                    "tiff"
                  ],
                  "type": "string"
                },
                "url": {
                  "format": "uri",
                  "type": "string"
                },
                "declared_width": {
                  "anyOf": [
                    {
                      "minimum": 1,
                      "type": "integer"
                    },
                    {
                      "type": "null"
                    }
                  ]
                },
                "declared_height": {
                  "anyOf": [
                    {
                      "minimum": 1,
                      "type": "integer"
                    },
                    {
                      "type": "null"
                    }
                  ]
                }
              },
              "required": [
                "source",
                "format",
                "url",
                "declared_width",
                "declared_height"
              ],
              "type": "object"
            },
            "minItems": 1,
            "type": "array"
          }
        },
        "required": [
          "media_id",
          "media_access",
          "usage_label",
          "resources"
        ],
        "then": {
          "properties": {
            "usage_label": {
              "const": "CC0"
            }
          }
        },
        "type": "object"
      },
      "type": "array"
    },
    "warnings": {
      "items": {
        "type": "string"
      },
      "type": "array"
    }
  },
  "required": [
    "record_id",
    "status",
    "manifest_url",
    "manifest_license_url",
    "images",
    "warnings"
  ],
  "type": "object"
}
```

</details>

## Per-image CC0

The tool reads `content.descriptiveNonRepeating.online_media.media[]` one entry at a time. `media_access` preserves the corresponding `usage.access` string, or `null` when absent. `usage_label` is `CC0` only when that image's own value is explicitly `CC0`. All other values display `Usage Conditions Apply`. In a two-image record, one image can display CC0 while the other displays Usage Conditions Apply with `media_access: null`.

Record metadata rights and the Manifest terms link do not supply a missing per-image CC0 value. The raw value distinguishes an explicit museum usage statement from a missing API field. See [EDAN 1.09 rights fields](https://sirismm.si.edu/siris/EDAN_IMM_OBJECT_RECORDS_1.09.pdf) and the [API and media guide](smithsonian-api-and-media.md).

## Discovery status

| Status | Meaning |
| --- | --- |
| `resolved` | Source checks completed and found at least one supported resource. IIIF fallback and missing image rights can both occur in this state. |
| `partial` | At least one source could not be fully checked. The tool returns any resources found, possibly an empty list, and explains the gap in `warnings`. For example, Open Access returns a JPEG and the IIIF request times out. |
| `no_assets` | Source checks completed without finding a supported resource. |

## View images in the Playground

In **Inspect a record**, select **Image assets**, enter the NMAH record ID,
and submit the lookup. In the **Resource** column, select **View image**.

- **Open Access API** opens a dialog where you can choose an available JPEG or TIFF.
- **IIIF** opens the image in a new browser tab.

## Live verification

Both MCP calls returned `resolved` on 2026-11-08 UTC. The separate Smithsonian Collections Skill downloaded both JPEGs to a temporary directory and verified their format, full decoding, dimensions, and SHA-256.

| Record | Media ID | Download source and verified size | `media_access` → `usage_label` |
| --- | --- | --- | --- |
| `nmah_446333` | `NMAH-2004-46240` | [Open Access high-resolution JPEG](https://ids.si.edu/ids/download?id=NMAH-2004-46240.jpg), 514 × 768 | `CC0` → `CC0` |
| `nmah_463569` | `NMAH-AHB2010q67926` | [IIIF full-size JPEG](https://ids.si.edu/ids/iiif/NMAH-AHB2010q67926/full/full/0/default.jpg), 3000 × 2250 | `null` → `Usage Conditions Apply` |

For `nmah_446333`, the high-resolution API resource declared 514 × 768 and the matching IIIF resource declared 428 × 640. The Skill used the API JPEG and skipped the duplicate IIIF view. For `nmah_463569`, the Content response had no media entry. The object-level Manifest supplied the full-size JPEG and linked to [Smithsonian Terms of Use](https://www.si.edu/termsofuse).

JPEG SHA-256 values from the download receipts.

- `nmah_446333` — `807cb6e1775ebfdd2bff62dff66ce9867cb1f10959504323b07762d997b5b3d6`
- `nmah_463569` — `288781560e78bdf526dbf6186e51f0cfe3aa3a90e7a5ad324e6b433b366c312b`
