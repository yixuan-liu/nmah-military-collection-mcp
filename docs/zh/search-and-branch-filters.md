# 检索与军种匹配

[English](../en/search-and-branch-filters.md) · [模块架构](architecture.md)

## 分类设计草案

[分类设计草案](../reference/taxonomy.json)记录了 A–L 研究分类及 Smithsonian Object Type 的候选映射，供后续分类工作参考。当前搜索工具独立构建筛选条件。

## 当前规则

`search_nmah_military_objects` 的军种筛选以 [query.py](../../src/nmah_military_collection_mcp/query.py) 为准。研究分组可以重叠，命中只说明指定字段匹配。军种、年代和有图筛选的请求路径见[工具调用流程](architecture.md)。

| 对外参数 `branch` | 独立单词匹配 | 子串匹配 |
| --- | --- | --- |
| Army | `USA`, `WAC`, `WAAC` | `Army`, `Military Academy` |
| Navy | `USN`, `U.S.N.`, `USNR` | `Navy`, `Naval Academy`, `Midshipman`, `Naval Reserve` |
| Air Force | `USAF`, `USAAF` | `Air Force`, `Army Air Forces`, `Air Corps` |
| Marine Corps | `USMC`, `U.S.M.C.`, `Marine` | `Marine Corps`, `Marines` |
| Coast Guard | `USCG`, `U.S.C.G.` | `Coast Guard` |

客户端仍须传五个标准军种名之一，例如 `branch="Navy"`；不能直接传 `branch="USNR"`。别名由服务端展开。同一军种内的别名取 OR，匹配字段为 `title` 或 `object_type`，二者也是 OR；不是对整个记录的军种识别。

## 匹配边界

匹配忽略大小写，使用显式字符类，例如 `Marine` 转为 `[Mm][Aa][Rr][Ii][Nn][Ee]`。没有依赖 API 自动进行大小写归一化。

独立单词边界是字段起止，或 ASCII 字母、数字和下划线之外的字符。实现使用下面的模式，不使用 Python 专属的词边界假设：

```python
pattern = f"(.*[^A-Za-z0-9_])?{term}([^A-Za-z0-9_].*)?"
```

这是一条明确的 ASCII 边界约定，不是语言学分词。空格、分号、括号等可以构成边界，非 ASCII 字符也被此规则视为边界。

带点缩写中的每个 `.` 转为 `[.]`，按字面句点匹配，避免正则中的点匹配任意字符。例如：

```text
[Uu][.][Ss][.][Nn][.]
```

| 输入文本 | 对应规则的预期 |
| --- | --- |
| `USNR`, `usnr`, `(USNR)`, `USNR,` | 匹配 Navy |
| `xUSNR`, `USNR1`, `USNR_` | 不因 `USNR` 命中 |
| `U.S.N.`, `(u.s.n.)` | 匹配 Navy |
| `UxSxNx`, `U.S.N.x` | 不因 `U.S.N.` 命中 |
| `Insignia; Marine; Epaulette` | 匹配 Marine Corps |
| `Submarine`, `Marine1` | 不因 `Marine` 命中 |

带点形式目前需要完整的点号，包括最后一个点；不自动删除或补齐标点。裸缩写 `USN` 与 `U.S.N.` 是分别配置的别名。

`Marines` 和其他原有完整名称继续使用子串匹配。因此，即使 `Marine` 的独立单词分支不匹配某个字符串，其他别名分支仍可能匹配；不能把单个分支的边界保证理解为整个工具的排除保证。

## 2026-11-07 别名扩展实测

实测日期：2026-11-07（America/Los_Angeles）。保存的 UTC 响应时间范围：`2026-11-08T06:53:23.631493+00:00` 至 `2026-11-08T06:53:32.022810+00:00`。这些是当时索引的快照，不是永久常量。

| 军种 | 加入前 | 加入后 | 新增 | 移除 |
| --- | ---: | ---: | ---: | ---: |
| Army | 33,671 | 33,690 | +19 | 0 |
| Navy | 6,091 | 6,095 | +4 | 0 |
| Air Force | 1,174 | 1,174 | +0 | 0 |
| Marine Corps | 1,591 | 1,593 | +2 | 0 |
| Coast Guard | 301 | 304 | +3 | 0 |

本次每个军种均执行四次请求，共 20 次：

1. 原固定范围 AND 旧军种规则，获取旧总数。
2. 原固定范围 AND 新军种规则，获取新总数。
3. 原固定范围 AND 新规则 AND NOT 旧规则，获取实际新增数。
4. 原固定范围 AND 旧规则 AND NOT 新规则，检查是否丢失旧结果。

五个军种均验证 `after - before == added - removed`，且移除数为 0。这是 API 查询层面的集合计数核验，没有下载五个军种的完整记录集。不同军种可能重叠，不能把各行新增数相加后称为跨军种去重总数。

可追溯的脱敏参数、响应时间和总数保存在 [API 对比证据](../evidence/branch-alias-counts-2026-11-07.json)。文件根据当次保存的响应提取，不是本文编写时重新调用 API 得到的结果。

### 命中样本与回归

此前已使用 Codex 保存的启动配置建立真实 stdio MCP 连接，并把返回记录与直接 API 请求比较。以下每个样本在“编号关键词 + 对应军种”查询下，旧规则命中 0 条，新 MCP 和直接 API 都命中 1 条：

| 军种 | 新增别名 | 样本编号 | 馆方字段或标题 |
| --- | --- | --- | --- |
| Army | `WAC` | `nmah_1816779` | `Alice Kono's WAC overseas cap` |
| Army | `WAAC` | `nmah_399218` | `Raincoat; Woman; Waac` |
| Navy | `U.S.N.` | `nmah_450621` | `The Late Captain Charles V. Gridley, U.S.N.` |
| Navy | `USNR` | `nmah_2040284` | `Howard Taylor Lovrien, USNR` |
| Coast Guard | `U.S.C.G.` | `nmah_450736` | `Seaman in Antarctic Parka Aboard the U.S.C.G. North Wind` |
| Marine Corps | `U.S.M.C.` | `nmah_408437` | `U.S.M.C. Knife` |

历史肩章查询返回 `nmah_1119480` 和 `nmah_1119482`，总数为 2：

```json
{
  "query": "enlisted epaulette",
  "branch": "Marine Corps",
  "date": "1850s",
  "has_images": true,
  "rows": 10,
  "offset": 0
}
```

## 历史名称消歧草案

以下映射仍待确认和实施。按完整短语和 ASCII 单词边界匹配，保留馆方名称。

| 馆方名称 | 建议检索归入 | 匹配方式 | 返回时的解释 |
| --- | --- | --- | --- |
| `Army Air Service` | Air Force | 完整短语，两端加单词边界 | 历史陆军航空机构，不声称当时属于独立空军 |
| `Revenue Cutter Service` | Coast Guard | 完整短语，两端加单词边界 | 海岸警卫队历史前身，保留原名称 |
| `Revenue Marine` | Coast Guard | 完整短语，两端加单词边界 | 保留馆方军种历史名称 |

现有 Marine Corps 规则中的独立单词 `Marine` 会命中 `Revenue Marine`。`nmah_466528` 是这一匹配的实例。拟议规则为：

```text
strong_marine_match OR (standalone_marine_match AND NOT revenue_marine_match)
```

排除只作用于弱匹配分支。同一记录如果还有 `USMC` 等明确证据，可同时进入两个研究组。第一版按记录判断，不跨字段拼接历史名称。实施后需验证已知误匹配、明确陆战队词保留，以及两件肩章记录的回归。
