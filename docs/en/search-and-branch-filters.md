# Search and branch filters

[中文版](../zh/search-and-branch-filters.md) · [Architecture](architecture.md)

## Classification design draft

The [taxonomy draft](../reference/taxonomy.json) records the proposed A–L research categories and candidate mappings from Smithsonian Object Type values. It is reference material for future classification work. The current search tool builds its filters independently of this draft.

## Current behavior

Pass one of the five branch values to `search_nmah_military_objects`. The server expands aliases and matches them case-insensitively against `title` or `object_type`. These are overlapping research groups. See [query.py](../../src/nmah_military_collection_mcp/query.py).

| Branch | Standalone aliases | Substring aliases |
| --- | --- | --- |
| Army | `USA`, `WAC`, `WAAC` | `Army`, `Military Academy` |
| Navy | `USN`, `U.S.N.`, `USNR` | `Navy`, `Naval Academy`, `Midshipman`, `Naval Reserve` |
| Air Force | `USAF`, `USAAF` | `Air Force`, `Army Air Forces`, `Air Corps` |
| Marine Corps | `USMC`, `U.S.M.C.`, `Marine` | `Marine Corps`, `Marines` |
| Coast Guard | `USCG`, `U.S.C.G.` | `Coast Guard` |

Standalone matches use field edges or characters outside ASCII letters, digits, and underscores as boundaries. Periods in initialisms are literal, including the final period. `Marine` matches `Insignia; Marine; Epaulette`, while the same alias fails to match `Submarine`. Other aliases can independently match the record.

## Alias expansion measured on 2026-11-07

The comparison added `U.S.N.`, `USNR`, `U.S.C.G.`, `U.S.M.C.`, `WAC`, and `WAAC`. The baseline already included standalone `Marine`. All 20 requests used the fixed collection scope with no date or image constraint. The figures are historical index counts. See the [request evidence](../evidence/branch-alias-counts-2026-11-07.json).

| Branch | Before | After | Added | Removed |
| --- | ---: | ---: | ---: | ---: |
| Army | 33,671 | 33,690 | 19 | 0 |
| Navy | 6,091 | 6,095 | 4 | 0 |
| Air Force | 1,174 | 1,174 | 0 | 0 |
| Marine Corps | 1,591 | 1,593 | 2 | 0 |
| Coast Guard | 301 | 304 | 3 | 0 |

Individual positive samples were `nmah_1816779` (WAC), `nmah_399218` (WAAC), `nmah_450621` (U.S.N.), `nmah_2040284` (USNR), `nmah_450736` (U.S.C.G.), and `nmah_408437` (U.S.M.C.). The historical enlisted epaulette query returned `nmah_1119480` and `nmah_1119482`. See the [Chinese guide](../zh/search-and-branch-filters.md) for the replay input and set-count method.

## Historical-name proposal

The proposed phrase mappings are Army Air Service to Air Force and Revenue Cutter Service and Revenue Marine to Coast Guard. These mappings remain pending. Preserve the source name and the distinction between a predecessor and a modern branch.

Standalone `Marine` currently matches `Revenue Marine`, as observed in `nmah_466528`. The proposed rule suppresses that weak alias when the conflicting phrase appears. Strong terms such as `USMC` still match independently. Verification would cover the known false match, retained strong matches, and the two epaulette records.
