# Smithsonian API、EDAN 记录与图片核验

[English](../en/smithsonian-api-and-media.md) · [模块架构](architecture.md) · [Swagger UI 指南](swagger-ui.md)

搜索工具以 `q` 和 `fqs` 调用 `GET /search`。元数据工具调用 `GET /content/{id}`，再核验记录是否属于同一馆藏范围。见[工具调用流程](architecture.md)。

下表列出 API 与 EDAN 数据模型的参考资料。本地 Swagger UI 使用[OpenAPI 定义](../reference/smithsonian/swagger/openapi.json)。

| 参考文档 | 说明内容 | 主要用途 |
| --- | --- | --- |
| [馆方 Open Access API 文档](https://edan.si.edu/openaccess/apidocs/) | Open Access 的内容、搜索、分类搜索、统计和术语端点 | API 操作与参数参考 |
| [馆方 EDAN JSON 格式](https://edan.si.edu/openaccess/docs/more.html) | EDAN 记录外层结构及标识、版本字段 | 记录身份与解析边界 |
| [EDAN 对象元数据模型 1.09（PDF）](https://sirismm.si.edu/siris/EDAN_IMM_OBJECT_RECORDS_1.09.pdf) | 对象元数据模型，版本 1.09，2019-12-18 | 内容字段含义及来源语义 |

## 其他 API 操作

### 术语发现

`/terms/:category` 列出允许的词类和可选 `starts_with`。它适合发现馆方词汇，再在固定军事集合内验证。文档未声明该端点接受 `q`、`fqs`、馆别范围或返回分面计数；允许类别也不包含 `set_name`。

建议先作为内部映射维护能力，不把全量术语列表注入工具 docstring。术语存在不等于在本集合内有命中，主专题有命中也不等于涵盖该冲突的全部相关记录。

### 排序、统计和记录类型

- 当前 `sort=id` 有利于稳定条件下的分页核对，但首页不是“最相关”或“核心藏品”。文档称默认排序为 relevancy，却在允许值中只列出 `id`、`newest`、`updated`、`random`；未来相关性模式应先按省略参数方式验证，不盲目加入未经验证的显式值。
- `/stats` 被描述为 CC0 对象和媒体统计，不应拿其全局数据替代 NMAH 军事范围内的搜索计数。
- `/category/:cat/search` 的三个大类不是我们自定义的 A–L taxonomy，也不是军种或冲突分类。
- `type` 与 `row_group` 用于上游记录分组。当前固定 `type:edanmdm`，不应为“功能齐全”而未经需求确认扩展到档案接口。
- 文档允许的 `rows` 范围为 0–1000；当前 MCP 限制 1–50 是客户端上下文预算的选择，不是需要修复的 API 不一致。

## EDAN JSON 的编号与外层记录

| 来源字段 | 文档含义 | 建议的用途 |
| --- | --- | --- |
| 外层 `id` | EDAN 记录标识 | API 定位，作为不透明字符串处理 |
| 外层 `url` | 仓库中的规范化名称，例如 `edanmdm:nmah_1119480` | API 定位；不能直接当作网页 URL |
| `content.descriptiveNonRepeating.record_ID` | 来源系统记录编号 | 向用户展示、记录关联 |
| `content.descriptiveNonRepeating.guid` | DOI／ARK 等标识 | 来源引用，保留原值 |
| `content.freetext.identifier` | 目录号、入藏号等带标签编号 | 保留标签，不能压成一个模糊的 ID |

当前返回 raw records，没有丢失这些字段，但客户端需要反复解析。建议在未来类型化外层中明确提供这些身份字段，并保留原始记录作为核验依据。

`lastTimeUpdated`、`docSignature`、`version` 可以支持未来缓存和变更检测，但不证明我们已经拥有可查询的历史版本。文档对 `id` 的生成方式说明也不意味着客户端应依赖其内部格式。

必须区分：API 信封中的 `status=200` 与文档描述的记录发布状态 `status=0` 不是同一种状态。不要用一个枚举同时处理它们。

## EDAN 元数据模型：三个区块的职责

| 区块 | 原文职责 | 建议处理 |
| --- | --- | --- |
| `descriptiveNonRepeating` | 标识、来源、标题、媒体与元数据权利 | 记录身份与媒体结构 |
| `indexedStructured` | 规范化检索与分面入口 | 筛选值与匹配证据 |
| `freetext` | 带标签的展示文本 | 忠实保留描述、日期、人物角色和来源语义 |

建议建立薄解析层，不要求为这三个区块分别创建工具。

### 保留标签，避免把观察改写成推断

```json
{
  "label": "associated date",
  "content": "1859"
}
```

该值不能无条件转换成 `manufacture_year=1859`。同理，人物出现在 `name` 中并不自动表示 Maker；还可能是 Sitter、Creator 或其他关联角色。结构化摘要应保留原始标签和值，不能仅保留第一条文字而丢弃其身份。

### 年代示例不是完整枚举

文档给出的 `1870s`、`1910s` 等只是示例。此前保存的 `nmah_1341785` 响应有 `indexedStructured.date=["1914-1918"]`。当前 `1770s` 至 `2000s` 是十年分面产品限制，并非完整馆方日期规范。

第一阶段可保留现有接口，并说明它不覆盖所有日期表达。扩展日期区间需验证实际搜索语义，不能根据年份字符串推断制作时间。

### Set Name 是逻辑分组

文档将 Set Name 定义为集合或逻辑分组，例子还包含展览名称。它可以限定检索范围，但不是部门组织树的权威替代品。一条记录可能属于多个集合。

`setName` 在展示内容中位于 `freetext`，而我们通过已验证的 `set_name` 搜索字段过滤。这说明 JSON 路径与 API 搜索字段不是机械的一一映射；不能声称只有 `indexedStructured` 下的值才能用于过滤。

### 媒体、元数据与物件权利分开

```text
metadata_usage
media[].usage
object_rights
```

文档区分元数据许可、每个媒体文件的使用条件和物件权利。未来不要合并成一个没有作用对象的 `is_cc0`。缺失值应保持未知，不能直接断言公开或受限。

当前 `online_media_type:Images` 表示索引为有图，不保证搜索响应含有下载 URL，也不保证图片是 CC0。

### 展出状态与出处

`onPhysicalExhibit`、`exhibition` 是展出相关字段；不能由有图推断在展，不能由缺失推断在库房。文档还明确展出信息不是完整的历史展览档案。

`creditLine`、记录级或媒体级 `preferred_citation` 和 `related_record` 值得在详情阶段保留。入藏说明不能自动等同于完整 provenance；共享编号或相关记录也不能未经核实推导完整所有权历史。

自然史的分类、地质年代和地层字段属于通用模型，当前军事项目不需要因文档列出它们就逐一建模。

## 搜索参数与响应字段

两个搜索端点均接受 JSON 数组编码成的 `fqs` 字符串。见 [API 参考](https://edan.si.edu/openaccess/apidocs/)。EDAN 文档中的占位符和 XML 必填说明需要结合真实 Open Access JSON 核对。例如部分时间戳在响应中为数字字符串，个别字段在修订记录中已移除但正文仍保留说明。

## 有图筛选与媒体核验

以下计数和单件记录核验于 **2026-11-08** 完成。

### 结论

面向“查找有图片的藏品”，Open Access API 应使用 `online_media_type:Images`。不要将官网 URL 中的 `online_visual_material:true` 原样复制到 API 并假定语义一致。

现有 `query.py` 已把工具参数 `has_images=True` 映射为 API 的 `online_media_type:Images`，本次检查确认该实现应保留。此参数表示有图索引，不保证搜索响应包含图片链接，更不保证图片为 CC0。

### 固定范围与实测数量

固定 `q=*`、`type=edanmdm`、`row_group=objects`，并在 `fqs` 中同时限定 NMAH、Armed Forces History 前缀和 `Insignias`。计数对照使用 `rows=1`；此前 Swagger 的第一页核验使用 `rows=10`。总数读取 `response.rowCount`，不以返回数组长度代替。

| API 条件（均包含固定范围） | 命中总数 | 首条记录 |
| --- | ---: | --- |
| `online_media_type:Images` | 19,962 | `nmah_463569` |
| 上述条件 + `online_visual_material:true` | 1 | `nmah_439653` |
| 上述条件 + `online_visual_material:false` | 19,961 | `nmah_463569` |
| 上述条件 + `media_usage:CC0` | 1 | `nmah_439653` |

这组结果说明：在此次范围和时间点，`online_visual_material:true` 与 CC0 筛选的唯一结果相同。没有获得官方对前者内部计算逻辑的明确说明，不能据此宣布两个字段对所有馆藏永久等价，也不能推断全部 19,961 条各自具体的限制原因。

此前 Swagger 对照中，`/search` 与 `/category/history_culture/search` 在两种有图条件下分别均返回 19,962 和 1；Images 查询第一页 10 条编号及顺序相同。没有全量遍历 19,962 条，不能声称两个接口的完整集合已逐条验证。

### nmah_463569 单件核验

藏品名称 `insignia`，细分名称 `Insignia; Navy; Ribbon, Hat`，编号 `1982.0590.01`，关联日期 1917–1918；日期是 associated date，不直接等同制造年份。Set Name 为 `Military and Society: Armed Forces History, Naval`。

| 核验 | 结果 |
| --- | --- |
| 官网搜索 `edan_q=nmah_463569` + `online_visual_material:true` | 勾选 Show only items with images，仍显示 1 条 |
| API 搜索 `q=nmah_463569`，无有图过滤 | 1 条 |
| API 加 `online_media_type:Images` | 1 条 |
| API 加 `online_visual_material:true` | 0 条 |
| API 加 `online_visual_material:false` | 1 条 |
| 官网详情 | 图片加载成功，标注 Usage Conditions Apply |
| `content/edanmdm:nmah_463569` | `indexedStructured.online_media_type` 含 Images；`descriptiveNonRepeating` 无 `online_media` |
| 对象级 IIIF Manifest | 返回 1 个 canvas，提供图片资源和图像服务 |

### 图片实际位置与许可

媒体 ID 为 `NMAH-AHB2010q67926`。官网本件图片实际加载的地址是：

<https://ids.si.edu/ids/deliveryService?id=NMAH-AHB2010q67926&max=600>

浏览器确认缩略图加载成功，实际尺寸为 600 × 450。对象级 Manifest 声明原尺寸为 3000 × 2250，并列出：

<https://ids.si.edu/ids/iiif/NMAH-AHB2010q67926/full/full/0/default.jpg>

本次读取 Manifest 并验证官网缩略图加载，没有下载和完整解码上述全尺寸 JPEG，因此 3000 × 2250 属于 Manifest 声明尺寸。

Manifest 的图片路径为 `sequences[].canvases[].images[].resource`，图像服务为该 resource 的 `service`。官网 IIIF 按钮指向媒体级 Manifest；对象级 Manifest 将藏品编号关联到同一媒体 ID。

官网图片许可为 Usage Conditions Apply，并提示重复使用受限制；Manifest 的 `license` 指向 Smithsonian Terms of Use。API 中的 `metadata_usage.access=CC0` 仅说明元数据许可，不能当作图片许可。

官方开发者说明指出，存在版权或其他限制的藏品可以提供 CC0 元数据，但不通过 Open Access 提供媒体文件。这解释了本件“官网有图、API 无媒体地址”的表现。具体限制类型未由本次记录明确，不应自行认定一定是版权问题。

### MCP 筛选与媒体处理建议

1. 保留有图开关到 `online_media_type:Images` 的映射。
2. 将有图索引、API 是否带图片 URL、IIIF 是否有公开资源、图片许可分别表示；不要合并为一个 `is_cc0` 或 `has_image` 推断。
3. 读取详情时先检查 `descriptiveNonRepeating.online_media.media`。无资源时，可查询公开的对象级 IIIF Manifest；失败或为空应保留未知/不可获取状态，不能据此说藏品没有图片。
4. 只有用户明确要求 CC0 图片时才增加 `media_usage:CC0`，并继续逐图核对许可。公开可查看不等于自由再利用。
5. IIIF 回退是可选的客户端流程。元数据工具返回馆方的原始记录。

### 可复现请求

示例从环境变量读取密钥并放在请求头；不输出密钥或包含密钥的 URL。`fqs` 为 JSON 数组字符串，HTTP 客户端负责 URL 编码。前缀条件末尾的 `*` 不转义。

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

### 证据与边界

- [本次 content 响应](../evidence/image-filter-validation-2026-11-08/nmah_463569-content.json)
- [本次对象级 Manifest](../evidence/image-filter-validation-2026-11-08/nmah_463569-manifest.json)

这两个 JSON 是实测响应的解析后格式化副本，不是原始 HTTP 字节封存，不包含完整响应头或精确请求时间。计数与官网观察来自本次工具输出的人工整理；未保存全部搜索响应及浏览器截图。结果是日期快照，不是未来数量保证。

### 官方来源

- [NMAH object page](https://americanhistory.si.edu/collections/object/nmah_463569)
- [NMAH image-only search for this record](https://americanhistory.si.edu/collections/search?edan_q=nmah_463569&edan_fq%5B%5D=online_visual_material%3Atrue)
- [Object-level IIIF Manifest](https://ids.si.edu/ids/manifest/edanmdm:nmah_463569)
- [Media-level Manifest linked by the object page](https://ids.si.edu/ids/manifest/NMAH-AHB2010q67926)
- [Official developer guidance](https://www.si.edu/openaccess/devtools)
- [Official API documentation](https://edan.si.edu/openaccess/apidocs/)
