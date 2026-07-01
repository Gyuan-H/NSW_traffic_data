"""
NSW Traffic Benchmark -- Data Reader & Explorer
================================================
Usage:
  python read_data_en.py                    # show directory and overview
  python read_data_en.py head               # first 20 rows of long table
  python read_data_en.py station <key>      # station details (e.g. 55304)
  python read_data_en.py daily <key>        # daily volume trend for a station
  python read_data_en.py holiday            # holiday vs normal volume comparison
  python read_data_en.py peak               # AM peak vs PM peak by road class
  python read_data_en.py lga <name>         # filter stations by LGA (e.g. Sydney)
  python read_data_en.py road <type>        # filter stations by road class (e.g. Motorway)
  python read_data_en.py crash              # crash feature coverage statistics
"""

import pandas as pd
import os
import sys

DATA_DIR = "data"
DEFAULT_YEAR = 2022

# --- files ---
def get_files(year):
    return {
        "stations":   os.path.join(DATA_DIR, "stations_sydney.csv"),
        "traffic":    os.path.join(DATA_DIR, f"traffic_hourly_sydney_{year}.csv"),
        "aligned":    os.path.join(DATA_DIR, f"traffic_hourly_sydney_{year}_aligned.csv"),
        "yearly":     os.path.join(DATA_DIR, f"yearly_summary_sydney_{year}.csv"),
    }

FILES = get_files(DEFAULT_YEAR)


def load(name: str) -> pd.DataFrame:
    path = FILES[name]
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    print(f"Loading {path} ...")
    df = pd.read_csv(path)
    print(f"  {len(df):,} rows x {len(df.columns)} cols")
    return df


# ============================================================
# Command handlers
# ============================================================

def cmd_head():
    """Display first 20 rows of the long table"""
    df = pd.read_csv(FILES["traffic"], nrows=20)
    print(df.to_string(max_colwidth=50))


def cmd_station(key: int):
    """Show station metadata + 24-hour volume profile"""
    # station metadata
    st = pd.read_csv(FILES["stations"])
    s = st[st["station_key"] == key]
    if s.empty:
        print(f"Station {key} not found")
        return
    print("=== Station Info ===")
    print(s.T.to_string(header=False))

    # hourly data for this station (selected cols only)
    df = pd.read_csv(FILES["traffic"],
                     usecols=["station_key", "date", "hour", "volume",
                              "public_holiday", "school_holiday", "daily_total"])
    df = df[df["station_key"] == key]
    if df.empty:
        print(f"\nStation {key} has no data")
        return

    print(f"\n=== Data Overview ({len(df):,} rows) ===")
    print(f"  Date range: {df['date'].min()[:10]} ~ {df['date'].max()[:10]}")
    print(f"  Daily mean volume: {df['daily_total'].mean():.0f}")
    print(f"  Hourly volume range: {df['volume'].min():.0f} ~ {df['volume'].max():.0f}")
    print(f"  Hourly volume mean: {df['volume'].mean():.0f}")

    # aggregate by hour
    hourly = df.groupby("hour")["volume"].agg(["mean", "median", "std"]).round(0)
    print(f"\n=== 24-Hour Volume Profile ===")
    print(hourly.to_string())

    # holiday / normal comparison
    print(f"\n=== Holiday vs Normal ===")
    for label, mask in [("holiday", df["public_holiday"]),
                         ("school_holiday", df["school_holiday"]),
                         ("normal", ~df["public_holiday"] & ~df["school_holiday"])]:
        subset = df[mask]
        if len(subset):
            print(f"  {label:>15s}: {len(subset):,} rows, mean_vol={subset['volume'].mean():.0f}")


def cmd_daily(key: int):
    """Daily volume trend for a station (console text chart)"""
    df = pd.read_csv(FILES["traffic"],
                     usecols=["station_key", "date", "daily_total", "volume"])
    df = df[df["station_key"] == key]
    if df.empty:
        print(f"Station {key} has no data")
        return

    daily = df.groupby("date").agg(vol_mean=("volume", "mean"),
                                    vol_max=("volume", "max"),
                                    daily_total=("daily_total", "first"))
    print(f"=== Station {key} Daily Volume Trend (first 30 days) ===")
    print(daily.head(30).to_string())


def cmd_holiday():
    """Public holiday vs normal volume comparison -- all Sydney"""
    df = pd.read_csv(FILES["traffic"], nrows=500000,
                     usecols=["hour", "volume", "public_holiday", "school_holiday"])
    print("=== Sydney-wide: Holiday vs Normal Volume Comparison ===")

    for label, col in [("public_holiday", "public_holiday"),
                        ("school_holiday", "school_holiday")]:
        normal = df[~df[col]]["volume"]
        special = df[df[col]]["volume"]
        if len(special) == 0:
            continue
        print(f"\n--- {label} ---")
        print(f"  Normal:         mean={normal.mean():.0f} median={normal.median():.0f} n={len(normal):,}")
        print(f"  {label}:  mean={special.mean():.0f} median={special.median():.0f} n={len(special):,}")
        print(f"  ratio (special/normal mean): {special.mean() / normal.mean():.2f}")


def cmd_peak():
    """AM peak (7-9) vs PM peak (16-18) comparison by road class"""
    df = pd.read_csv(FILES["traffic"], nrows=1000000,
                     usecols=["hour", "volume", "road_functional_hierarchy"])
    df["period"] = "offpeak"
    df.loc[df["hour"].between(7, 9), "period"] = "AM peak (7-9)"
    df.loc[df["hour"].between(16, 18), "period"] = "PM peak (16-18)"

    print("=== Road Hierarchy x Time Period: Mean Volume ===")
    pivot = df.groupby(["road_functional_hierarchy", "period"])["volume"].mean().unstack()
    print(pivot.round(0).to_string())


def cmd_lga(name: str):
    """Filter stations by LGA name"""
    st = pd.read_csv(FILES["stations"])
    matched = st[st["lga"].str.lower().str.contains(name.lower())]
    if matched.empty:
        print(f"LGA not found: {name}")
        print(f"Available LGAs: {sorted(st['lga'].unique())}")
        return
    print(f"=== {name} ({len(matched)} stations) ===")
    for _, r in matched.iterrows():
        print(f"  key={r['station_key']:>8d} | {r['full_name'][:50]:50s} | {r['road_functional_hierarchy']}")


def cmd_road(road_type: str):
    """Filter stations by road functional hierarchy"""
    st = pd.read_csv(FILES["stations"])
    matched = st[st["road_functional_hierarchy"].str.lower().str.contains(road_type.lower())]
    if matched.empty:
        print(f"Road class not found: {road_type}")
        print(f"Available: {sorted(st['road_functional_hierarchy'].dropna().unique())}")
        return
    print(f"=== {road_type} ({len(matched)} stations) ===")
    for _, r in matched.iterrows():
        print(f"  key={r['station_key']:>8d} | {r['full_name'][:50]:50s} | {r['lga']}")


def cmd_crash():
    """Crash feature coverage statistics"""
    df = pd.read_csv(FILES["aligned"], nrows=800000,
                     usecols=["crash_count", "crash_severity_sum", "crash_injury_sum",
                              "crash_fatal_count", "crash_wet_count",
                              "volume", "public_holiday", "school_holiday", "hour",
                              "road_functional_hierarchy"])
    print("=== Crash Feature Coverage ===")
    crash_cols = ["crash_count", "crash_severity_sum", "crash_injury_sum",
                   "crash_fatal_count", "crash_wet_count"]
    for c in crash_cols:
        nz = (df[c] > 0).sum()
        print(f"  {c}: nonzero={nz:,} ({nz/len(df):.1%}), mean={df[c].mean():.3f}, max={df[c].max()}")

    print("\n=== Crash Count vs Volume (hourly avg) ===")
    df["crash_bin"] = pd.cut(df["crash_count"], bins=[-1, 0, 1, 2, 100],
                              labels=["0", "1", "2", "3+"])
    print(df.groupby("crash_bin")["volume"].mean().round(1).to_string())

    print("\n=== Crash Count by Road Hierarchy ===")
    pivot = df.groupby("road_functional_hierarchy")["crash_count"].agg(["mean", "sum"])
    print(pivot.round(2).to_string())

    print("\n=== Crash Count by Hour ===")
    hourly = df.groupby("hour")["crash_count"].mean()
    print(hourly.round(3).to_string())


def cmd_overview():
    """Print overview of all four tables"""
    for name in ["stations", "yearly", "traffic", "aligned"]:
        path = FILES[name]
        size_mb = os.path.getsize(path) / 1024 / 1024 if os.path.exists(path) else 0
        print(f"\n{'-'*50}")
        print(f"[{name}]  {path}  ({size_mb:.1f} MB)")

        if name in ("traffic", "aligned"):
            # peek at first few rows for structure
            df = pd.read_csv(path, nrows=5)
            print(f"  columns ({len(df.columns)}): {', '.join(df.columns)}")
            ncols = len(df.columns)
            # quick row count (without loading all data)
            nrows = sum(1 for _ in open(path, encoding='utf-8')) - 1
            print(f"  shape (full): {nrows:,} x {ncols}")
        else:
            df = pd.read_csv(path)
            print(f"  rows: {len(df):,}  cols: {len(df.columns)}")
            print(f"  columns: {', '.join(df.columns[:10])}...")

    # key statistics
    print(f"\n{'-'*50}")
    print("[key stats]")
    st = pd.read_csv(FILES["stations"])
    print(f"  Road hierarchy: {st['road_functional_hierarchy'].value_counts().to_dict()}")
    print(f"  LGA count: {st['lga'].nunique()}")

    yr = pd.read_csv(FILES["yearly"])
    print(f"  yearly_summary: {len(yr)} rows x {yr['station_key'].nunique()} stations")


# ============================================================
HELP_TEXT = """
Usage:
  python read_data_en.py [--year <YYYY>]                overview
  python read_data_en.py [--year <YYYY>] head            first 20 rows of long table
  python read_data_en.py [--year <YYYY>] station <key>   station details (e.g. 55304)
  python read_data_en.py [--year <YYYY>] daily <key>     daily volume trend
  python read_data_en.py [--year <YYYY>] holiday         holiday vs normal comparison
  python read_data_en.py [--year <YYYY>] peak            peak period analysis
  python read_data_en.py [--year <YYYY>] lga <name>      filter by LGA (e.g. Sydney)
  python read_data_en.py [--year <YYYY>] road <type>     filter by road class (e.g. Motorway)
  python read_data_en.py [--year <YYYY>] crash           crash feature statistics

Default year: 2022
"""


if __name__ == "__main__":
    args = sys.argv[1:]

    # parse --year / -y argument
    if len(args) >= 2 and args[0] in ("--year", "-y"):
        YEAR = int(args[1])
        FILES = get_files(YEAR)
        args = args[2:]

    if not args:
        cmd_overview()
    elif args[0] == "head":
        cmd_head()
    elif args[0] == "station" and len(args) > 1:
        cmd_station(int(args[1]))
    elif args[0] == "daily" and len(args) > 1:
        cmd_daily(int(args[1]))
    elif args[0] == "holiday":
        cmd_holiday()
    elif args[0] == "peak":
        cmd_peak()
    elif args[0] == "lga" and len(args) > 1:
        cmd_lga(args[1])
    elif args[0] == "road" and len(args) > 1:
        cmd_road(args[1])
    elif args[0] == "crash":
        cmd_crash()
    else:
        print(HELP_TEXT)
