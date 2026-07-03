print("Climate record script started", flush=True)

import calendar
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import cdsapi
import pandas as pd
import xarray as xr

print("Imports complete", flush=True)

# ------------------------------------------------------------
# Location / sample area
# ------------------------------------------------------------

LOCATION_NAME = "North Tyneside coast"
LOCATION_DESCRIPTION = "Offshore coastal waters around Whitley Bay, Cullercoats and Tynemouth"

# Reference point near Whitley Bay / Panama Swimming Club
REFERENCE_LAT = 55.0519527
REFERENCE_LON = -1.4479198

# ERA5 is coarser than OSTIA, so use a wider coastal box.
# CDS area order is: North, West, South, East
ERA5_NORTH = 55.25
ERA5_SOUTH = 54.75
ERA5_WEST = -1.75
ERA5_EAST = -1.00

# ------------------------------------------------------------
# Dataset settings
# ------------------------------------------------------------

DATASET_ID = "reanalysis-era5-single-levels"
VARIABLE_REQUEST_NAME = "sea_surface_temperature"

# In NetCDF the ERA5 SST variable often appears as "sst"
POSSIBLE_SST_VARIABLE_NAMES = [
    "sst",
    "sea_surface_temperature",
]

BASELINE_START = 1991
BASELINE_END = 2020

# For first testing, run:
# CLIMATE_START_YEAR=2023 CLIMATE_END_YEAR=2026 python scripts/build_climate_record.py
#
# For full run, leave unset or set CLIMATE_START_YEAR=1940.
START_YEAR = int(os.environ.get("CLIMATE_START_YEAR", "1940"))
END_YEAR = int(os.environ.get("CLIMATE_END_YEAR", str(datetime.now(timezone.utc).year)))

# ERA5/ERA5T can lag. Use a conservative end date for current-year pulls.
# You can override with CLIMATE_END_DATE=YYYY-MM-DD.
DEFAULT_END_DATE = datetime.now(timezone.utc).date() - timedelta(days=7)
END_DATE = date.fromisoformat(os.environ.get("CLIMATE_END_DATE", DEFAULT_END_DATE.isoformat()))

# Avoid requesting before the selected start year.
START_DATE = date(START_YEAR, 1, 1)

# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------

CACHE_DIR = Path("climate-cache")
CACHE_DIR.mkdir(exist_ok=True)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

OUT_JSON = DATA_DIR / "nt_era5_sst_climate.json"
OUT_CSV = DATA_DIR / "nt_era5_sst_climate_daily.csv"

print(f"Start year: {START_YEAR}", flush=True)
print(f"End year: {END_YEAR}", flush=True)
print(f"End date: {END_DATE}", flush=True)
print(f"Output JSON: {OUT_JSON}", flush=True)

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def download_period(start_year: int, end_year: int, client: cdsapi.Client) -> Path | None:
    """
    Download ERA5 hourly SST for a multi-year period.
    This avoids one slow CDS queue per year.
    """
    period_start = date(start_year, 1, 1)
    period_end = min(date(end_year, 12, 31), END_DATE)

    if period_end < period_start:
        print(f"Skipping {start_year}-{end_year}: after end date", flush=True)
        return None

    years = [str(y) for y in range(start_year, end_year + 1) if date(y, 1, 1) <= END_DATE]

    months = [f"{m:02d}" for m in range(1, 13)]
    days = [f"{d:02d}" for d in range(1, 32)]

    out_file = CACHE_DIR / f"era5_sst_nt_{start_year}_{end_year}.nc"

    if out_file.exists() and out_file.stat().st_size > 0:
        print(f"Using cached file: {out_file}", flush=True)
        return out_file

    request = {
        "product_type": ["reanalysis"],
        "variable": [VARIABLE_REQUEST_NAME],
        "year": years,
        "month": months,
        "day": days,
        "time": [
            "00:00", "01:00", "02:00", "03:00",
            "04:00", "05:00", "06:00", "07:00",
            "08:00", "09:00", "10:00", "11:00",
            "12:00", "13:00", "14:00", "15:00",
            "16:00", "17:00", "18:00", "19:00",
            "20:00", "21:00", "22:00", "23:00",
        ],
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": [
            ERA5_NORTH,
            ERA5_WEST,
            ERA5_SOUTH,
            ERA5_EAST,
        ],
    }

    print(f"Downloading ERA5 SST for {start_year}-{end_year}", flush=True)

    for attempt in range(1, 4):
        try:
            print(f"CDS attempt {attempt}/3 for {start_year}-{end_year}", flush=True)
            client.retrieve(DATASET_ID, request, str(out_file))
            print(f"Downloaded {out_file}", flush=True)
            return out_file

        except Exception as e:
            print(f"CDS attempt {attempt} failed for {start_year}-{end_year}: {e}", flush=True)

            error_text = str(e).lower()

            if "cost limits exceeded" in error_text or "request is too large" in error_text:
                raise RuntimeError(
                    f"CDS request too large for {year}. "
                    "Reduce the request size."
                ) from e
            
            if "cost limits exceeded" in error_text or "request is too large" in error_text:
                raise RuntimeError(
                    "CDS request too large for {start_year}-{end_year}. "
                    "Reduce CLIMATE_CHUNK_YEARS, for example to 2 or 1."
                ) from e
                
            if "required licences not accepted" in error_text or "licences" in error_text:
                raise RuntimeError(
                    "CDS licence not accepted. Log in to the Copernicus Climate Data Store "
                    "and accept the ERA5 single-levels licence before re-running."
                ) from e

            if out_file.exists():
                try:
                    out_file.unlink()
                except Exception:
                    pass

            if attempt == 3:
                raise

            time.sleep(60)

    return None

def month_day_list(year: int, month: int, end_date: date) -> list[str]:
    """Return day strings for a month, clipped to end_date."""
    last_day = calendar.monthrange(year, month)[1]
    days = []

    for day in range(1, last_day + 1):
        d = date(year, month, day)

        if d < START_DATE:
            continue

        if d > end_date:
            continue

        days.append(f"{day:02d}")

    return days


def month_list_for_year(year: int, end_date: date) -> list[str]:
    """Return month strings for a year, clipped to end_date."""
    months = []

    for month in range(1, 13):
        first_of_month = date(year, month, 1)

        if first_of_month > end_date:
            continue

        if date(year, month, calendar.monthrange(year, month)[1]) < START_DATE:
            continue

        months.append(f"{month:02d}")

    return months


def noleap_doy(ts: pd.Timestamp) -> int | None:
    """
    Return day-of-year on a 365-day no-leap calendar.
    Feb 29 is dropped. Days after Feb 29 in leap years are shifted back by 1.
    """
    if ts.month == 2 and ts.day == 29:
        return None

    doy = int(ts.dayofyear)

    if calendar.isleap(ts.year) and doy > 59:
        return doy - 1

    return doy


def get_sst_variable_name(ds: xr.Dataset) -> str:
    """Find the SST variable in the downloaded NetCDF."""
    for name in POSSIBLE_SST_VARIABLE_NAMES:
        if name in ds.data_vars:
            return name

    raise KeyError(
        "Could not find SST variable. Available variables: "
        + ", ".join(ds.data_vars.keys())
    )


def normalise_time_dimension(ds: xr.Dataset) -> xr.Dataset:
    """
    ERA5 NetCDF may use 'time' or 'valid_time'.
    Standardise to 'time'.
    """
    if "time" in ds.coords or "time" in ds.dims:
        return ds

    if "valid_time" in ds.coords or "valid_time" in ds.dims:
        return ds.rename({"valid_time": "time"})

    raise KeyError(
        "Could not find a time coordinate. Coordinates: "
        + ", ".join(ds.coords.keys())
    )


def download_year(year: int, client: cdsapi.Client) -> Path | None:
    """
    Download ERA5 hourly SST for one year, clipped for the current year.
    Returns the NetCDF path, or None if there are no days to request.
    """
    year_end_date = min(date(year, 12, 31), END_DATE)

    if year_end_date < date(year, 1, 1):
        print(f"Skipping {year}: year is after end date", flush=True)
        return None

    months = month_list_for_year(year, year_end_date)

    if not months:
        print(f"Skipping {year}: no months to request", flush=True)
        return None

    # CDS requires day list. For current year, requesting all days in future
    # months can fail, so build a clipped day list across requested months.
    all_days = sorted(
        {
            day
            for month_str in months
            for day in month_day_list(year, int(month_str), year_end_date)
        }
    )

    if not all_days:
        print(f"Skipping {year}: no days to request", flush=True)
        return None

    out_file = CACHE_DIR / f"era5_sst_nt_{year}.nc"

    if out_file.exists() and out_file.stat().st_size > 0:
        print(f"Using cached file for {year}: {out_file}", flush=True)
        return out_file

    request = {
        "product_type": ["reanalysis"],
        "variable": [VARIABLE_REQUEST_NAME],
        "year": [str(year)],
        "month": months,
        "day": all_days,
        "time": [
            "11:00",
        ],
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": [
            ERA5_NORTH,
            ERA5_WEST,
            ERA5_SOUTH,
            ERA5_EAST,
        ],
    }

    print(f"Downloading ERA5 SST for {year}", flush=True)
    print(f"Months: {months}", flush=True)
    print(f"Days: {all_days[0]} to {all_days[-1]}", flush=True)

    for attempt in range(1, 4):
        try:
            print(f"CDS attempt {attempt}/3 for {year}", flush=True)
            client.retrieve(DATASET_ID, request, str(out_file))
            print(f"Downloaded {out_file}", flush=True)
            return out_file

        except Exception as e:
            print(f"CDS attempt {attempt} failed for {year}: {e}", flush=True)
        
            error_text = str(e).lower()
        
            if "required licences not accepted" in error_text or "licences" in error_text:
                raise RuntimeError(
                    "CDS licence not accepted. Log in to the Copernicus Climate Data Store "
                    "and accept the ERA5 single-levels licence before re-running."
                ) from e
        
            if out_file.exists():
                try:
                    out_file.unlink()
                except Exception:
                    pass
        
            if attempt == 3:
                raise
        
            time.sleep(60)

    return None


def process_year(nc_file: Path, year: int) -> pd.DataFrame:
    """
    Read one NetCDF file and return daily mean SST across the box.
    """
    print(f"Processing {year}: {nc_file}", flush=True)

    ds = xr.open_dataset(nc_file)
    ds = normalise_time_dimension(ds)

    var_name = get_sst_variable_name(ds)

    sst = ds[var_name]

    # Average across the selected coastal box.
    # skipna=True means land/missing cells will not poison the result.
    spatial_dims = [
        dim for dim in ["latitude", "longitude"] if dim in sst.dims
    ]

    if not spatial_dims:
        raise ValueError(f"No latitude/longitude dimensions found for {year}")

    box_mean_k = sst.mean(dim=spatial_dims, skipna=True)

    # Convert Kelvin to Celsius.
    box_mean_c = box_mean_k - 273.15

    # Daily mean.
    daily = box_mean_c.resample(time="1D").mean(skipna=True)

    df = daily.to_dataframe(name="sst_c").reset_index()
    df["date"] = pd.to_datetime(df["time"]).dt.date
    df["year"] = pd.to_datetime(df["time"]).dt.year
    df["month"] = pd.to_datetime(df["time"]).dt.month
    df["day"] = pd.to_datetime(df["time"]).dt.day

    # Remove missing values and future clipped values.
    df = df.dropna(subset=["sst_c"]).copy()
    df["sst_c"] = df["sst_c"].astype(float).round(2)

    # Add no-leap day-of-year for clean overlay charts.
    timestamps = pd.to_datetime(df["date"])
    df["doy"] = [noleap_doy(ts) for ts in timestamps]
    df = df[df["doy"].notna()].copy()
    df["doy"] = df["doy"].astype(int)

    # Handy label for debugging / hover labels.
    df["month_day"] = timestamps.dt.strftime("%m-%d")

    return df[
        [
            "date",
            "year",
            "month",
            "day",
            "doy",
            "month_day",
            "sst_c",
        ]
    ]


def build_json(df: pd.DataFrame) -> dict:
    """
    Build website-friendly JSON.
    """
    print("Building JSON", flush=True)

    baseline_df = df[
        (df["year"] >= BASELINE_START)
        & (df["year"] <= BASELINE_END)
    ].copy()

    baseline = (
        baseline_df.groupby("doy", as_index=False)["sst_c"]
        .mean()
        .sort_values("doy")
    )
    baseline["sst_c"] = baseline["sst_c"].round(2)

    years = []

    for year, group in df.groupby("year"):
        group = group.sort_values("doy")

        years.append(
            {
                "year": int(year),
                "values": [
                    {
                        "date": row["date"].isoformat(),
                        "doy": int(row["doy"]),
                        "month_day": row["month_day"],
                        "sst_c": round(float(row["sst_c"]), 2),
                    }
                    for _, row in group.iterrows()
                ],
            }
        )

    latest_row = df.sort_values("date").iloc[-1]

    return {
        "version": 1,
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "location": LOCATION_NAME,
        "location_description": LOCATION_DESCRIPTION,
        "reference_point": {
            "lat": REFERENCE_LAT,
            "lon": REFERENCE_LON,
            "description": "Near Whitley Bay / Panama Swimming Club",
        },
        "sample_area": {
            "north": ERA5_NORTH,
            "south": ERA5_SOUTH,
            "west": ERA5_WEST,
            "east": ERA5_EAST,
            "description": "Wider ERA5 coastal box for the North Tyneside coast",
        },
        "source": "Copernicus Climate Data Store ERA5 hourly data on single levels",
        "dataset": DATASET_ID,
        "variable": VARIABLE_REQUEST_NAME,
        "measurement": "Sea surface temperature",
        "units": "°C",
        "baseline": f"{BASELINE_START}-{BASELINE_END}",
        "calendar": "365-day no-leap overlay; 29 February is omitted",
        "sample_method": (
            "ERA5 sea surface temperature sampled once per day at 11:00 UTC, "
            "averaged across a North Tyneside coastal grid box and converted "
            "from Kelvin to Celsius."
        ),
        "start_year": int(df["year"].min()),
        "end_year": int(df["year"].max()),
        "latest": {
            "date": latest_row["date"].isoformat(),
            "year": int(latest_row["year"]),
            "doy": int(latest_row["doy"]),
            "sst_c": round(float(latest_row["sst_c"]), 2),
        },
        "average_1991_2020": [
            {
                "doy": int(row["doy"]),
                "sst_c": round(float(row["sst_c"]), 2),
            }
            for _, row in baseline.iterrows()
        ],
        "years": years,
    }


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main() -> None:
    print("Creating CDS client", flush=True)
    client = cdsapi.Client()

    chunk_years = int(os.environ.get("CLIMATE_CHUNK_YEARS", "10"))

    all_periods = []

    # Only chunk complete years.
    # The current ERA5/ERA5T year is partial, so handle it separately.
    latest_complete_year = min(END_YEAR, END_DATE.year - 1)

    year = START_YEAR

    while year <= latest_complete_year:
        chunk_start = year
        chunk_end = min(year + chunk_years - 1, latest_complete_year)

        nc_file = download_period(chunk_start, chunk_end, client)

        if nc_file is not None:
            df_period = process_year(nc_file, chunk_start)
            all_periods.append(df_period)

        year = chunk_end + 1

    # Handle current partial year separately, if requested.
    if END_YEAR >= END_DATE.year and START_YEAR <= END_DATE.year:
        current_year = END_DATE.year
        print(f"Downloading current partial year separately: {current_year}", flush=True)

        nc_file = download_year(current_year, client)

        if nc_file is not None:
            df_period = process_year(nc_file, current_year)
            all_periods.append(df_period)

    if not all_periods:
        raise RuntimeError("No climate data was downloaded or processed.")

    df = pd.concat(all_periods, ignore_index=True)
    df = df.sort_values("date").reset_index(drop=True)

    print(f"Daily rows: {len(df)}", flush=True)
    print(f"First date: {df['date'].min()}", flush=True)
    print(f"Last date: {df['date'].max()}", flush=True)

    df.to_csv(OUT_CSV, index=False)
    print(f"Wrote CSV: {OUT_CSV}", flush=True)

    payload = build_json(df)

    with open(OUT_JSON, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"Wrote JSON: {OUT_JSON}", flush=True)
    print("Climate record script finished", flush=True)


if __name__ == "__main__":
    main()
    
if __name__ == "__main__":
    main()