# Sydney Traffic Volume Dataset — Data Pipeline, Exploration & Alignment

Downloads, cleans, and explores **NSW traffic volume data**, then aligns it with **road crash data** to produce a complete feature set for machine learning models.

- **Source**: [NSW Traffic Volume Counts API](https://opendata.transport.nsw.gov.au/data/dataset/nsw-roads-traffic-volume-counts-api)
- **Region**: Sydney metropolitan area
- **Years**: 2022, 2023, 2024
- **Crash data**: [NSW Road Crash Data 2020–2024](https://opendata.transport.nsw.gov.au/data/dataset/nsw-crash-data)

---

## 🔑 Before You Start: API Key Required

**`fetch_traffic_data.py` requires a NSW Open Data API key.** The embedded key may expire — you should get your own:

1. Go to https://opendata.transport.nsw.gov.au/ and register an account
2. Navigate to your account dashboard and create an API key
3. Open `fetch_traffic_data.py` and replace the value of `API_KEY` (line 19):

```python
API_KEY = "your-new-api-key-here"
```

Without a valid key, step 1 will fail with a `401` error. Steps 2 (`align_crash_data.py`) and 3 (`read_data.py`) do not require an API key, but they depend on the files generated in step 1.

---

## ⚠️ Read This First: Execution Order & Final Output

**The scripts must be run in order.** Each step depends on the previous one:

```
  fetch_traffic_data.py          download 2022/2023/2024 raw data from API
         │
         ▼
  align_crash_data.py            attach crash features for all three years
         │
         ▼
  read_data.py                   explore the final datasets
```

| Step | Script | What It Does | Input / Prerequisite | Output |
|------|--------|--------------|----------------------|--------|
| **1** | `fetch_traffic_data.py` | Downloads station metadata, hourly traffic (2022–2024), and yearly AADT from the NSW API. | API key (register at opendata.transport.nsw.gov.au) | `stations_sydney.csv`, `traffic_hourly_sydney_{2022,2023,2024}.csv`, `yearly_summary_sydney_{2022,2023,2024}.csv` |
| **2** | `align_crash_data.py` | Aligns crash data (2020–2024) to traffic data by time + space, appending 5 crash features per year. | Step 1 output + crash Excel (included in repo) | **`traffic_hourly_sydney_{2022,2023,2024}_aligned.csv`** ← **these are the files you use for modeling** |
| **3** | `read_data.py` | CLI exploration tool — inspect the aligned datasets without writing pandas. Supports `--year` flag. | Step 2 output | (read-only queries) |

### 🎯 The Final Datasets You Should Use

```
data/traffic_hourly_sydney_2022_aligned.csv
data/traffic_hourly_sydney_2023_aligned.csv
data/traffic_hourly_sydney_2024_aligned.csv
```

Three years of hourly traffic volume (14 original columns + 5 crash context columns = 19 columns each), produced after running both `fetch_traffic_data.py` and `align_crash_data.py`.

| Year | Rows | Active Stations |
|------|------|-----------------|
| 2022 | ~1,231,000 | 112 |
| 2023 | ~1,282,000 | 80 |
| 2024 | ~1,202,000 | 71 |

The raw files `traffic_hourly_sydney_{year}.csv` (14 columns, no crash features) are intermediate products — use them only if you explicitly don't want crash context.

> 💡 **Preview without running**: A 10k-row sample is included in the repo at `data/traffic_hourly_sydney_2022_aligned_sample_10k.csv` so you can inspect the schema immediately after cloning.

---

## Project Structure

```
traffic_data/
├── fetch_traffic_data.py          # ① Data download (run first)
├── align_crash_data.py            # ② Crash–traffic alignment (run second)
├── read_data.py                   # ③ Exploration & query tool (run third)
├── data/
│   ├── stations_sydney.csv                         # Station metadata (299 stations) ✓ in repo
│   ├── traffic_hourly_sydney_{year}.csv            # Intermediate: raw hourly traffic (14 cols) — generated
│   ├── traffic_hourly_sydney_{year}_aligned.csv    # ★ FINAL: traffic + crash features (19 cols) — generated
│   ├── traffic_hourly_sydney_2022_aligned_sample_10k.csv  # Sample (10k rows) for schema preview ✓ in repo
│   ├── traffic_hourly_sydney_{year}_crash_stats.csv # Crash feature distribution per year ✓ in repo
│   ├── yearly_summary_sydney_{year}.csv            # Annual summary statistics (AADT) ✓ in repo
│   ├── nsw_road_crash_data_2020-2024_crash.xlsx    # Raw crash data source ✓ in repo
│   └── crash_alignment_stats.csv                   # Crash feature alignment summary (legacy)
└── README.md
```
> ✓ in repo = committed to GitHub. "generated" = produced by running the scripts; too large for GitHub (>100 MB). `{year}` = 2022, 2023, 2024.

---

## Python Scripts

### ① `fetch_traffic_data.py` — Data Download (Run First)

**Purpose**: Downloads three categories of Sydney data (2022–2024) via the NSW Traffic Volume API, applies column curation, and saves as CSV. Runs in a loop across all three years.

**Pipeline**:

1. **Station metadata** → Queries the `road_traffic_counts_station_reference` table for permanent stations within the Sydney bounding box (lat: -34.2 to -33.4, lon: 150.5 to 151.5). Keeps only 9 curated columns. Outputs `stations_sydney.csv` (299 stations).
2. **Hourly traffic** (per year) → Queries `road_traffic_counts_hourly_permanent` for each year in batches of 10 stations. Melts the wide table (24 `hour_xx` columns) into long format and merges station spatial context (full_name, road_functional_hierarchy, lga, lat, lon). Outputs `traffic_hourly_sydney_{year}.csv`.
3. **Yearly summary** (per year) → Queries `road_traffic_counts_yearly_summary` for AADT and reliability metrics per station × direction × vehicle class. Outputs `yearly_summary_sydney_{year}.csv`.

**Usage**:

```bash
python fetch_traffic_data.py
```

> Requires a valid API key. Replace `API_KEY` on line 19. If expired, get a new key at the [NSW Open Data Portal](https://opendata.transport.nsw.gov.au).

---

### ② `align_crash_data.py` — Crash Data Alignment (Run Second)

**Purpose**: Aligns NSW road crash data (2020–2024, filtered to 2022–2024) with hourly traffic data by **time + space**, generating 5 crash-context feature columns per year. Produces the final modeling-ready files `traffic_hourly_sydney_{year}_aligned.csv`.

**Prerequisite**: The crash Excel file `nsw_road_crash_data_2020-2024_crash.xlsx` is already included in this repository (~23 MB). If missing, download it from the [NSW Open Data Portal](https://opendata.transport.nsw.gov.au).

**Why can't we align on exact dates?**
The crash dataset only provides **month + day of week + 2-hour window** — the exact calendar date is withheld for privacy protection. Therefore the alignment operates at a **statistical density** level: all dates sharing the same (station, month, day_of_week, hour) slot receive the same aggregate crash count. Crash features are aggregated across all three years (2022–2024) for maximum coverage.

**Pipeline**:

1. **Load crash data** → Reads the crash Excel file, filters to 2022–2024, maps month/weekday names to integers, expands 2-hour windows into individual hours. Computes severity scores (Fatal=5, Injury=2, Towaway=1) and total injuries.
2. **Spatial join** → For each crash, computes Haversine distance to all 299 stations. Keeps station–crash pairs within 5 km.
3. **Temporal mapping** → Maps each crash to `(station_key, month, day_of_week, hour)` tuples.
4. **Aggregation** → Groups by `(station_key, month, day_of_week, hour)` and computes 5 crash features:
   - `crash_count` — number of matching crashes
   - `crash_severity_sum` — sum of severity scores
   - `crash_injury_sum` — total persons injured or killed
   - `crash_fatal_count` — number of fatal crashes
   - `crash_wet_count` — number of wet-surface crashes
5. **Left join** (per year) → Left-joins the aggregated crash features onto each year's raw traffic table. Rows with no matching crash are zero-filled. Outputs `traffic_hourly_sydney_{year}_aligned.csv`. Also saves per-year crash feature statistics to `traffic_hourly_sydney_{year}_crash_stats.csv`.

**Usage**:

```bash
python align_crash_data.py
```

---

### ③ `read_data.py` — Data Exploration Tool (Run Third / Optional)

**Purpose**: Provides command-line interactive data queries — no need to write pandas code for quick data inspection. Defaults to 2022; use `--year` to select a different year.

**Commands**:

| Command | Description | Example |
|---------|-------------|---------|
| `python read_data.py` | Show overview of all data files (rows, cols, size) | — |
| `python read_data.py --year 2024` | Use 2024 data instead of default 2022 | — |
| `python read_data.py head` | Show first 20 rows of the traffic long table | — |
| `python read_data.py station <key>` | Station details + 24-hour volume profile | `python read_data.py station 55304` |
| `python read_data.py daily <key>` | Daily volume trend for a station | `python read_data.py daily 55304` |
| `python read_data.py holiday` | Sydney-wide: holiday vs normal volume comparison | — |
| `python read_data.py peak` | AM peak (7–9) vs PM peak (16–18) by road hierarchy | — |
| `python read_data.py lga <name>` | Filter stations by Local Government Area | `python read_data.py lga Sydney` |
| `python read_data.py road <type>` | Filter stations by road functional hierarchy | `python read_data.py road Motorway` |
| `python read_data.py crash` | Crash feature coverage statistics (requires `align_crash_data.py` first) | — |

**Typical use cases**:

- Quickly inspect a station's traffic patterns (`station` gives hourly mean/median/std + holiday comparison)
- Understand volume patterns by road class (`peak` gives a mean-volume matrix: AM peak / PM peak / off-peak × road hierarchy)
- Assess crash feature distributions (`crash` outputs nonzero ratios, distributions by hour and road class)

---

## Data Files

**Universal join key**: `station_key` (integer), present in all tables.

---

### 📄 `stations_sydney.csv` — Station Metadata

| Property | Value |
|----------|-------|
| Rows | 299 |
| Columns | 9 |
| File size | ~39 KB |

299 **permanent traffic counting stations** within the Sydney bounding box.

| Column | Type | Description | Values / Examples |
|--------|------|-------------|-------------------|
| `station_key` | int | **Primary key** — joins to all other tables | `55304` |
| `name` | str | Short station name | `"Sydney Harbour Tunnel"` |
| `full_name` | str | Full descriptor: road name + relative position | `"Sydney Harbour Tunnel, North of Cahill Expressway"` |
| `road_functional_hierarchy` | str | **Road functional class** (6 categories) | Motorway (35), Primary Road (73), Arterial Road (160), Distributor Road (19), Local Road (11), Sub-Arterial Road (1) |
| `lga` | str | **Local Government Area** — spatial unit for joining external data (weather, events, etc.) | 42 LGAs. Top 3: Hornsby (25), Sydney (23), Parramatta (19) |
| `wgs84_latitude` | float | WGS84 latitude — **spatial join key** | -34.2 to -33.4 |
| `wgs84_longitude` | float | WGS84 longitude | 150.5 to 151.5 |
| `vehicle_classifier` | int | Whether the station distinguishes light vs heavy vehicles | 0 = no (180), 1 = yes (119) |
| `device_type` | str | Sensor hardware type | Trafficorder Loop Counter (139), Tirtl (74), Trafficorder Dual Tube Classifier (40), Excel Lpl (36), Excel Ll (8), Excel Pp (2) |

---

### 📄 `traffic_hourly_sydney_{year}.csv` — Raw Hourly Traffic

| Property | 2022 | 2023 | 2024 |
|----------|------|------|------|
| Rows | ~1,231,000 | ~1,282,000 | ~1,202,000 |
| Columns | 14 | 14 | 14 |
| File size | ~175 MB | ~183 MB | ~171 MB |
| Format | **Long format** (one row = one station × one date × one hour) |
| Active stations | 112 | 80 | 71 |

#### Temporal Columns

| Column | Type | Description | Range |
|--------|------|-------------|-------|
| `date` | str | Date in ISO 8601 format | `"2022-01-01"` to `"2024-12-31"` |
| `month` | int | Month of year — captures **seasonal effects** (1 = Jan = summer, 7 = Jul = winter) | 1–12 |
| `day_of_week` | int | Day of week — captures **weekday/weekend cycles** | 1 = Monday … 7 = Sunday |
| `hour` | int | Hour of day (0–23) — captures **diurnal patterns** (AM/PM peaks, overnight troughs) | 0–23 |

#### Target Variables

| Column | Type | Description |
|--------|------|-------------|
| `volume` | float | **Hourly traffic volume (veh/h)** — primary prediction target |
| `daily_total` | int | **Daily total volume (veh/day)** — repeated across all 24 hours of the same day |

> ⚠️ `volume` is heavily right-skewed: the median is roughly half the mean. Most hours carry moderate traffic; a small number of peak hours reach very high volumes.

#### Built-in Context Labels

| Column | Type | Description | Coverage |
|--------|------|-------------|----------|
| `public_holiday` | bool | NSW **public holiday** (Christmas, Easter, Australia Day, ANZAC Day, etc.) | ~1.3% of rows (~15 days/year) |
| `school_holiday` | bool | NSW **school holiday** periods (summer Dec–Jan, autumn Apr, winter Jul, spring Sep–Oct) | ~23% of rows (~85 days/year) |

> Both can be `True` simultaneously (e.g. Christmas falls within the summer school holidays).

#### Spatial Context (denormalized from stations table)

| Column | Type | Description |
|--------|------|-------------|
| `station_key` | int | Foreign key to `stations` |
| `full_name` | str | Station full name |
| `road_functional_hierarchy` | str | Road functional class |
| `lga` | str | Local Government Area |
| `latitude` | float | WGS84 latitude |
| `longitude` | float | WGS84 longitude |

---

### 📄 `traffic_hourly_sydney_{year}_aligned.csv` — Hourly Traffic with Crash Features

Same row counts as the raw files above, with **19 columns** (14 original + 5 crash features). This is the final modeling-ready dataset.

#### Crash Context Features (Columns 15–19)

| Column | Type | Description |
|--------|------|-------------|
| `crash_count` | int | Number of crashes within 5 km in the same (month, dow, hour) window |
| `crash_severity_sum` | int | Sum of severity scores (Fatal=5, Injury=2, Towaway=1) |
| `crash_injury_sum` | int | Total persons injured or killed across all matching crashes |
| `crash_fatal_count` | int | Number of fatal crashes among the matches |
| `crash_wet_count` | int | Number of crashes that occurred on wet road surface |

> Crash features are aggregated across 2022–2024 for maximum coverage. Nonzero rates range from ~1% (fatal) to ~60% (crash_count) depending on the feature and year. See `traffic_hourly_sydney_{year}_crash_stats.csv` for per-year distributions.

**Which file to use**:
- **For modeling / downstream tasks → use `traffic_hourly_sydney_{year}_aligned.csv` (19 columns).** This is the final, complete dataset.
- Only use the raw `traffic_hourly_sydney_{year}.csv` (14 columns) if you explicitly want to exclude crash context.

---

### 📄 `yearly_summary_sydney_{year}.csv` — Annual Summary (AADT)

One row = one station × one direction × one vehicle class × one period.

#### Dimension Columns

| Column | Type | Description | Values |
|--------|------|-------------|--------|
| `station_key` | int | Foreign key to `stations` | 71–112 stations per year |
| `station_id` | str | Internal NSW road management ID | `"1003"` |
| `traffic_direction_name` | str | Direction reporting type | `PRESCRIBED` (forward), `COUNTER` (reverse), `PRESCRIBED AND COUNTER` (both) |
| `cardinal_direction_name` | str | Cardinal travel direction | `NORTH`, `SOUTH`, `EAST`, `WEST`, `BOTH` |
| `classification_type` | str | Vehicle classification | `ALL VEHICLES`, `LIGHT VEHICLES`, `HEAVY VEHICLES`, `UNCLASSIFIED` |
| `period` | str | Aggregation time window | `WEEKDAYS`, `WEEKENDS`, `AM PEAK`, `PM PEAK`, `OFF PEAK`, `PUBLIC HOLIDAYS`, `ALL DAYS` |
| `year` | int | Year | `2022`, `2023`, or `2024` |

#### Metric Columns

| Column | Type | Description | Range |
|--------|------|-------------|-------|
| `traffic_count` | int | Average traffic volume for the given dimension combination (AADT or period-specific average) | 3–139,318, median ~9,900 |
| `data_availability` | int | Percentage of days with valid data. `-1` = not assessed | -1 to 100, mean ~57% |
| `data_reliability` | int | Reliability score. `-1` = not assessed | -1 to 100 |

#### Typical Usage

- **Filter high-quality stations**: `data_availability >= 80`
- **Morning peak baseline**: `period = "AM PEAK"` + `classification_type = "ALL VEHICLES"`
- **Heavy vehicle proportion**: compare `classification_type = "HEAVY VEHICLES"` against `ALL VEHICLES`
- **Directional asymmetry**: ratio of traffic counts across different `cardinal_direction_name` values at the same station
- **Year-over-year comparison**: compare `traffic_count` for the same station + direction + period across 2022/2023/2024

---

### 📄 `traffic_hourly_sydney_{year}_crash_stats.csv` — Per-Year Crash Feature Summary

| Property | Value |
|----------|-------|
| Rows | 5 (one per crash feature) |
| Columns | 4 (`feature`, `mean`, `max`, `nonzero_pct`) |

Quick distribution overview of the 5 crash features per year, without loading the full traffic file.

---

### 📄 `nsw_road_crash_data_2020-2024_crash.xlsx` — Raw Crash Data

NSW Government road crash dataset (2020–2024). **Included in this repository** (~23 MB). If missing, download from the [NSW Open Data Portal](https://opendata.transport.nsw.gov.au). Each record includes crash time, location, severity, casualties, weather conditions, surface conditions, speed limit, and more.

---

## Crash–Traffic Alignment: Technical Details

### Why Statistical Density Alignment Instead of Exact Date Matching?

| Dataset | Temporal Resolution | Example |
|---------|---------------------|---------|
| Traffic (`traffic_hourly`) | Exact date + hour | `2022-03-15, Tuesday, 08:00` |
| Crash (`nsw_road_crash_data`) | Month + day of week + 2-hour window | `March, Tuesday, 08:00–09:59` |

The crash dataset **does not include the day of month** — a deliberate privacy-preserving measure by the data provider. Exact crash dates could be used to re-identify individuals.

Therefore we **cannot** answer:
- "Did a crash occur near station 55304 on March 15, 2022 at 8:00 AM?"

But we **can** answer:
- "On a typical Tuesday morning in March, how many crashes occur near station 55304 during the 8:00–9:59 window?"

### Alignment Logic

```
Crash Data (2022–2024)                        Traffic Data
+----------------------------+            +--------------------------------+
| month = 3 (March)           |            | month = 3                      |
| day_of_week = 2 (Tuesday)   | == match == | day_of_week = 2                |
| hours = [8, 9]              |            | hour = 8  (or hour = 9)        |
| (lat, lon)                  |            | (latitude, longitude)          |
+----------------------------+            +--------------------------------+
          |                                           |
          |   Spatial filter: Haversine(crash, station) ≤ 5 km   |
          +--------------------------------------------+
```

Crash features are aggregated across all three years (2022–2024) before being joined to each individual year's traffic data. This maximizes feature coverage by pooling crash density information.

### One-to-Many Expansion

A single crash record maps to **many** traffic rows. For example:

> One crash on *some Tuesday in March, 08:00–09:59, near station 55304*

matches traffic rows for **every Tuesday in March** at hours 8 and 9 for that station — across all three years. Thus `crash_count` measures **crash density/risk for that recurring time slot**, not a real-time "crash is happening now" flag.

### Why This Approach Is Valid

1. **Contextual signal, not event trigger** — The model benefits from knowing "how risky is this time slot for crashes" as a contextual predictor, rather than needing an exact event marker.
2. **Sparsity mitigation** — With millions of (station, date, hour) cells, exact crash dates would produce <1.4% nonzero coverage. The aggregated approach yields up to ~60% nonzero coverage.
3. **Temporal patterns are real** — Crashes cluster during peak hours, Friday evenings, and winter months. These patterns are preserved at (month, day_of_week, hour) granularity.
4. **Multi-year pooling** — Aggregating across 2022–2024 increases coverage and smooths year-to-year noise, giving more stable crash density estimates.

---

## Table Relationships

```
stations (station_key)  [299 stations]
  │
  ├── 1:N ── hourly traffic  [up to 365 × 24 = 8,760 rows per station per year]
  │             │
  │             └── left join on (station_key, month, day_of_week, hour) ── crash features
  │
  └── 1:N ── yearly_summary  [up to 28 rows per station per year: 7 periods × 4 classification types]
```

**Join key across all tables**: `station_key` (**integer type**).

---

## Built-in Feature Checklist

The following features are available directly from this dataset without any external data:

| Feature | Source Table | Purpose |
|---------|-------------|---------|
| `volume` | traffic | 🎯 Prediction target |
| `daily_total` | traffic | Daily-level target |
| `month` | traffic | Seasonal baseline |
| `day_of_week` | traffic | Weekly cycle baseline |
| `hour` | traffic | Diurnal cycle baseline |
| `public_holiday` | traffic | Public holiday indicator |
| `school_holiday` | traffic | School holiday indicator |
| `road_functional_hierarchy` | traffic / stations | Road type context |
| `lga` | traffic / stations | Spatial unit (for joining external data) |
| `latitude` / `longitude` | traffic / stations | Spatial coordinates (nearest-neighbor lookup) |
| `crash_count` | aligned | Crash density feature |
| `crash_severity_sum` | aligned | Crash severity feature |
| `crash_injury_sum` | aligned | Casualty count feature |
| `crash_fatal_count` | aligned | Fatal crash feature |
| `crash_wet_count` | aligned | Wet-surface crash feature |
| `vehicle_classifier` | stations | Vehicle-type capability flag |
| `device_type` | stations | Sensor hardware type |
| `traffic_count` (AADT) | yearly | Annual mean baseline (for normalization) |
| `data_availability` | yearly | Data quality filter |
| `classification_type` | yearly | Light vs heavy vehicle split |
| `cardinal_direction_name` | yearly | Directional analysis |

---

## Workflow Summary

```bash
# Step 1: Download raw data (requires API key)
python fetch_traffic_data.py

# Step 2: Align crash data (crash Excel already in repo)
python align_crash_data.py

# Step 3: Explore the data (default year: 2022)
python read_data.py                         # Overview
python read_data.py --year 2024             # Switch to 2024 data
python read_data.py station 55304           # Inspect a specific station
python read_data.py holiday                 # Holiday vs normal comparison
python read_data.py peak                    # AM/PM peak analysis
python read_data.py crash                   # Crash feature statistics
```
