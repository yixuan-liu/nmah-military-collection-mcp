# NMAH 军事藏品图片清单工具

[English](../en/image-assets.md) · [文档目录](README.md)

`get_nmah_military_object_image_assets` 是只读工具。从搜索结果的 `content.descriptiveNonRepeating.record_ID` 取裸藏品编号。工具先核验编号、NMAH 馆别、EDAN 记录类型和 Armed Forces History 的 Set Name 前缀，再检查 IIIF。输入无效、馆方记录无法取得或藏品范围核验失败时返回工具错误。

## 输入 schema

例如传入 `{"record_id": "nmah_446333"}`。

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

## 输出 schema

能确定媒体 ID 时，`images` 按媒体 ID 组织。同一张图的 Open Access 高清 JPEG 和 TIFF 资源排在 IIIF 候选之前。工具检查 Smithsonian 的公开 IIIF Presentation 2 Manifest，核对同图资源并查找其他视角。尺寸字段来自各自资源的来源声明。以下 JSON Schema 由 FastMCP Inspect 导出。

<details>
<summary>展开完整输出 JSON Schema</summary>

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

## 逐图判定 CC0

工具逐项读取 `content.descriptiveNonRepeating.online_media.media[]`。每张图的 `media_access` 保留对应条目 `usage.access` 的原始字符串，缺失时为 `null`。只有该图明确标注 `CC0` 时，`usage_label` 才返回 `CC0`，其余情况显示 `Usage Conditions Apply`。同一藏品的第一张图可以是 CC0，第二张图缺少许可字段时仍返回 `media_access: null`，显示 Usage Conditions Apply。

元数据许可和 Manifest 条款链接都不能补成某张图的 CC0 标注。通过 `media_access` 可区分馆方明确声明使用条件与 API 字段缺失。[EDAN 1.09 权利字段](https://sirismm.si.edu/siris/EDAN_IMM_OBJECT_RECORDS_1.09.pdf) · [API 与图片核验指南](smithsonian-api-and-media.md)

## 清单状态

| 状态 | 含义 |
| --- | --- |
| `resolved` | 完成来源核验并找到至少一个支持的资源。通过 IIIF 找到图片，或某张图缺少许可字段，仍可返回此状态。 |
| `partial` | 至少一个来源未能完整核验。已找到的资源照常返回，也可能暂时没有结果。具体缺口写入 `warnings`。例如 Open Access 已找到 JPEG，但 IIIF 请求超时。 |
| `no_assets` | 完成来源核验，未找到支持的资源。 |

## 在 Playground 查看图片

在 **Inspect a record** 中选择 **Image assets**，输入 NMAH record ID 并提交查询。
在结果表的 **Resource** 栏选择 **View image**。

- **Open Access API** 图片会打开弹窗，可选择可用的 JPEG 或 TIFF。
- **IIIF** 图片会在浏览器新标签页打开。

## 实测结果

2026-11-08 UTC，两次 MCP 调用均返回 `resolved`。独立的 Smithsonian Collections Skill 将两张 JPEG 下载到临时目录，核对了格式、完整解码、实际尺寸和 SHA-256。

| 藏品 | 媒体 ID | 下载来源与实测尺寸 | `media_access` → `usage_label` |
| --- | --- | --- | --- |
| `nmah_446333` | `NMAH-2004-46240` | [Open Access 高清 JPEG](https://ids.si.edu/ids/download?id=NMAH-2004-46240.jpg), 514 × 768 | `CC0` → `CC0` |
| `nmah_463569` | `NMAH-AHB2010q67926` | [IIIF 全尺寸 JPEG](https://ids.si.edu/ids/iiif/NMAH-AHB2010q67926/full/full/0/default.jpg), 3000 × 2250 | `null` → `Usage Conditions Apply` |

`nmah_446333` 的 API 高清资源声明尺寸为 514 × 768，对应 IIIF 资源声明尺寸为 428 × 640。Skill 下载了 API 高清 JPEG，跳过同一媒体 ID 的 IIIF 版本。`nmah_463569` 的 Content 没有媒体条目，对象级 IIIF Manifest 提供了全尺寸 JPEG，许可链接指向 [Smithsonian Terms of Use](https://www.si.edu/termsofuse)。

下载回执记录的 JPEG SHA-256 如下。

- `nmah_446333` — `807cb6e1775ebfdd2bff62dff66ce9867cb1f10959504323b07762d997b5b3d6`
- `nmah_463569` — `288781560e78bdf526dbf6186e51f0cfe3aa3a90e7a5ad324e6b433b366c312b`
