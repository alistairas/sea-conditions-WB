import sys
from pathlib import Path
from datetime import timedelta

import pandas as pd
import matplotlib.pyplot as plt


PROJECT_TITLE = "Whitley Bay Multi-Source Sea Temperature Record"
REPORT_TITLE = "Apple Watch Sensor Characterisation Report v0.1"


def load_data(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    # Expected columns from the extraction script:
    # Date, Time, Temperature_C, Source
    temp_col = "Temperature_C" if "Temperature_C" in df.columns else "Temperature"

    df["timestamp"] = pd.to_datetime(df["Date"] + " " + df["Time"])
    df["temperature_c"] = pd.to_numeric(df[temp_col], errors="coerce")

    df = df.dropna(subset=["timestamp", "temperature_c"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    return df


def add_sessions(df: pd.DataFrame, gap_minutes: int = 30) -> pd.DataFrame:
    df = df.copy()
    df["gap_minutes"] = df["timestamp"].diff().dt.total_seconds().div(60)
    df["new_session"] = (df["gap_minutes"].isna()) | (df["gap_minutes"] > gap_minutes)
    df["session_id"] = df["new_session"].cumsum()
    return df


def session_summary(df: pd.DataFrame) -> pd.DataFrame:
    grouped = df.groupby("session_id")

    sessions = grouped.agg(
        start=("timestamp", "min"),
        end=("timestamp", "max"),
        readings=("temperature_c", "count"),
        min_temp=("temperature_c", "min"),
        max_temp=("temperature_c", "max"),
        median_temp=("temperature_c", "median"),
    ).reset_index()

    sessions["duration_minutes"] = (
        sessions["end"] - sessions["start"]
    ).dt.total_seconds() / 60

    sessions["range_c"] = sessions["max_temp"] - sessions["min_temp"]

    sessions["observation_type"] = pd.cut(
        sessions["readings"],
        bins=[0, 1, 4, float("inf")],
        labels=["single observation", "short session", "continuous session"],
    )

    return sessions


def sampling_intervals(df: pd.DataFrame) -> pd.Series:
    intervals = []

    for _, g in df.groupby("session_id"):
        if len(g) > 1:
            diffs = g["timestamp"].diff().dt.total_seconds().dropna()
            intervals.extend(diffs.tolist())

    return pd.Series(intervals, name="sampling_interval_seconds")


def plot_hist(series, title, xlabel, output_path, bins=30):
    plt.figure()
    series.dropna().plot(kind="hist", bins=bins)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_monthly_counts(df, output_path):
    monthly = df.set_index("timestamp").resample("ME").size()

    plt.figure()
    monthly.plot(kind="bar")
    plt.title("Water temperature observations by month")
    plt.xlabel("Month")
    plt.ylabel("Observations")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_temperature_range(df, output_path):
    plt.figure()
    df.plot(x="timestamp", y="temperature_c", kind="scatter", s=8)
    plt.title("Raw Apple Watch water temperature observations")
    plt.xlabel("Date")
    plt.ylabel("Temperature (°C)")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def format_percentiles(series):
    p = series.dropna().quantile([0.1, 0.25, 0.5, 0.75, 0.9, 0.95])
    return "\n".join(
        f"- {int(q * 100)}th percentile: **{v:.1f}**"
        for q, v in p.items()
    )


def make_report(df, sessions, intervals, output_dir):
    report_path = output_dir / "apple_watch_sensor_characterisation_v0.1.md"

    start_date = df["timestamp"].min().date()
    end_date = df["timestamp"].max().date()

    raw_n = len(df)
    session_n = len(sessions)

    single_n = (sessions["readings"] == 1).sum()
    short_n = ((sessions["readings"] >= 2) & (sessions["readings"] <= 4)).sum()
    continuous_n = (sessions["readings"] >= 5).sum()

    high_values = (df["temperature_c"] >= 20).sum()
    very_high_values = (df["temperature_c"] >= 25).sum()

    median_interval = intervals.median() if len(intervals) else None

    md = f"""# {PROJECT_TITLE}

## {REPORT_TITLE}

### Bringing together swimmers, satellites and history to understand Whitley Bay's changing sea temperature.

---

## 1. Purpose

This report characterises Apple Watch water temperature observations extracted from Apple Health.

The aim is to understand the behaviour of the Apple Watch as a water temperature sensor before deriving representative sea temperature estimates.

---

## 2. Dataset overview

| Metric | Value |
|---|---:|
| Raw water temperature observations | {raw_n:,} |
| Observation period | {start_date} to {end_date} |
| Sessions using 30-minute gap rule | {session_n:,} |
| Single-observation sessions | {single_n:,} |
| Short sessions, 2–4 readings | {short_n:,} |
| Continuous sessions, 5+ readings | {continuous_n:,} |

---

## 3. Temperature range and high values

Apple Health records a wide range of water temperature values. Some high values are unlikely to represent open seawater at Whitley Bay and are probably affected by body heat, wetsuit coverage, post-swim warming, showering or other non-sea exposure.

| Metric | Value |
|---|---:|
| Minimum recorded temperature | {df["temperature_c"].min():.2f}°C |
| Maximum recorded temperature | {df["temperature_c"].max():.2f}°C |
| Readings >=20°C | {high_values:,} |
| Readings >=25°C | {very_high_values:,} |

![Raw temperature observations](charts/raw_temperature_observations.png)

---

## 4. Sampling behaviour

Where the watch records multiple readings within a session, the sampling interval is typically short.

| Metric | Value |
|---|---:|
| Median sampling interval | {median_interval:.1f} seconds |
| Number of within-session intervals | {len(intervals):,} |

Sampling interval percentiles:

{format_percentiles(intervals)}

![Sampling interval distribution](charts/sampling_intervals.png)

---

## 5. Session duration

Session duration is calculated as the time between the first and last water temperature observation in each session.

Duration percentiles:

{format_percentiles(sessions["duration_minutes"])}

![Session duration distribution](charts/session_durations.png)

---

## 6. Readings per session

A substantial number of sessions contain only one or a small number of readings. These should be treated differently from continuous sessions where a stable temperature plateau can be identified.

Readings-per-session percentiles:

{format_percentiles(sessions["readings"])}

![Readings per session](charts/readings_per_session.png)

---

## 7. Initial interpretation

The Apple Watch appears to provide useful in-water temperature observations, but the data should not be treated as a complete diary of all swims.

Several factors affect interpretation:

- More than one Apple Watch may have contributed data over the observation period.
- Recording behaviour may differ between devices or watchOS versions.
- Gaps in the record may reflect sensor availability rather than absence of swimming.
- High values suggest the sensor sometimes records body heat or post-swim warming.
- Single-observation sessions should not be treated as equivalent to continuous swim recordings.

---

## 8. Methodological implication

The preferred approach is to derive representative seawater temperature from the stable temperature plateau within continuous swim sessions.

Sessions without enough observations to identify a stable plateau should be flagged with lower confidence or held for manual review.

---

## 9. Next steps

Recommended next steps:

1. Implement stable plateau detection for continuous sessions.
2. Assign confidence categories based on readings, duration and plateau quality.
3. Compare representative Apple Watch temperatures with Copernicus SST.
4. Compare with historical local water temperature records where dates overlap.
5. Produce a validated `apple_watch_sessions.csv` dataset.

---

## Status

**Version:** 0.1  
**Generated from:** `water_temperatures.csv`

This report is an initial sensor characterisation and should not yet be treated as a final validation of Apple Watch-derived sea temperature.
"""

    report_path.write_text(md, encoding="utf-8")
    return report_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 apple_watch_sensor_report.py water_temperatures.csv")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    output_dir = Path("reports")
    chart_dir = output_dir / "charts"
    output_dir.mkdir(exist_ok=True)
    chart_dir.mkdir(parents=True, exist_ok=True)

    df = load_data(csv_path)
    df = add_sessions(df, gap_minutes=30)
    sessions = session_summary(df)
    intervals = sampling_intervals(df)

    plot_temperature_range(df, chart_dir / "raw_temperature_observations.png")
    plot_monthly_counts(df, chart_dir / "monthly_observations.png")
    plot_hist(
        intervals,
        "Sampling intervals within sessions",
        "Seconds",
        chart_dir / "sampling_intervals.png",
        bins=40,
    )
    plot_hist(
        sessions["duration_minutes"],
        "Session duration distribution",
        "Minutes",
        chart_dir / "session_durations.png",
        bins=40,
    )
    plot_hist(
        sessions["readings"],
        "Readings per session",
        "Readings",
        chart_dir / "readings_per_session.png",
        bins=40,
    )

    sessions.to_csv(output_dir / "apple_watch_session_summary_diagnostic.csv", index=False)

    report_path = make_report(df, sessions, intervals, output_dir)

    print(f"Report written to: {report_path}")
    print(f"Charts written to: {chart_dir}")
    print(f"Diagnostic session CSV written to: {output_dir / 'apple_watch_session_summary_diagnostic.csv'}")


if __name__ == "__main__":
    main()