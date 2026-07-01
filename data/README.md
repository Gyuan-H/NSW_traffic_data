# NSW Traffic Volume Dataset -- Feature Reference

Benchmark data for the **Weather, Events, and Urban Context Benchmark** project.

- **Source**: [NSW Traffic Volume Counts API](https://opendata.transport.nsw.gov.au)
- **Region**: Sydney metropolitan area
- **Year**: 2019
- **Download script**: `fetch_traffic_data.py`
- **Exploration script**: `read_data.py`
- **Crash alignment script**: `align_crash_data.py`

---

## Output Files

| File | Rows | Cols | Size | Description |
|------|------|------|------|-------------|
| `stations_sydney.csv` | 299 | 9 | ~0.04 MB | Permanent traffic station metadata |
| `traffic_hourly_sydney_2019.csv` | 2,528,481 | 14 | ~360 MB | Hourly traffic volumes -- original, no crash features |
| `traffic_hourly_sydney_2019_aligned.csv` | 2,528,481 | 19 | ~384 MB | Hourly traffic volumes -- with 5 crash context features appended |
| `yearly_summary_sydney_2019.csv` | 4,828 | 10 | ~0.3 MB | Annual aggregated statistics (AADT) |
| `nsw_road_crash_data_2019-2023_crash.xlsx` | -- | -- | -- | Raw crash data (source, not produced by fetch script) |
| `crash_alignment_stats.csv` | 5 | 4 | <0.01 MB | Summary statistics for the 5 crash features |
| `osm_pois_sydney.csv` | varies | 8 | ~1-3 MB | Points of Interest from OpenStreetMap (see Section 5) |
| `osm_landuse_sydney.csv` | varies | 9 | ~2-5 MB | Land use polygons from OpenStreetMap (see Section 5) |
| `osm_lga_boundaries_sydney.csv` | varies | 7 | ~0.2 MB | LGA boundary polygons for spatial join (see Section 5) |
| `osm_lga_summary_sydney.csv` | varies | varies | ~0.05 MB | LGA-level POI counts + land use composition (see Section 5) |

**Join key**: `station_key` (int) -- present in all tables.

**Two traffic files**: The `_aligned` file is a superset: it contains all 14 columns from the original file plus 5 crash-derived features. The original file is kept unchanged so that crash-free analyses can be run without extra filtering.

---

## 1. `stations_sydney.csv` -- Station Metadata

299 permanent traffic counting stations within the Sydney bounding box
(lat: -34.2 to -33.4, lon: 150.5 to 151.5).

### Columns

| Column | Type | Description | Example / Values |
|--------|------|-------------|------------------|
| `station_key` | int | **Primary key**. Join to the other tables. | `55304` |
| `name` | str | Short station name. | `"Sydney Harbour Tunnel"` |
| `full_name` | str | Full descriptor: road name + relative position. Useful as natural-language context in T5 scenario cards. | `"Sydney Harbour Tunnel, North of Cahill Expressway"` |
| `road_functional_hierarchy` | str | **Road functional class** -- a core spatial feature for benchmark tasks. | 6 values: `Motorway` (35), `Primary Road` (73), `Arterial Road` (160), `Distributor Road` (19), `Local Road` (11), `Sub-Arterial Road` (1) |
| `lga` | str | **Local Government Area** -- the recommended spatial unit for joining external data (weather stations, crash locations, events). | 42 LGAs. Top: Hornsby (25), Sydney (23), Parramatta (19) |
| `wgs84_latitude` | float | WGS84 latitude. **Spatial join key** for nearest weather station lookup. | -34.2 to -33.4 |
| `wgs84_longitude` | float | WGS84 longitude. | 150.5 to 151.5 |
| `vehicle_classifier` | int | Whether the station can distinguish vehicle types (light vs heavy). | `0` = no (180 stations), `1` = yes (119 stations) |
| `device_type` | str | Sensor hardware type. Relevant for data quality assessment. | 6 types: `Trafficorder Loop Counter` (139), `Tirtl` (74), `Trafficorder Dual Tube Classifier` (40), `Excel Lpl` (36), `Excel Ll` (8), `Excel Pp` (2) |

---

## 2. `traffic_hourly_sydney_2019.csv` -- Hourly Traffic Volumes (Original)

**Long format**: one row = one station x one date x one hour.

172 stations with actual 2019 data.

### Time Columns

| Column | Type | Description | Range |
|--------|------|-------------|-------|
| `date` | str | Date in UTC+0 (ISO 8601). | `"2019-01-01"` to `"2019-12-31"` |
| `month` | int | Month of year. Captures **seasonal effects** (1 = Jan = Australian summer, 7 = Jul = winter). | 1-12 |
| `day_of_week` | int | Day of week. Captures **weekday/weekend cycles**. | 1 = Monday ... 7 = Sunday |
| `hour` | int | Hour of day (0-23). Captures **diurnal patterns** (AM peak, PM peak, off-peak, overnight). | 0-23 |

### Target Variables

| Column | Type | Description | Stats |
|--------|------|-------------|-------|
| `volume` | float | **Hourly traffic volume** (veh/h). The primary prediction target for benchmark tasks T1-T5. | 0 ~ 6,637, mean = 630, median = 313 |
| `daily_total` | int | **Daily total volume** (veh/day). Repeated across all 24 hours of the same day. | 0 ~ 139,000+ |

> **Distribution note**: `volume` is right-skewed. The median (313) is half the mean (630), meaning most hours have moderate traffic while a small number of peak hours reach very high volumes.

### Built-in Context Labels

| Column | Type | Description | Coverage |
|--------|------|-------------|----------|
| `public_holiday` | bool | **NSW public holiday**. Includes Christmas, Easter, Australia Day, ANZAC Day, etc. | `True` = 1.33% (~15 days/year) |
| `school_holiday` | bool | **NSW school holiday period**. Covers summer break (Dec-Jan), autumn break (Apr), winter break (Jul), spring break (Sep-Oct). | `True` = 22.7% (~85 days/year) |

> Both can be `True` simultaneously (e.g. Christmas falls during summer school holidays).

### Spatial Context (denormalized from stations table)

| Column | Type | Description |
|--------|------|-------------|
| `station_key` | int | Foreign key to `stations`. |
| `full_name` | str | Station full name. |
| `road_functional_hierarchy` | str | Road functional class (6 categories). |
| `lga` | str | Local Government Area. |
| `latitude` | float | WGS84 latitude (renamed from `wgs84_latitude`). |
| `longitude` | float | WGS84 longitude (renamed from `wgs84_longitude`). |

---

## 3. `traffic_hourly_sydney_2019_aligned.csv` -- Hourly Traffic + Crash Context

**Same 2,528,481 rows as the original traffic file**, with 5 additional crash-derived columns appended.

Same schema as Section 2, plus:

### Crash Context Features (Columns 15-19)

| Column | Type | Description | Mean | Max | Nonzero % |
|--------|------|-------------|------|-----|-----------|
| `crash_count` | int | Number of crashes within 5 km that occurred on the same (month, day_of_week, hour). | 0.56 | 10 | 36.2% |
| `crash_severity_sum` | int | Sum of severity scores: Fatal=5, Injury=2, Towaway=1. | 0.97 | 17 | 36.2% |
| `crash_injury_sum` | int | Total persons injured/killed across all matching crashes. | 0.47 | 13 | 27.9% |
| `crash_fatal_count` | int | Number of fatal crashes among the matching crashes. | 0.004 | 2 | 0.38% |
| `crash_wet_count` | int | Number of crashes that occurred on wet road surface. | 0.065 | 4 | 5.85% |

> **Benchmark role**: These features serve as **contextual signals** for tasks T2 (anomaly detection) and T3 (causal attribution). A traffic volume deviation that coincides with nearby crash activity may be explained by crash-induced disruption rather than being a genuine demand anomaly. The severity-weighted and injury-based features distinguish minor incidents from serious ones that cause major disruptions.

---

## 4. `yearly_summary_sydney_2019.csv` -- Annual Summary (AADT)

One row = one station x one direction x one vehicle class x one time period.

### Dimension Columns

| Column | Type | Description | Values |
|--------|------|-------------|--------|
| `station_key` | int | Foreign key to `stations`. | 172 stations |
| `station_id` | str | Internal NSW road management ID. | e.g. `"1003"` |
| `traffic_direction_name` | str | Direction reporting type. | `PRESCRIBED` (single direction), `COUNTER` (reverse), `PRESCRIBED AND COUNTER` (both directions) |
| `cardinal_direction_name` | str | Cardinal travel direction. | `NORTH`, `SOUTH`, `EAST`, `WEST`, `BOTH` |
| `classification_type` | str | Vehicle classification. `UNCLASSIFIED` = no breakdown available. | `ALL VEHICLES`, `LIGHT VEHICLES`, `HEAVY VEHICLES`, `UNCLASSIFIED` |
| `period` | str | Aggregation time window. | `WEEKDAYS`, `WEEKENDS`, `AM PEAK`, `PM PEAK`, `OFF PEAK`, `PUBLIC HOLIDAYS`, `ALL DAYS` |
| `year` | int | Year. | Always `2019` |

### Metric Columns

| Column | Type | Description | Range |
|--------|------|-------------|-------|
| `traffic_count` | int | Average traffic volume for the given dimension combination (AADT or period-specific average). | 3 ~ 139,318, median = 9,924 |
| `data_availability` | int | **Percentage of days with valid data** in 2019. `-1` = not assessed. | -1 to 100, mean = 57% |
| `data_reliability` | int | **Reliability score**. Higher = more trustworthy. `-1` = not assessed. | -1 to 100 |

### Benchmark Usage

- **`data_availability >= 80`** -> filter to high-quality stations only.
- **`period = "AM PEAK"`** + **`classification_type = "ALL VEHICLES"`** -> morning peak baseline for T2 anomaly detection.
- **`classification_type = "HEAVY VEHICLES"`** -> heavy vehicle proportion, useful as a T5 scenario-card variable.
- **`cardinal_direction_name`** -> directional asymmetry (inbound vs outbound), useful for T3 causal contrast.

---

## 5. OSM Data — Points of Interest & Land Use

OpenStreetMap data for the Sydney metropolitan area, downloaded via the Overpass API.  
**Download script**: `fetch_osm_data.py`  
**Exploration script**: `read_osm_data.py`

### 5.1 `osm_pois_sydney.csv` — Points of Interest

Individual POI points with coordinates. Usable for proximity-based joins to traffic stations.

| Column | Type | Description |
|--------|------|-------------|
| `osm_id` | int | OpenStreetMap node ID |
| `name` | str | POI name (may be empty for unnamed features) |
| `name_en` | str | English name (if different from name) |
| `category_key` | str | High-level category slug (see table below) |
| `category_label` | str | Chinese category label |
| `osm_tag` | str | Primary OSM tag (e.g. `amenity=school`) |
| `latitude` | float | WGS84 latitude |
| `longitude` | float | WGS84 longitude |
| `lga` | str | LGA assigned via point-in-polygon spatial join |

**POI Categories** (9 groups):

| Category Key | Label | Example OSM Tags |
|-------------|-------|-----------------|
| `transport` | 交通枢纽 | railway=station, amenity=bus_station, aeroway=aerodrome |
| `education` | 教育机构 | amenity=school, amenity=university, amenity=library |
| `healthcare` | 医疗服务 | amenity=hospital, amenity=clinic, amenity=pharmacy |
| `shopping` | 购物消费 | shop=mall, shop=supermarket, amenity=marketplace |
| `food_drink` | 餐饮娱乐 | amenity=restaurant, amenity=cafe, amenity=bar |
| `leisure_culture` | 文体休闲 | leisure=stadium, amenity=theatre, tourism=museum |
| `public_service` | 公共服务 | amenity=police, amenity=post_office, amenity=place_of_worship |
| `accommodation` | 住宿 | tourism=hotel, tourism=motel |
| `office` | 办公商业 | office=corporate, building=commercial |

**Benchmark Usage**:
- **Proximity join**: For each traffic station, count POIs within 500m / 1km / 2km buffers. POI density around a station is a proxy for "trip attractor density" — stations near schools, malls, or hospitals will have different traffic patterns.
- **T5 scenario cards**: "This motorway station is near 3 schools and a shopping centre" — adds urban context to scenario descriptions.
- **Event proxies**: Stadiums and theatres near a station suggest event-day traffic surges.

### 5.2 `osm_landuse_sydney.csv` — Land Use Polygons

Land use areas as polygon centroids with area estimates.

| Column | Type | Description |
|--------|------|-------------|
| `osm_id` | int | OSM way or relation ID |
| `osm_type` | str | `way` or `relation` |
| `name` | str | Area name (e.g. "Centennial Park") |
| `class_key` | str | Land use class slug (e.g. `residential`, `park`) |
| `class_label` | str | Chinese class label |
| `centroid_lat` | float | Polygon centroid latitude |
| `centroid_lon` | float | Polygon centroid longitude |
| `area_km2` | float | Polygon area in km² (Shoelace formula, lat-corrected) |
| `num_vertices` | int | Number of vertices in the polygon |
| `tags_json` | str | Additional OSM tags as JSON |
| `lga` | str | LGA assigned via centroid point-in-polygon |

**Land Use Classes**:

| Class | Label | Typical Traffic Implication |
|-------|-------|---------------------------|
| `residential` | 住宅 | Morning outbound + evening inbound peaks |
| `commercial` | 商业 | All-day steady traffic, weekday peaks |
| `retail` | 零售 | Weekend peaks, midday traffic |
| `industrial` | 工业 | Heavy vehicle proportion, off-peak activity |
| `park` | 公园 | Weekend leisure traffic |
| `nature_reserve` | 自然保护区 | Low baseline traffic, tourism spikes |
| `construction` | 在建 | Temporary traffic disruption |
| `farmland` | 农田 | Very low traffic, seasonal variation |
| `port` | 港口 | Heavy vehicle traffic, freight corridors |
| `railway` | 铁路用地 | Rail corridor, may depress road volume |
| `education` | 教育用地 | School-hour peaks (8-9 AM, 3-4 PM) |

### 5.3 `osm_lga_boundaries_sydney.csv` — LGA Boundaries

Boundary polygons for NSW Local Government Areas (OSM admin_level=6).

| Column | Type | Description |
|--------|------|-------------|
| `osm_id` | int | OSM relation ID |
| `lga_name` | str | LGA name (matches stations.lga) |
| `centroid_lat` | float | LGA centroid latitude |
| `centroid_lon` | float | LGA centroid longitude |
| `area_km2` | float | LGA area in km² |
| `num_vertices` | int | Number of boundary vertices |
| `polygon_json` | str | Full polygon as JSON array of [lat, lon] pairs |

Used internally for the POI-to-LGA and landuse-to-LGA spatial joins. Can also be used for custom spatial operations.

### 5.4 `osm_lga_summary_sydney.csv` — LGA-Level Summary

Aggregated statistics per LGA — the recommended join target for the traffic data.

**Core Columns**:

| Column | Type | Description |
|--------|------|-------------|
| `lga` | str | LGA name (**join key** to `stations.lga` and `traffic_hourly.lga`) |
| `poi_total` | int | Total POI count in this LGA |
| `poi_transport` | int | Transport-related POIs |
| `poi_education` | int | Education-related POIs |
| `poi_healthcare` | int | Healthcare POIs |
| `poi_shopping` | int | Shopping POIs |
| `poi_food_drink` | int | Food & drink POIs |
| `poi_leisure_culture` | int | Leisure & culture POIs |
| `poi_public_service` | int | Public service POIs |
| `poi_accommodation` | int | Accommodation POIs |
| `poi_office` | int | Office POIs |
| `landuse_total_area_km2` | float | Total mapped land use area |
| `lu_residential_km2` / `_pct` | float / float | Residential area and percentage |
| `lu_commercial_km2` / `_pct` | float / float | Commercial area and percentage |
| `lu_industrial_km2` / `_pct` | float / float | Industrial area and percentage |
| `lu_retail_km2` / `_pct` | float / float | Retail area and percentage |
| `lu_park_km2` / `_pct` | float / float | Park/green space area and percentage |
| ... (additional land use classes) | | |
| `lga_centroid_lat` | float | LGA centroid latitude |
| `lga_centroid_lon` | float | LGA centroid longitude |

**Join to Traffic Data**:

```python
# One-line LGA-level context join
traffic = pd.read_csv("data/traffic_hourly_sydney_2019.csv")
lga_osm = pd.read_csv("data/osm_lga_summary_sydney.csv")
traffic_enriched = traffic.merge(lga_osm, on="lga", how="left")
```

**Benchmark Usage**:
- **T1 (prediction)**: Add POI density and land use proportions as conditioning variables — a station in a residential LGA with many schools will have different diurnal patterns than one in an industrial LGA.
- **T2 (anomaly detection)**: Normalize anomalies by land use context — a volume spike in an industrial area at 2 AM is less anomalous than the same spike in a residential area.
- **T5 (scenario cards)**: Generate rich scenario descriptions — "Station 55304 is in Sydney LGA, a predominantly commercial area (45% commercial, 20% park) with 156 restaurants and 12 schools within the LGA."
- **Cross-LGA analysis**: Compare traffic patterns across LGAs with different land use compositions.

### 5.5 Data Completeness Notes

- **OSM coverage**: OpenStreetMap is volunteer-contributed. Urban areas (Sydney CBD, Parramatta) have near-complete POI coverage; outer suburbs may have sparser data.
- **Land use mapping**: Not all land parcels are tagged in OSM. The `landuse_total_area_km2` per LGA will be less than the actual LGA area because roads, water bodies, and un-tagged areas are excluded.
- **LGA matching**: OSM LGA names may differ slightly from the Transport NSW names. Run `read_osm_data.py` to check the match rate.
- **Polygon simplification**: Full polygon geometries are stored as JSON arrays in `osm_lga_boundaries_sydney.csv`. For use with `shapely` or `geopandas`, parse `polygon_json` into `shapely.geometry.Polygon` objects.

---

## Crash-Traffic Alignment: Methodology and Rationale

The alignment between NSW Crash Data and hourly traffic data is **not a precise date-level join** -- it is a **statistical density join** at coarser temporal granularity. This section explains why this approach is necessary and why it is valid for our benchmark.

### The Data Asymmetry Problem

The two datasets have **mismatched temporal precision**:

| Dataset | Temporal Resolution | Example |
|---------|-------------------|---------|
| Traffic (`traffic_hourly`) | Exact date + hour | `2019-03-15, Friday, 08:00` |
| Crash (`nsw_road_crash_data`) | Month + day of week + 2-hour window | `March, Friday, 08:00-09:59` |

The crash dataset records **month**, **day of week**, and **two-hour interval** -- but **not** the specific calendar date (day of month). This is a deliberate privacy-preserving choice by the data provider: exact crash dates could be used to re-identify individuals involved in crashes.

Because of this, we **cannot** answer questions like:
- "Did a crash occur near station 55304 on March 15, 2019 at 8:00 AM?"

But we **can** answer:
- "On a typical Friday morning in March, how many crashes occur near station 55304 during the 8:00-9:59 window?"

### The Alignment Mechanism

The join operates on three shared dimensions:

```
Crash Data                                    Traffic Data
+----------------------------+               +--------------------------------+
| month = 3 (March)          |               | month = 3                      |
| day_of_week = 5 (Friday)   | === match === | day_of_week = 5                |
| hours = [8, 9]             |               | hour = 8  (or hour = 9)        |
| (lat, lon)                 |               | (latitude, longitude)          |
+----------------------------+               +--------------------------------+
          |                                                |
          |         Spatial filter:                        |
          |    haversine(crash, station) <= 5 km           |
          +-----------------------------------------------+
```

**Step by step** (implemented in `align_crash_data.py`):

1. **Temporal mapping**: Each crash's `Two-hour intervals` field (e.g. `"08:00 - 09:59"`) is expanded into its constituent hours `[8, 9]`. Month names are mapped to integers (January -> 1). Day-of-week names are mapped to integers (Monday -> 1).

2. **Spatial join**: For each crash, compute the Haversine distance to all 299 traffic stations. Keep only station-crash pairs where distance <= 5 km. This is vectorized for efficiency.

3. **Temporal join**: The crash row is expanded to one row per matching hour per nearby station: `(station_key, month, day_of_week, hour)`.

4. **Aggregation**: Crash features are aggregated by `groupby(["station_key", "month", "day_of_week", "hour"])`:
   - `crash_count` = number of crashes matching this (station, month, dow, hour)
   - `crash_severity_sum` = sum of severity scores (Fatal=5, Injury=2, Towaway=1)
   - `crash_injury_sum` = total persons injured or killed
   - `crash_fatal_count` = count of fatal crashes
   - `crash_wet_count` = count of crashes on wet road surface

5. **Left-join to traffic**: The aggregated crash features are left-joined onto the traffic table on `(station_key, month, day_of_week, hour)`. Rows with no matching crashes get zero-filled.

### Implications of the "One-to-Many" Join

A single crash record maps to **many** traffic rows. For example:

> One crash on *any Friday in March, 8:00-9:59 AM, near station 55304*

will match traffic rows for **every Friday in March** at hours 8 and 9 for station 55304:

| Traffic Row | Matches? |
|-------------|----------|
| 55304, 2019-03-01 (Fri), hour=8 | Yes |
| 55304, 2019-03-01 (Fri), hour=9 | Yes |
| 55304, 2019-03-08 (Fri), hour=8 | Yes |
| 55304, 2019-03-08 (Fri), hour=9 | Yes |
| 55304, 2019-03-15 (Fri), hour=8 | Yes |
| 55304, 2019-03-15 (Fri), hour=9 | Yes |
| 55304, 2019-03-22 (Fri), hour=8 | Yes |
| 55304, 2019-03-22 (Fri), hour=9 | Yes |
| ... all other Fridays in March ... | Yes |
| 55304, 2019-03-06 (Wed), hour=8 | No (wrong day_of_week) |
| 55304, 2019-04-05 (Fri), hour=8 | No (wrong month) |

This means `crash_count = 1` for this crash will appear on **all** Friday-8AM and Friday-9AM rows in March for station 55304 -- not just one specific day. The feature therefore measures **crash density/risk for that recurring time slot**, not a binary "crash happened right now" flag.

### Why This Is Valid for the Benchmark

This alignment strategy is **conceptually correct** for our benchmark's use case for three reasons:

**1. Crash features are contextual signals, not event triggers.** The benchmark uses crash data to answer questions like: "Is this traffic anomaly explained by nearby crash activity?" and "How does crash density correlate with traffic volume deviations?" For these questions, knowing the *typical crash density* for a given (station, month, weekday, hour) is actually more informative than knowing whether a crash happened at that exact moment -- because crash-induced traffic disruption can persist for hours and affect multiple days with similar temporal patterns.

**2. Direct event-level matching would be too sparse.** In 2019, there were approximately 20,355 crashes in NSW. Even if every crash had an exact timestamp, the probability of a crash landing on any specific (station, date, hour) cell is extremely low. With 172 stations x 365 days x 24 hours = 1,506,720 possible cells, fewer than 1.4% of traffic rows would have a crash event -- making the feature nearly useless as a predictor. The aggregated approach gives 36.2% nonzero coverage, providing meaningful signal.

**3. Temporal patterns are real and informative.** Crashes are not uniformly distributed across time. They cluster during peak hours, on certain weekdays, and in certain months (e.g., more crashes in winter during reduced visibility, more on Friday evenings). Capturing this pattern at the (month, day_of_week, hour) granularity preserves these meaningful temporal variations while sacrificing only the exact-date specificity -- which is not recoverable from the data anyway.

### What This Alignment Can and Cannot Support

| Benchmark Task | Supported? | Rationale |
|---------------|------------|-----------|
| T1 (context-conditioned prediction) | Yes | Crash density is a valid conditioning variable |
| T2 (anomaly detection) | Yes | Elevated crash density can explain volume deviations |
| T3 (causal attribution) | Yes | Contrast high-crash vs low-crash time slots |
| T4 (counterfactual) | Yes | "What if crash density were lower in this time slot?" |
| T5 (scenario cards) | Yes | Crash risk level is meaningful scenario context |
| Precise event studies ("did the March 15 crash cause the 8:15 spike?") | No | Requires exact crash date, which the source data does not provide |
| Real-time crash detection | No | This is a historical benchmark dataset, not a live system |

### Coverage Summary

| Metric | Value |
|--------|-------|
| Crashes in 2019 (with valid time/location) | ~20,355 |
| Crash-station pairs (within 5 km) | 346,224 |
| Unique (station, month, dow, hour) combinations with >=1 crash | 222,662 |
| Traffic rows with >=1 crash match (`crash_count > 0`) | 36.2% |
| Traffic rows with >=1 fatal crash | 0.38% |
| Traffic rows with >=1 wet-surface crash | 5.85% |

---

## Table Relationships

```
stations (station_key)
  |
  +-- 1:N -- traffic_hourly   (each station has ~365 x 24 = 8,760 rows for a full year)
  |            |
  |            +-- left-join on (station_key, month, day_of_week, hour) -- crash_aggregated
  |
  +-- 1:N -- yearly_summary   (each station has up to 28 rows: 7 periods x 4 classification types)
```

`station_key` is the sole join key -- it is an **integer**, not a string.

---

## Features Available Without External Data

These are ready to use directly from the API download:

| Feature | Source Table | Benchmark Role |
|---------|-------------|----------------|
| `volume` (hourly traffic) | traffic | Prediction target (T1-T5) |
| `daily_total` | traffic | Daily-level target |
| `month` | traffic | Seasonal baseline |
| `day_of_week` | traffic | Weekly cycle baseline |
| `hour` | traffic | Diurnal cycle baseline |
| `public_holiday` | traffic | Holiday context label (gold) |
| `school_holiday` | traffic | School term context label (gold) |
| `road_functional_hierarchy` | both | Road type context |
| `lga` | both | Spatial unit for joins |
| `latitude` / `longitude` | both | Spatial join key |
| `vehicle_classifier` | stations | Vehicle-type capability flag |
| `traffic_count` (AADT) | yearly | Normalization baseline |
| `data_availability` | yearly | Quality filter |
| `classification_type` | yearly | Light vs heavy vehicle split |

## Features Requiring External Data

| Feature | Source | Join Method | Status |
|---------|--------|-------------|--------|
| Crash incidents | NSW Crash Data (XLSX) | Proximity (5 km Haversine) + temporal (month x day_of_week x hour) | Done -- see aligned file |
| Weather (temperature, rainfall, visibility) | BOM / Open-Meteo | Nearest station by lat/lon + hour | Pending |
| Large events (sports, concerts, festivals) | Manual curation / OSM | Date + LGA/suburb | Pending |
| Land use / POI density | OpenStreetMap (Overpass API) | LGA (point-in-polygon) or proximity (Haversine) | Done -- see Section 5 |
