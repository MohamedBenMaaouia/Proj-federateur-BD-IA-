# Data card: ingestion corpus

## Contents

| File | Format | Content | Language | Size |
|---|---|---|---|---|
| `manuals/2017-F-150-Owners-Manual-English.pdf` | PDF | Ford F-150 2017 owner's manual | English | 599 pages |
| `manuals/2017-F-150-Owners-Manual-French.pdf` | PDF | Ford F-150 2017 owner's manual | French | 683 pages |
| `obd_codes.json` | JSON | Generic OBD-II powertrain diagnostic trouble codes (SAE J2012) | English | 469 codes |
| `manifest.json` | JSON | Validation result: page counts, sizes, SHA-256 checksums | — | — |

## Why this corpus is representative

- **Two content types with opposite retrieval needs:** long narrative manuals, which need semantic matching, and short identifier-based records, which need exact matching. Together they exercise the full hybrid retrieval design.
- **Two languages covering the same vehicle,** which allows cross-lingual questions such as a French question answered from an English page.
- **Real-world documents:** tables, warnings, cross-references and repeated boilerplate across 1,282 pages.

## `obd_codes.json` schema

```json
{
  "source": "SAE J2012 generic powertrain diagnostic trouble codes (OBD-II)",
  "count": 469,
  "codes": [
    {"code": "P0100", "description": "Mass or Volume Air Flow Circuit Malfunction"}
  ],
  "corrections": [ ... ]
}
```

## Validation

Run `python scripts/validate_corpus.py` (requires `pypdf`). It checks:

| File type | Checks |
|---|---|
| PDF | file opens · page count · text extractable on sampled pages (not scanned images) · text in the expected language |
| JSON codes | valid JSON · declared count matches · every code matches `P` + 4 hex characters · no duplicate codes · no empty descriptions |

It writes `manifest.json`. **Current result: all checks pass.**

## Corrections applied

Validation found two typos in the source code list. Both were corrected and are recorded in the `corrections` field of `obd_codes.json`:

| Source code | Corrected to | Description | Reason |
|---|---|---|---|
| P0109 (second occurrence) | **P0110** | Intake Air Temperature Circuit Malfunction | P0110 was missing from the P0109 → P0111 sequence, and this is its SAE J2012 meaning |
| P0576 (second occurrence) | **P0577** | Cruise Control Related Malfunction | Exact duplicate; P0577 was missing from the P0575 → P0578 sequence |

## Sources and attribution

- **Owner's manuals:** © Ford Motor Company, included for academic, non-commercial use.
- **OBD-II codes:** generic SAE J2012 powertrain codes, compiled from the open-source [dtcdb](https://github.com/todrobbins/dtcdb) project and converted to JSON.
