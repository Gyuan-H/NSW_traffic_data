# Sydney Traffic Volume Dataset — Data Pipeline, Exploration & Alignment

Downloads, cleans, and explores **NSW traffic volume data**, then aligns it with **road crash data** to produce a complete feature set for machine learning models.

- **Source**: [NSW Traffic Volume Counts API](https://opendata.transport.nsw.gov.au)
- **Region**: Sydney metropolitan area
- **Year**: 2019
- **Crash data**: [NSW Road Crash Data 2019-2023](https://opendata.transport.nsw.gov.au)

---

## Project Structure

```
traffic_data/
├── fetch_traffic_data.py          # ① Data download
├── read_data.py                   # ② Data exploration & query tool
├── align_crash_data.py            # ③ Crash–traffic alignment
├── data/
│   ├── stations_sydney.csv                    # Station metadata (299 stations)
│   ├── traffic_hourly_sydney_2019.csv         # Raw hourly traffic (long format)
│   ├── traffic_hourly_sydney_2019_aligned.csv # Hourly traffic with crash features
│   ├── yearly_summary_sydney_2019.csv         # Annual summary statistics (AADT)
│   ├── nsw_road_crash_data_2019-2023_crash.xlsx  # Raw crash data (manual download)
│   └── crash_alignment_stats.csv              # Crash feature alignment summary
└── README.md
```

---

## Python Scripts

### ① `fetch_traffic_data.py` — Data Download

**Purpose**: Downloads three categories of Sydney 2019 data via the NSW Traffic Volume API, applies column curation, and saves as CSV.

**Pipeline**:

1. **Station metadata** → Queries the `road_traffic_counts_station_reference` table for permanent stations within the Sydney bounding box (lat: -34.2 to -33.4, lon: 150.5 to 151.5). Keeps only 9 curated columns. Outputs `stations_sydney.csv`.
2. **Hourly traffic** → Queries `road_traffic_counts_hourly_permanent` for 2019 data in batches of 10 stations. Melts the wide table (24 `hour_xx` columns) into long format and merges station spatial context (full_name, road_functional_hierarchy, lga, lat, lon). Outputs `traffic_hourly_sydney_2019.csv`.
3. **Yearly summary** → Queries `road_traffic_counts_yearly_summary` for AADT and reliability metrics per station × direction × vehicle class. Outputs `yearly_summary_sydney_2019.csv`.

**Usage**:

```bash
python fetch_traffic_data.py
```

> Requires a valid API key (embedded in the script). If expired, apply for a new one at the [NSW Open Data Portal](https://opendata.transport.nsw.gov.au).

---

### ② `read_data.py` — Data Exploration Tool

**Purpose**: Provides command-line interactive data queries — no need to write pandas code for quick data inspection.

**Commands**:

| Command | Description | Example |
|---------|-------------|---------|
| `python read_data.py` | Show overview of all data files (rows, cols, size) | — |
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

### ③ `align_crash_data.py` — Crash Data Alignment

**Purpose**: Aligns NSW road crash data with hourly traffic data by **time + space**, generating 5 crash-context feature columns.

**Why can't we align on exact dates?**
The crash dataset only provides **month + day of week + 2-hour window** — the exact calendar date is withheld for privacy protection. Therefore the alignment operates at a **statistical density** level: all dates sharing the same (station, month, day_of_week, hour) slot receive the same aggregate crash count.

**Pipeline**:

1. **Load crash data** → Reads `nsw_road_crash_data_2019-2023_crash.xlsx`, filters to 2019 (~20,355 records), maps month/weekday names to integers, expands 2-hour windows into individual hours. Computes severity scores (Fatal=5, Injury=2, Towaway=1) and total injuries.
2. **Spatial join** → For each crash, computes Haversine distance to all 299 stations. Keeps station–crash pairs within 5 km.
3. **Temporal mapping** → Maps each crash to `(station_key, month, day_of_week, hour)` tuples.
4. **Aggregation** → Groups by `(station_key, month, day_of_week, hour)` and computes 5 crash features:
   - `crash_count` — number of matching crashes
   - `crash_severity_sum` — sum of severity scores
   - `crash_injury_sum` — total persons injured or killed
   - `crash_fatal_count` — number of fatal crashes
   - `crash_wet_count` — number of wet-surface crashes
5. **Left join** → Left-joins the aggregated features onto the raw traffic table. Rows with no matching crash are zero-filled. Outputs `traffic_hourly_sydney_2019_aligned.csv`.

**Usage**:

```bash
python align_crash_data.py
```

> Requires `fetch_traffic_data.py` to have been run first, and the crash Excel file placed manually in the `data/` directory.

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

### 📄 `traffic_hourly_sydney_2019.csv` — Raw Hourly Traffic

| Property | Value |
|----------|-------|
| Rows | 2,528,481 |
| Columns | 14 |
| File size | ~360 MB |
| Format | **Long format** (one row = one station × one date × one hour) |
| Active stations | 172 (with actual 2019 data) |

#### Temporal Columns

| Column | Type | Description | Range |
|--------|------|-------------|-------|
| `date` | str | Date in ISO 8601 format | `"2019-01-01"` to `"2019-12-31"` |
| `month` | int | Month of year — captures **seasonal effects** (1 = Jan = summer, 7 = Jul = winter) | 1–12 |
| `day_of_week` | int | Day of week — captures **weekday/weekend cycles** | 1 = Monday … 7 = Sunday |
| `hour` | int | Hour of day (0–23) — captures **diurnal patterns** (AM/PM peaks, overnight troughs) | 0–23 |

#### Target Variables

| Column | Type | Description | Stats |
|--------|------|-------------|-------|
| `volume` | float | **Hourly traffic volume (veh/h)** — primary prediction target | 0–6,637, mean = 630, median = 313 |
| `daily_total` | int | **Daily total volume (veh/day)** — repeated across all 24 hours of the same day | 0–139,000+ |

> ⚠️ `volume` is heavily right-skewed: the median (313) is half the mean (630). Most hours carry moderate traffic; a small number of peak hours reach very high volumes.

#### Built-in Context Labels

| Column | Type | Description | Coverage |
|--------|------|-------------|----------|
| `public_holiday` | bool | NSW **public holiday** (Christmas, Easter, Australia Day, ANZAC Day, etc.) | True = 1.33% (~15 days/year) |
| `school_holiday` | bool | NSW **school holiday** periods (summer Dec–Jan, autumn Apr, winter Jul, spring Sep–Oct) | True = 22.7% (~85 days/year) |

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

### 📄 `traffic_hourly_sydney_2019_aligned.csv` — Hourly Traffic with Crash Features

| Property | Value |
|----------|-------|
| Rows | 2,528,481 (same as original) |
| Columns | 19 (14 original + 5 crash) |
| File size | ~384 MB |

**Identical to the 14-column raw file, with 5 crash features appended**:

| Column | Type | Description | Mean | Max | Nonzero % |
|--------|------|-------------|------|-----|-----------|
| `crash_count` | int | Number of crashes within 5 km in the same (month, dow, hour) window | 0.56 | 10 | 36.2% |
| `crash_severity_sum` | int | Sum of severity scores (Fatal=5, Injury=2, Towaway=1) | 0.97 | 17 | 36.2% |
| `crash_injury_sum` | int | Total persons injured or killed across all matching crashes | 0.47 | 13 | 27.9% |
| `crash_fatal_count` | int | Number of fatal crashes among the matches | 0.004 | 2 | 0.38% |
| `crash_wet_count` | int | Number of crashes that occurred on wet road surface | 0.065 | 4 | 5.85% |

**Which file to use**:
- If crash features are not needed → use the raw file `traffic_hourly_sydney_2019.csv` (14 columns)
- If the model benefits from crash context → use the aligned file `traffic_hourly_sydney_2019_aligned.csv` (19 columns)

---

### 📄 `yearly_summary_sydney_2019.csv` — Annual Summary (AADT)

| Property | Value |
|----------|-------|
| Rows | 4,828 |
| Columns | 10 |
| File size | ~350 KB |
| Format | One row = one station × one direction × one vehicle class × one period |

#### Dimension Columns

| Column | Type | Description | Values |
|--------|------|-------------|--------|
| `station_key` | int | Foreign key to `stations` | 172 stations |
| `station_id` | str | Internal NSW road management ID | `"1003"` |
| `traffic_direction_name` | str | Direction reporting type | `PRESCRIBED` (forward), `COUNTER` (reverse), `PRESCRIBED AND COUNTER` (both) |
| `cardinal_direction_name` | str | Cardinal travel direction | `NORTH`, `SOUTH`, `EAST`, `WEST`, `BOTH` |
| `classification_type` | str | Vehicle classification | `ALL VEHICLES`, `LIGHT VEHICLES`, `HEAVY VEHICLES`, `UNCLASSIFIED` |
| `period` | str | Aggregation time window | `WEEKDAYS`, `WEEKENDS`, `AM PEAK`, `PM PEAK`, `OFF PEAK`, `PUBLIC HOLIDAYS`, `ALL DAYS` |
| `year` | int | Year | Always `2019` |

#### Metric Columns

| Column | Type | Description | Range |
|--------|------|-------------|-------|
| `traffic_count` | int | Average traffic volume for the given dimension combination (AADT or period-specific average) | 3–139,318, median = 9,924 |
| `data_availability` | int | Percentage of days with valid data in 2019. `-1` = not assessed | -1 to 100, mean = 57% |
| `data_reliability` | int | Reliability score. `-1` = not assessed | -1 to 100 |

#### Typical Usage

- **Filter high-quality stations**: `data_availability >= 80`
- **Morning peak baseline**: `period = "AM PEAK"` + `classification_type = "ALL VEHICLES"`
- **Heavy vehicle proportion**: compare `classification_type = "HEAVY VEHICLES"` against `ALL VEHICLES`
- **Directional asymmetry**: ratio of traffic counts across different `cardinal_direction_name` values at the same station

---

### 📄 `crash_alignment_stats.csv` — Crash Feature Summary

| Property | Value |
|----------|-------|
| Rows | 5 (one per crash feature) |
| Columns | 4 (`feature`, `mean`, `max`, `nonzero_pct`) |

Quick distribution overview of the 5 crash features without loading the full traffic file.

---

### 📄 `nsw_road_crash_data_2019-2023_crash.xlsx` — Raw Crash Data

NSW Government road crash dataset (2019–2023). Must be downloaded manually from the [NSW Open Data Portal](https://opendata.transport.nsw.gov.au). Each record includes crash time, location, severity, casualties, weather conditions, surface conditions, speed limit, and more.

---

## Crash–Traffic Alignment: Technical Details

### Why Statistical Density Alignment Instead of Exact Date Matching?

| Dataset | Temporal Resolution | Example |
|---------|---------------------|---------|
| Traffic (`traffic_hourly`) | Exact date + hour | `2019-03-15, Friday, 08:00` |
| Crash (`nsw_road_crash_data`) | Month + day of week + 2-hour window | `March, Friday, 08:00–09:59` |

The crash dataset **does not include the day of month** — a deliberate privacy-preserving measure by the data provider. Exact crash dates could be used to re-identify individuals.

Therefore we **cannot** answer:
- "Did a crash occur near station 55304 on March 15, 2019 at 8:00 AM?"

But we **can** answer:
- "On a typical Friday morning in March, how many crashes occur near station 55304 during the 8:00–9:59 window?"

### Alignment Logic

```
Crash Data                                   Traffic Data
+----------------------------+            +--------------------------------+
| month = 3 (March)           |            | month = 3                      |
| day_of_week = 5 (Friday)    | == match == | day_of_week = 5                |
| hours = [8, 9]              |            | hour = 8  (or hour = 9)        |
| (lat, lon)                  |            | (latitude, longitude)          |
+----------------------------+            +--------------------------------+
          |                                           |
          |   Spatial filter: Haversine(crash, station) ≤ 5 km   |
          +--------------------------------------------+
```

### One-to-Many Expansion

A single crash record maps to **many** traffic rows. For example:

> One crash on *some Friday in March, 08:00–09:59, near station 55304*

matches traffic rows for **every Friday in March** at hours 8 and 9 for that station:

| Traffic Row | Match? |
|-------------|--------|
| 55304, 2019-03-01 (Fri), hour=8 | ✅ |
| 55304, 2019-03-01 (Fri), hour=9 | ✅ |
| 55304, 2019-03-08 (Fri), hour=8 | ✅ |
| 55304, 2019-03-08 (Fri), hour=9 | ✅ |
| … all other Fridays in March … | ✅ |
| 55304, 2019-03-06 (Wed), hour=8 | ❌ (wrong day of week) |
| 55304, 2019-04-05 (Fri), hour=8 | ❌ (wrong month) |

Thus `crash_count = 1` appears on **all Friday 8:00 and 9:00 rows in March** for station 55304, not just one specific day. The crash features therefore measure **crash density/risk for that recurring time slot**, not a real-time "crash is happening now" flag.

### Why This Approach Is Valid

1. **Contextual signal, not event trigger** — The model benefits from knowing "how risky is this time slot for crashes" as a contextual predictor, rather than needing an exact event marker.
2. **Sparsity mitigation** — 172 stations × 365 days × 24 hours = 1.5M+ cells. Even with exact dates, fewer than 1.4% of cells would have a crash — the feature would be nearly useless. The aggregated approach yields 36.2% nonzero coverage.
3. **Temporal patterns are real** — Crashes cluster during peak hours, Friday evenings, and winter months. These patterns are preserved at (month, day_of_week, hour) granularity.

---

## Table Relationships

```
stations (station_key)  [299 stations]
  │
  ├── 1:N ── hourly traffic  [up to 365 × 24 = 8,760 rows per station]
  │             │
  │             └── left join on (station_key, month, day_of_week, hour) ── crash features
  │
  └── 1:N ── yearly_summary  [up to 28 rows per station: 7 periods × 4 classification types]
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
# Step 1: Download raw data
python fetch_traffic_data.py

# Step 2 (optional): Place the crash Excel file in data/, then align
python align_crash_data.py

# Step 3: Explore the data
python read_data.py                    # Overview
python read_data.py station 55304      # Inspect a specific station
python read_data.py holiday            # Holiday vs normal comparison
python read_data.py peak               # AM/PM peak analysis
python read_data.py crash              # Crash feature statistics
```
