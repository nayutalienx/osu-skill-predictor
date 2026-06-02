# Mod Parsing Rules

Project: `osu-skill-predictor`

## Purpose

This document defines how mods should be represented consistently from raw score inputs in V1.

It answers three questions:

- which mod acronyms are explicitly supported in V1;
- how combined mod strings should be normalized and parsed;
- what should happen when unknown or unsupported mods appear.

## V1 Canonical Representation

The canonical raw mod field is:

- `mods_raw`

V1 representation rule:

- store mods as a compact uppercase acronym string with no separators

Examples:

- no mod -> `""`
- Hidden -> `HD`
- Hidden + HardRock -> `HDHR`
- DoubleTime + Hidden -> `HDDT`

Important note:

- the empty string is the canonical representation of no mod in the dataset
- `NM` may appear in external discussion or ad hoc debugging, but it should not be stored as the canonical raw dataset value

## Supported Mods for V1

### Core recognized mods

These acronyms are explicitly recognized by the V1 parser:

- `EZ`
- `HD`
- `HR`
- `DT`
- `NC`
- `HT`
- `FL`
- `NF`
- `SD`
- `PF`

### Why these were chosen

- they are common enough to matter in `osu` standard play
- several directly affect beatmap difficulty or score interpretation
- they are easy to express as compact acronym tokens

### Modeling importance in V1

Highest priority for later engineered helper features:

- `HD`
- `HR`
- `DT`
- `NC`

Medium-priority recognized but not necessarily used in the first baseline:

- `EZ`
- `HT`
- `FL`

Low-priority recognized pass-through mods:

- `NF`
- `SD`
- `PF`

## Raw Input Forms

The collector may encounter mods in several shapes before normalization:

- `null`
- empty string
- compact acronym string such as `HDHR`
- API list of acronym strings
- API list of objects containing `acronym`

V1 normalization rule:

1. if mods are missing or null, normalize to `""`
2. if mods are provided as a list, extract acronyms and concatenate them
3. uppercase the result
4. remove separators or whitespace if they appear
5. parse into recognized acronym tokens
6. rebuild the canonical compact string in canonical token order

## Combined Mod String Parsing Rules

### Tokenization

V1 mod parsing is acronym-based.

Rules:

- parse the compact string as a sequence of two-letter mod acronyms
- parsing is case-insensitive at input time
- canonical storage is uppercase
- duplicate tokens should be removed after parsing

Examples:

- `hdhr` -> `HDHR`
- `HRHD` -> parsed as `HR`, `HD`, then rebuilt canonically
- `["HD", "HR"]` -> `HDHR`
- `[{"acronym": "DT"}, {"acronym": "HD"}]` -> `HDDT`

### Canonical token order

When rebuilding a parsed mod string, use this V1 order:

1. `NF`
2. `EZ`
3. `HD`
4. `HR`
5. `DT`
6. `NC`
7. `HT`
8. `FL`
9. `SD`
10. `PF`

Examples:

- input `HRHD` -> canonical `HDHR`
- input `DTHD` -> canonical `HDDT`
- input `PFHD` -> canonical `HDPF`

### Special relationships

Some acronyms imply another gameplay effect conceptually, but V1 should preserve the explicit raw token rather than expanding it.

Rules:

- `NC` should remain `NC` in `mods_raw`; do not rewrite it to `DT`
- `PF` should remain `PF` in `mods_raw`; do not rewrite it to `SD`

However, for later helper features:

- `has_doubletime` should evaluate to true for either `DT` or `NC`
- a future sudden-death-like helper may evaluate to true for either `SD` or `PF`

### Empty and no-mod handling

Rules:

- `null`, missing, empty, or whitespace-only mod input -> `mods_raw = ""`
- do not store `NM` in the canonical dataset field

## Invalid or Conflicting Combinations

The parser should be conservative.

If a combination is structurally contradictory, such as:

- `DT` together with `HT`
- `EZ` together with `HR`

then V1 behavior should be:

- preserve the canonical raw string if it can be tokenized
- flag the row for later validation or inspection if a strict validation layer exists
- do not silently rewrite the combination into something "fixed"

Reason:

- raw collection should preserve source information where possible
- correction logic should not guess at user intent

## Unknown or Unsupported Mods

### Definition

An unknown or unsupported mod is any token that:

- is not in the V1 recognized acronym list; or
- prevents clean two-character acronym parsing

### V1 behavior

If unknown content appears:

1. preserve the raw compact string in `mods_raw` as best as possible
2. do not reject the row at raw-data collection time only because of the unknown mod
3. mark the row as unsupported for mod-derived helper features in later preprocessing logic
4. allow the rest of the row to remain usable for models that do not depend on detailed mod parsing

Practical interpretation:

- unknown mods should not destroy the row
- they should only limit what mod-engineered features can be safely derived

### Recommended future preprocessing behavior

For V1 feature engineering:

- if all tokens are recognized, derive helper flags normally
- if unknown tokens are present, either:
  - derive only the recognized safe flags and ignore unknown tokens; or
  - route the row into an `unknown_mod_present` bucket if that helper is introduced later

Do not silently drop unknown tokens from `mods_raw`.

## Relationship to Later Engineered Features

This document defines only raw mod representation and parsing rules.

It does not itself require creation of these engineered columns yet:

- `has_hidden`
- `has_hardrock`
- `has_doubletime`
- `has_flashlight`
- `has_easy`
- `has_half_time`

But these rules are designed so those helper features can be added consistently later.

## Validation Rules for `mods_raw`

For V1:

1. `mods_raw` must be non-null after normalization
2. `mods_raw` may be empty
3. canonical values should be uppercase
4. canonical values should not contain spaces, commas, or separators
5. recognized combined strings should follow canonical token order

## V1 Practical Recommendation

For the first baseline:

- keep `mods_raw` as the canonical compact raw field
- treat `""` as no mod
- recognize the ten acronyms listed above
- normalize combined mod strings into canonical order
- preserve unknown mod content rather than throwing away the row

This keeps mod handling simple, explicit, and compatible with the current collector and future feature engineering.
