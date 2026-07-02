"""
Crash Data -> Traffic Data Alignment Script
============================================
Aligns NSW Crash Data to traffic_hourly table by time + space,
generating crash context features.

Method:
  Time:  month + day_of_week + 2h_window -> hour
  Space: each crash -> traffic stations within 5km radius

Output:
  data/traffic_hourly_sydney_{YEAR}_aligned.csv  -- traffic data with 5 crash columns appended
  data/crash_alignment_stats_{YEAR}.csv          -- alignment summary statistics (per year)
"""

import pandas as pd
import numpy as np
import os
import sys
import io
import time

# GBK encoding workaround for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATA = "data"
CRASH_FILE = os.path.join(DATA, "nsw_road_crash_data_2020-2024_crash.xlsx")
STATIONS_FILE = os.path.join(DATA, "stations_sydney.csv")
YEARS = [2022, 2023, 2024]

RADIUS_KM = 5.0  # crash influence radius


# ============================================================
# 1. Load and preprocess crash data
# ============================================================
def load_crashes() -> pd.DataFrame:
    print("[1/5] Loading crash data...")
    cols = [
        "Year of crash", "Month of crash", "Day of week of crash",
        "Two-hour intervals", "Degree of crash",
        "Latitude", "Longitude", "LGA",
        "Weather", "Surface condition", "Natural lighting",
        "Speed limit", "Road classification (admin)",
        "No. killed", "No. seriously injured",
        "No. moderately injured", "No. minor-other injured",
    ]
    df = pd.read_excel(CRASH_FILE, usecols=cols)
    df = df[df["Year of crash"].isin(YEARS)].copy()
    print(f"  {len(df):,} crashes in {YEARS}")

    # -- time mapping --
    month_map = {
        "January": 1, "February": 2, "March": 3, "April": 4,
        "May": 5, "June": 6, "July": 7, "August": 8,
        "September": 9, "October": 10, "November": 11, "December": 12,
    }
    dow_map = {
        "Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4,
        "Friday": 5, "Saturday": 6, "Sunday": 7,
    }
    # 2h_window -> hour list
    window_to_hours = {
        "00:01 - 01:59":     [0, 1],
        "02:00 - 03:59":     [2, 3],
        "04:00 - 05:59":     [4, 5],
        "06:00 - 07:59":     [6, 7],
        "08:00 - 09:59":     [8, 9],
        "10:00 - 11:59":     [10, 11],
        "12:00 - 13:59":     [12, 13],
        "14:00 - 15:59":     [14, 15],
        "16:00 - 17:59":     [16, 17],
        "18:00 - 19:59":     [18, 19],
        "20:00 - 21:59":     [20, 21],
        "22:00 - Midnight":  [22, 23],
    }

    df["month"] = df["Month of crash"].map(month_map)
    df["day_of_week"] = df["Day of week of crash"].map(dow_map)
    df["hours"] = df["Two-hour intervals"].map(window_to_hours)

    # drop Unknown time windows
    before = len(df)
    df = df.dropna(subset=["month", "day_of_week", "hours"]).copy()
    print(f"  {len(df):,} after dropping Unknown time windows (removed {before - len(df)})")

    # -- severity scoring --
    severity = {"Fatal": 5, "Injury": 2, "Non-casualty (towaway)": 1}
    df["severity_score"] = df["Degree of crash"].map(severity).fillna(0)
    df["total_injuries"] = (df["No. killed"] + df["No. seriously injured"] +
                             df["No. moderately injured"] + df["No. minor-other injured"])

    print(f"  severity: {df['Degree of crash'].value_counts().to_dict()}")
    return df


# ============================================================
# 2. Vectorized Haversine distance
# ============================================================
def haversine(lat1, lon1, lat2, lon2):
    """Vectorized Haversine formula, returns distance in km"""
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (np.sin(dlat / 2) ** 2 +
         np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2)
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


# ============================================================
# 3. Spatial join: crash -> nearby stations
# ============================================================
def spatial_join(crashes: pd.DataFrame, stations: pd.DataFrame) -> pd.DataFrame:
    """
    For each crash, find all stations within 5 km.
    Returns a long table of (station_key, month, day_of_week, hour,
                             severity_score, total_injuries, is_fatal, is_wet)
    """
    print(f"\n[2/5] Spatial join: {len(crashes):,} crashes x {len(stations)} stations...")
    t0 = time.time()

    c_lat = crashes["Latitude"].values
    c_lon = crashes["Longitude"].values
    s_lat = stations["wgs84_latitude"].values
    s_lon = stations["wgs84_longitude"].values
    s_keys = stations["station_key"].values

    rows = []
    chunk = 2000
    total_hits = 0

    for i in range(0, len(crashes), chunk):
        end = min(i + chunk, len(crashes))
        c_lat_chunk = c_lat[i:end]
        c_lon_chunk = c_lon[i:end]

        for j in range(len(c_lat_chunk)):
            ci = i + j
            # distance to all stations
            dists = haversine(c_lat_chunk[j], c_lon_chunk[j], s_lat, s_lon)
            nearby = np.where(dists <= RADIUS_KM)[0]

            if len(nearby) == 0:
                continue

            crash_row = crashes.iloc[ci]
            hours_list = crash_row["hours"]

            for h in hours_list:
                for sk_idx in nearby:
                    rows.append({
                        "station_key": int(s_keys[sk_idx]),
                        "month": crash_row["month"],
                        "day_of_week": crash_row["day_of_week"],
                        "hour": h,
                        "severity_score": crash_row["severity_score"],
                        "total_injuries": crash_row["total_injuries"],
                        "is_fatal": 1 if crash_row["Degree of crash"] == "Fatal" else 0,
                        "is_wet": 1 if crash_row["Surface condition"] == "Wet" else 0,
                    })
            total_hits += len(nearby) * len(hours_list)

        if (end % 4000) < chunk:
            print(f"  {end:,}/{len(crashes):,} crashes processed, {total_hits:,} station x hour pairs...")

    elapsed = time.time() - t0
    result = pd.DataFrame(rows)
    print(f"  Done in {elapsed:.0f}s: {len(result):,} rows")
    print(f"  Stations with >=1 nearby crash: {result['station_key'].nunique()}")
    return result


# ============================================================
# 4. Aggregate crash features by (station, month, dow, hour)
# ============================================================
def aggregate_crashes(joined: pd.DataFrame) -> pd.DataFrame:
    print(f"\n[3/5] Aggregating crash features per (station, month, dow, hour)...")

    agg = joined.groupby(["station_key", "month", "day_of_week", "hour"]).agg(
        crash_count=("severity_score", "count"),
        crash_severity_sum=("severity_score", "sum"),
        crash_injury_sum=("total_injuries", "sum"),
        crash_fatal_count=("is_fatal", "sum"),
        crash_wet_count=("is_wet", "sum"),
    ).reset_index()

    print(f"  {len(agg):,} unique (station, month, dow, hour) combinations")
    print(f"  crash_count: mean={agg['crash_count'].mean():.2f}, "
          f"max={agg['crash_count'].max()}, "
          f">0 in {agg['crash_count'].gt(0).mean():.1%} of slots")
    return agg


# ============================================================
# 5. Merge to traffic data
# ============================================================
def merge_duplicate_traffic_rows(traffic: pd.DataFrame) -> pd.DataFrame:
    """
    Collapse duplicated detector rows for the same station/date/hour.
    Multiple rows can represent separate traffic streams for one station; add
    their hourly volume and daily total before attaching crash features.
    """
    sum_cols = ["daily_total", "volume"]
    group_cols = [c for c in traffic.columns if c not in sum_cols]

    dup_mask = traffic.duplicated(subset=group_cols, keep=False)
    dup_rows = int(dup_mask.sum())
    if dup_rows == 0:
        print("  No duplicate traffic rows found")
        return traffic

    before_rows = len(traffic)
    traffic = (
        traffic.groupby(group_cols, as_index=False, dropna=False)[sum_cols]
        .sum()
    )

    ordered_cols = [c for c in group_cols if c in traffic.columns]
    for c in sum_cols:
        if c in traffic.columns:
            insert_at = 6 if c == "daily_total" else 7
            ordered_cols.insert(min(insert_at, len(ordered_cols)), c)
    traffic = traffic[[c for c in ordered_cols if c in traffic.columns]]

    print(
        f"  Merged duplicate traffic rows: {before_rows:,} -> {len(traffic):,} "
        f"(collapsed {before_rows - len(traffic):,} rows)"
    )
    return traffic


def merge_to_traffic(crash_agg: pd.DataFrame, traffic_file: str, aligned_file: str):
    print(f"\n[4/5] Merging crash features into traffic data...")
    t0 = time.time()

    # load traffic
    print("  Loading traffic CSV (large file)...")
    traffic = pd.read_csv(traffic_file)
    print(f"  {len(traffic):,} rows, {len(traffic.columns)} cols")
    traffic = merge_duplicate_traffic_rows(traffic)

    before_cols = len(traffic.columns)

    # left join
    traffic = traffic.merge(
        crash_agg,
        on=["station_key", "month", "day_of_week", "hour"],
        how="left",
    )

    # fill rows with no crash data
    crash_cols = ["crash_count", "crash_severity_sum", "crash_injury_sum",
                   "crash_fatal_count", "crash_wet_count"]
    for c in crash_cols:
        traffic[c] = traffic[c].fillna(0).astype(int)

    new_cols = len(traffic.columns)
    elapsed = time.time() - t0
    print(f"  Done in {elapsed:.0f}s: {len(traffic):,} rows, {new_cols} cols (added {new_cols - before_cols})")

    # -- save aligned file --
    print(f"\n[5/5] Saving aligned file...")
    traffic.to_csv(aligned_file, index=False)
    mb = os.path.getsize(aligned_file) / 1024 / 1024
    print(f"  [OK] {aligned_file} ({mb:.1f} MB)")

    # -- stats --
    print(f"\n=== Crash Feature Stats ===")
    for c in crash_cols:
        nonzero = (traffic[c] > 0).sum()
        print(f"  {c}: mean={traffic[c].mean():.3f}, "
              f"max={traffic[c].max()}, nonzero={nonzero:,} ({nonzero/len(traffic):.2%})")

    # save alignment stats (per-year)
    stats_file = aligned_file.replace("_aligned.csv", "_crash_stats.csv")
    stats = pd.DataFrame({
        "feature": crash_cols,
        "mean": [traffic[c].mean() for c in crash_cols],
        "max": [traffic[c].max() for c in crash_cols],
        "nonzero_pct": [(traffic[c] > 0).mean() for c in crash_cols],
    })
    stats.to_csv(stats_file, index=False)

    return traffic


# ============================================================
def main():
    print("=" * 60)
    print("Crash <-> Traffic Alignment")
    print(f"  Radius: {RADIUS_KM} km")
    print(f"  Years: {YEARS}")
    print("=" * 60)

    crashes = load_crashes()
    stations = pd.read_csv(STATIONS_FILE)

    joined = spatial_join(crashes, stations)

    if joined.empty:
        print("[ERROR] No crashes matched to any station!")
        return

    crash_agg = aggregate_crashes(joined)

    for YEAR in YEARS:
        print(f"\n{'='*60}")
        print(f"--- Year {YEAR} ---")
        print(f"{'='*60}")
        traffic_file = os.path.join(DATA, f"traffic_hourly_sydney_{YEAR}.csv")
        aligned_file = os.path.join(DATA, f"traffic_hourly_sydney_{YEAR}_aligned.csv")
        merge_to_traffic(crash_agg, traffic_file, aligned_file)

    print("\n" + "=" * 60)
    print("Done. Crash features saved to traffic_hourly_sydney_{2022,2023,2024}_aligned.csv")
    print("=" * 60)


if __name__ == "__main__":
    main()
