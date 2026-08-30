# Tower Data And Rendering Notes

This note captures the current understanding of the Tower! Simulator 3 airport data layout and how the app currently turns that data into ADIRS, DBRIGHT, and STRIPS output.

It exists so the app can be reset and rebuilt from a cleaner starting point without losing the data model and rendering rules that were already recovered.

## Source Folder Shape

The original game airport data lives under:

`/mnt/e/SteamLibrary/steamapps/common/Tower! Simulator 3/Airports/<ICAO>`

Each airport folder can contain:

- `databases/<variant>/...`
- `instruments/<set>/...`
- optional airport images and assets that are not needed by the current app

Examples:

- `Airports/KLAX/databases/default/KLAX.airport`
- `Airports/KLAX/instruments/default-2.0/adirslook.csv`
- `Airports/KLAX/instruments/default-2.0/dbrightlook.csv`
- `Airports/KLAX/instruments/default-2.0/striplook.csv`

## Current App Storage Copy

The app currently keeps a trimmed subset under:

`storage/app/tower_data/<ICAO>`

Only airports with a usable default geometry file are kept:

- `storage/app/tower_data/<ICAO>/databases/default/<ICAO>.airport`

Imported files per airport:

- `databases/default/<ICAO>.airport`
- `databases/<variant>/<ICAO>.airport` when that variant has its own geometry file
- `databases/<variant>/airlines.csv`
- `databases/<variant>/airports.csv`
- `databases/<variant>/freq.csv`
- `databases/<variant>/ga.csv`
- `databases/<variant>/schedule.csv`
- `databases/<variant>/terminals.csv`
- `instruments/<set>/adirslook.csv`
- `instruments/<set>/dbrightlook.csv`
- `instruments/<set>/striplook.csv`

Not copied:

- `package.txt`
- `weatherlook.csv`
- `T3Scheduler*.txt`
- `backup/`
- `*.bak`
- images, xlsx files, assets, and similar extras

## How To Audit `tower_data`

When checking whether `storage/app/tower_data` is current enough for the app, use this baseline:

- include every source airport that has `databases/default/`
- for those airports, compare deeper `databases/*` and `instruments/*` content
- treat `weatherlook.csv` as intentionally omitted unless the app starts using weather data

The main source path is:

`/mnt/e/SteamLibrary/steamapps/common/Tower! Simulator 3/Airports`

Run this from the repo root:

```bash
python3 - <<'PY'
from pathlib import Path
from collections import defaultdict

source = Path('/mnt/e/SteamLibrary/steamapps/common/Tower! Simulator 3/Airports')
local = Path('storage/app/tower_data')

db_files_for = lambda icao: {
    f'{icao}.airport', 'airlines.csv', 'airports.csv', 'freq.csv', 'ga.csv', 'schedule.csv', 'terminals.csv'
}
instrument_files = {'adirslook.csv', 'dbrightlook.csv', 'striplook.csv', 'weatherlook.csv'}

airports = sorted([
    p.name for p in source.iterdir()
    if p.is_dir() and (p / 'databases' / 'default').is_dir()
])

missing_variants = defaultdict(list)
missing_variant_files = defaultdict(dict)
missing_sets = defaultdict(list)
missing_set_files = defaultdict(dict)

for icao in airports:
    src_airport = source / icao
    loc_airport = local / icao
    if not loc_airport.is_dir():
        print(f'missing airport root: {icao}')
        continue

    src_db_root = src_airport / 'databases'
    loc_db_root = loc_airport / 'databases'
    src_variants = sorted([p.name for p in src_db_root.iterdir() if p.is_dir()]) if src_db_root.is_dir() else []
    loc_variants = {p.name for p in loc_db_root.iterdir() if p.is_dir()} if loc_db_root.is_dir() else set()

    for variant in src_variants:
        if variant not in loc_variants:
            missing_variants[icao].append(variant)
            continue
        src_variant = src_db_root / variant
        loc_variant = loc_db_root / variant
        want = db_files_for(icao)
        missing = sorted([name for name in want if (src_variant / name).exists() and not (loc_variant / name).exists()])
        if missing:
            missing_variant_files[icao][variant] = missing

    src_inst_root = src_airport / 'instruments'
    loc_inst_root = loc_airport / 'instruments'
    if src_inst_root.is_dir():
        src_sets = sorted([p.name for p in src_inst_root.iterdir() if p.is_dir()])
        loc_sets = {p.name for p in loc_inst_root.iterdir() if p.is_dir()} if loc_inst_root.is_dir() else set()
        for set_name in src_sets:
            if set_name not in loc_sets:
                missing_sets[icao].append(set_name)
                continue
            src_set = src_inst_root / set_name
            loc_set = loc_inst_root / set_name
            missing = sorted([name for name in instrument_files if (src_set / name).exists() and not (loc_set / name).exists()])
            if missing:
                missing_set_files[icao][set_name] = missing

print('missing database variants:', dict(missing_variants))
print('missing files in database variants:', {k: v for k, v in missing_variant_files.items()})
print('missing instrument sets:', dict(missing_sets))
print('missing files in instrument sets:', {k: v for k, v in missing_set_files.items()})
PY
```

Interpretation:

- missing database variants or missing database files are real drift and should usually be copied in
- missing instrument sets are real drift and should usually be copied in
- missing `adirslook.csv`, `dbrightlook.csv`, or `striplook.csv` are real drift
- missing `weatherlook.csv` is expected with the current trimmed copy rules

## Important Domain Rule

The app currently models ADIRS, DBRIGHT, and STRIPS as separate tools, but the real game structure treats the instrument folder as a shared set.

Example:

`storage/app/tower_data/KLAX/instruments/default-2.0/`

That folder is one instrument set and contains all three files:

- `adirslook.csv`
- `dbrightlook.csv`
- `striplook.csv`

That means the better domain model is:

- airport
- database variant
- instrument set

Not:

- airport
- database variant
- ADIRS look variant
- DBRIGHT look variant
- STRIPS look variant

The current code still uses the old `look_variants` naming in each service. That is a refactor target.

## Geometry Fallback Rule

This rule was confirmed from the game data:

- use `databases/<selected-variant>/<ICAO>.airport` when present
- otherwise fall back to `databases/default/<ICAO>.airport`

This fallback is already implemented in:

- `app/Support/Tower/AdirsDataService.php`
- `app/Support/Tower/DbrightDataService.php`

Implementation detail:

- database variants are listed even if they do not contain their own `.airport`
- they are still valid as long as the airport has `databases/default/<ICAO>.airport`

## What The `.airport` File Provides

The current app uses the `.airport` file as the geometry source for ADIRS and DBRIGHT.

Important fields used:

- `icao`
- `name`
- `_centerlat`
- `_centerlon`
- `roads`
- `roads[].name`
- `roads[].type`
- `roads[].width`
- `roads[].knots`
- `roads[].knots[].pos.x`
- `roads[].knots[].pos.z`
- `roads[].knots[].name`
- `roads[].knots[].sayname`

Current assumptions in the app:

- road geometry already exists in airport-local projected coordinates (`x`, `z`)
- ADIRS and DBRIGHT render from those projected coordinates directly
- lat/lon from the airport center is only needed to project area polygons from look files into local coordinates

## What The Instrument Files Provide

### `adirslook.csv`

Used by ADIRS.

Contains:

- key/value appearance settings
- color and line thickness settings
- `Area,"... Color=..."` polygon blocks

Current parsing behavior:

- ordinary lines are split on the first comma into `key,value`
- `Area,"...` blocks are parsed as multiline polygons
- polygon coordinates are lat/lon pairs
- polygon fill color comes from `Color=r,g,b,a`

### `dbrightlook.csv`

Used by DBRIGHT.

Contains:

- general radar styling
- ring color and thickness
- airport and runway colors and thicknesses
- aircraft marker and text colors
- area polygon blocks, same style as ADIRS

Current parsing behavior is the same general shape as ADIRS:

- key/value settings
- multiline `Area,"...` blocks
- polygon colors taken from `Color=...`

### `striplook.csv`

Used by STRIPS.

Does not rely on `.airport`.

Contains:

- first CSV row with width definitions such as `Width=22%`
- later rows containing quoted multiline cell blocks
- a final `Colors` block with global palette values

Current parsing behavior:

- uses `fgetcsv` against a temp stream, not line splitting
- this is necessary because cells are multiline and quoted
- rows become arrays of strip block dictionaries
- the first row becomes `widths`
- the `Colors` block becomes the global color map

## ADIRS Rendering Notes

Current backend service:

- `app/Support/Tower/AdirsDataService.php`

Current frontend renderer:

- `resources/js/adirs-viewer.js`

### Backend payload shape

ADIRS currently returns:

- `catalog`
- `selection`
- `airport`
- `styles`
- `style_entries`
- `areas`
- `look_source.areas`
- `roads`
- `named_points`
- `stats`

### Geometry extraction

Roads:

- come from `airport.roads`
- each road becomes:
  - `name`
  - `type`
  - `width`
  - `points[]` from knot `pos.x` and `pos.z`
  - `label` at the midpoint of the point list

Named points:

- extracted from road knots with a non-empty `name`
- used as labeled point markers

Areas:

- polygons come from `adirslook.csv`
- they start as lat/lon coordinates
- backend projects them into local airport coordinates using airport center lat/lon

### Current render order

ADIRS canvas render order is:

1. clear canvas
2. fill background
3. render area polygons
4. render roads
5. render named points
6. render road labels

### Current camera behavior

ADIRS fits to the bounds of:

- all road points
- all area points
- all named points

The fit is a simple padded bounding-box fit.

Current interactions:

- drag to pan
- mouse wheel to zoom
- double-click to reset to fitted view

### Road type mapping in ADIRS

The current renderer maps road `type` to styling keys:

- `0` taxiway
- `1` terminal
- `2` runway
- `4` road area
- `5` road area

These are current app conventions, not guaranteed final game semantics.

### Label filtering in ADIRS

The current renderer suppresses labels for names that look like:

- `gate_*`
- `carroad*`
- `car_traffic*`
- `taxiway_<number>`
- `taxicar*`

All other road names can be rendered as labels when labels are enabled.

## DBRIGHT Rendering Notes

Current backend service:

- `app/Support/Tower/DbrightDataService.php`

Current frontend renderer:

- `resources/js/dbright-viewer.js`

### Backend payload shape

DBRIGHT currently returns:

- `catalog`
- `selection`
- `airport`
- `styles`
- `style_entries`
- `areas`
- `look_source.areas`
- `roads`
- `range`
- `stats`

### Geometry extraction

Roads:

- come from `airport.roads`
- only roads with at least two points are kept
- each road has:
  - `name`
  - `type`
  - `width`
  - `points[]`

Areas:

- parsed and projected the same general way as ADIRS

Range:

- calculated from maximum distance of road points from origin
- ring spacing is fixed at `8046.72` meters
- this represents 5 nautical miles in the current implementation
- ring count is `max(3, ceil(maxDistance / ringSpacing))`

### Current render order

DBRIGHT canvas render order is:

1. clear canvas
2. fill background
3. draw rings
4. draw crosshair
5. render area polygons
6. render roads
7. render center marker

### Current camera behavior

DBRIGHT fits to a symmetric circular range around the airport center:

- scale is based on `range.meters * 2`
- fit origin is the canvas center

Current interactions:

- drag to pan
- mouse wheel to zoom
- double-click to reset to fitted view

### Current DBRIGHT filters

The renderer skips roads whose name matches:

- `^carroad`

That filter was added deliberately so service/car roads are not shown in the radar display.

### Current DBRIGHT road styling

The renderer treats:

- road type `2` as runway geometry
- all other rendered roads as generic airport layout geometry

Style keys used:

- `Airport color`
- `Airport thickness`
- `Airport runway color`
- `Airport runway thickness`

### Current DBRIGHT center markers

The radar center uses:

- rings
- a crosshair
- a center dot

The center dot color currently uses `ILS color`.

## STRIPS Rendering Notes

Current backend service:

- `app/Support/Tower/StripsDataService.php`

Current frontend preview:

- `resources/js/strips-viewer.js`

This is currently an HTML preview, not a canvas renderer.

### Backend payload shape

STRIPS currently returns:

- `catalog`
- `selection`
- `layout.widths`
- `layout.rows`
- `layout.blocks`
- `layout.colors`
- `stats`

### Current preview behavior

The preview:

- renders rows using CSS grid columns from the width definitions
- renders each strip block as a card with header and body
- uses block-level colors from the file
- falls back to global colors where needed
- skips rendering `BIN` blocks in the preview

This was a deliberate UI decision for the current first pass.

## Current Reset-Relevant Lessons

If the app is rebuilt, these are the pieces worth preserving:

- airport data lives under airport folders with separate `databases` and `instruments` trees
- instrument folders are shared instrument sets, not tool-specific look variants
- ADIRS and DBRIGHT need `.airport` plus their instrument file
- STRIPS only needs `striplook.csv`
- geometry fallback is `selected database .airport` first, then `default`
- area polygons in ADIRS and DBRIGHT come from look files and must be projected from lat/lon into airport-local coordinates
- ADIRS render is a bounded fit over roads, areas, and named points
- DBRIGHT render is a center-based circular fit with 5 NM rings
- STRIPS parsing must use a real CSV reader because the file uses quoted multiline cells

## Files To Revisit Later

When rebuilding from a cleaner base, these files are the ones to revisit for recovered logic:

- `app/Support/Tower/AdirsDataService.php`
- `app/Support/Tower/DbrightDataService.php`
- `app/Support/Tower/StripsDataService.php`
- `resources/js/adirs-viewer.js`
- `resources/js/dbright-viewer.js`
- `resources/js/strips-viewer.js`
