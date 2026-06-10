"""
NSW Traffic Volume Counts API -- Benchmark Data Download (curated)
==================================================================
Only keeps columns actually needed for the benchmark.

Three output files:
  data/stations_sydney.csv              (9 cols)   station metadata
  data/traffic_hourly_sydney_2019.csv   (14 cols)  hourly traffic, long format
  data/yearly_summary_sydney_2019.csv   (10 cols)  annual summary (AADT)
"""

import requests
import pandas as pd
import time
import os
from io import StringIO
from datetime import datetime

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiIxeGRRcTZxd3hyUHB2dWFtaUJDWlJZYU85dDJKdzRlcmJOUXpBU054QmZFIiwiaWF0IjoxNzgxMDEyNzA5fQ.4oVqr7Rdt4cOEsLZ4wL7aJ-Owp1eemcwPYuDSbN57Ew"
BASE_URL = "https://api.transport.nsw.gov.au/v1/traffic_volume"
HEADERS = {"Authorization": f"apikey {API_KEY}"}
OUTPUT_DIR = "data"
YEAR = 2019
LAT = (-34.2, -33.4)
LON = (150.5, 151.5)

# -- curated column definitions --
# stations: removed station_id, road_name, common_road_name, road_classification_type, suburb, post_code, rms_region, permanent_station
STATION_COLS = "station_key,name,full_name,road_functional_hierarchy,lga,wgs84_latitude,wgs84_longitude,vehicle_classifier,device_type"

# hourly: removed year, name, road_name, suburb (year derivable from date; name duplicates full_name)
HOUR_COLS = "station_key,date,month,day_of_week,public_holiday,school_holiday,daily_total,hour_00,hour_01,hour_02,hour_03,hour_04,hour_05,hour_06,hour_07,hour_08,hour_09,hour_10,hour_11,hour_12,hour_13,hour_14,hour_15,hour_16,hour_17,hour_18,hour_19,hour_20,hour_21,hour_22,hour_23"

# yearly: removed geom/cartodb/md5/update_date and 11 other useless columns
YEARLY_COLS = "station_key,station_id,traffic_direction_name,cardinal_direction_name,classification_type,year,period,traffic_count,data_availability,data_reliability"


def query(sql: str) -> pd.DataFrame:
    r = requests.get(BASE_URL, headers=HEADERS, params={"q": sql, "format": "csv"}, timeout=120)
    if r.status_code == 401:
        raise PermissionError("API key invalid (401)")
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    return pd.read_csv(StringIO(r.text))


def save(df: pd.DataFrame, name: str):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, name)
    df.to_csv(path, index=False)
    mb = os.path.getsize(path) / 1024 / 1024
    print(f"  [OK] {name} ({len(df):,} rows, {mb:.1f} MB)")


def melt_to_long(wide: pd.DataFrame) -> pd.DataFrame:
    hour_cols = [f"hour_{h:02d}" for h in range(24)]
    id_cols = [c for c in wide.columns if c not in hour_cols]
    long = wide.melt(id_vars=id_cols, value_vars=hour_cols, var_name="hour_str", value_name="volume")
    long["hour"] = long["hour_str"].str.extract(r"(\d+)").astype(int)
    long = long.drop(columns=["hour_str"]).dropna(subset=["volume"]).reset_index(drop=True)
    return long


def main():
    print("=" * 60)
    print(f"NSW Traffic Benchmark Data -- {YEAR} (cleaned)")
    print(f"  {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("=" * 60)

    # -- 1. stations --
    print("\n[1/3] stations...")
    sql = f"SELECT {STATION_COLS} FROM road_traffic_counts_station_reference WHERE wgs84_latitude >= {LAT[0]} AND wgs84_latitude <= {LAT[1]} AND wgs84_longitude >= {LON[0]} AND wgs84_longitude <= {LON[1]} AND publish = true AND permanent_station = 1 ORDER BY station_key"
    st = query(sql)
    print(f"  {len(st)} stations")
    save(st, "stations_sydney.csv")

    # -- 2. hourly --
    print(f"\n[2/3] hourly data for {len(st)} stations...")
    keys = st["station_key"].tolist()
    BATCH = 10
    all_wide = []

    for i in range(0, len(keys), BATCH):
        batch = keys[i:i + BATCH]
        bn = i // BATCH + 1
        ids = ", ".join(str(k) for k in batch)
        sql = f"SELECT {HOUR_COLS} FROM road_traffic_counts_hourly_permanent WHERE station_key IN ({ids}) AND year = {YEAR} ORDER BY station_key,date"
        try:
            df = query(sql)
            all_wide.append(df)
            print(f"  batch {bn}/{((len(keys)-1)//BATCH+1)}: {len(df)} days x {df['station_key'].nunique()} stations")
            time.sleep(0.3)
        except Exception as e:
            print(f"  batch {bn} FAIL: {e}")

    wide = pd.concat(all_wide, ignore_index=True)
    long = melt_to_long(wide)
    # merge station context (full_name, hierarchy, lga, lat, lon)
    meta = st[["station_key", "full_name", "road_functional_hierarchy", "lga",
               "wgs84_latitude", "wgs84_longitude"]]
    long = long.merge(meta, on="station_key", how="left")
    long = long.rename(columns={"wgs84_latitude": "latitude", "wgs84_longitude": "longitude"})
    save(long, f"traffic_hourly_sydney_{YEAR}.csv")

    # -- 3. yearly --
    print(f"\n[3/3] yearly summary...")
    valid = [int(k) for k in wide["station_key"].unique()]
    BATCH_Y = 30
    all_yr = []
    for i in range(0, len(valid), BATCH_Y):
        batch = valid[i:i + BATCH_Y]
        ids = ", ".join(str(k) for k in batch)
        sql = f"SELECT {YEARLY_COLS} FROM road_traffic_counts_yearly_summary WHERE station_key IN ({ids}) AND year = {YEAR} ORDER BY station_key"
        try:
            yr = query(sql)
            all_yr.append(yr)
            time.sleep(0.2)
        except Exception as e:
            print(f"  yearly batch FAIL: {e}")
    if all_yr:
        yearly = pd.concat(all_yr, ignore_index=True)
        save(yearly, f"yearly_summary_sydney_{YEAR}.csv")

    # -- summary --
    print("\n" + "=" * 60)
    print("=== final stats ===")
    print(f"  stations: {len(st)}")
    print(f"  traffic rows: {len(long):,}")
    print(f"  traffic stations: {long['station_key'].nunique()}")
    v = long["volume"]
    print(f"  volume: {v.min():.0f} ~ {v.max():.0f} (mean={v.mean():.0f}, median={v.median():.0f})")
    print(f"  public_holiday: {long['public_holiday'].mean():.2%}")
    print(f"  school_holiday: {long['school_holiday'].mean():.2%}")
    print("=" * 60)


if __name__ == "__main__":
    main()
