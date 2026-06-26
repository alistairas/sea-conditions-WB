import sys
from pathlib import Path
from datetime import timedelta

import pandas as pd
import matplotlib.pyplot as plt


PROJECT_TITLE = "Whitley Bay Multi-Source Sea Temperature Record"
REPORT_TITLE = "Smartwatch Sensor Characterisation Report v0.1"

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

def make_report(df, sessions, intervals):
    report_path = Path("smartwatch.html")

    start_date = df["timestamp"].min().date()
    end_date = df["timestamp"].max().date()

    raw_n = len(df)
    session_n = len(sessions)

    single_n = (sessions["readings"] == 1).sum()
    short_n = ((sessions["readings"] >= 2) & (sessions["readings"] <= 4)).sum()
    continuous_n = (sessions["readings"] >= 5).sum()

    high_values = (df["temperature_c"] >= 20).sum()
    very_high_values = (df["temperature_c"] >= 25).sum()

    median_interval = intervals.median() if len(intervals) else 0

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Smartwatch Report | Whitley Bay Sea Temperature</title>
<style>
body {{
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  margin: 0;
  background: #f4f7f8;
  color: #102027;
}}
.page {{
  max-width: 760px;
  margin: 0 auto;
  padding: 24px;
}}
.card {{
  background: white;
  border-radius: 18px;
  padding: 22px;
  margin: 18px 0;
  box-shadow: 0 8px 24px rgba(0,0,0,0.08);
}}
h1, h2 {{
  margin-top: 0;
}}
table {{
  width: 100%;
  border-collapse: collapse;
}}
td, th {{
  border-bottom: 1px solid #ddd;
  padding: 8px;
  text-align: left;
}}
img {{
  max-width: 100%;
  border-radius: 12px;
  margin-top: 12px;
}}
.small {{
  color: #607d8b;
  font-size: 0.9rem;
}}
a {{
  color: #006c80;
}}
</style>
</head>
<body>
<div class="page">

<p><a href="index.html">← Back to sea conditions</a></p>

<div class="card">
<h1>Smartwatch Sensor Characterisation Report</h1>
<p><strong>Whitley Bay Multi-Source Sea Temperature Record</strong></p>
<p><em>Bringing together swimmers, satellites and history to understand Whitley Bay's changing sea temperature.</em></p>
<p class="small">Version 0.1 · Generated from <code>water_temperatures.csv</code></p>
</div>

<div class="card">
<h2>Dataset overview</h2>
<table>
<tr><th>Metric</th><th>Value</th></tr>
<tr><td>Raw water temperature observations</td><td>{raw_n:,}</td></tr>
<tr><td>Observation period</td><td>{start_date} to {end_date}</td></tr>
<tr><td>Sessions using 30-minute gap rule</td><td>{session_n:,}</td></tr>
<tr><td>Single-observation sessions</td><td>{single_n:,}</td></tr>
<tr><td>Short sessions, 2–4 readings</td><td>{short_n:,}</td></tr>
<tr><td>Continuous sessions, 5+ readings</td><td>{continuous_n:,}</td></tr>
</table>
</div>

<div class="card">
<h2>Temperature range and high values</h2>
<p>Some high values are unlikely to represent open seawater at Whitley Bay and may be affected by body heat, wetsuit coverage, post-swim activity or other non-sea exposure.</p>
<table>
<tr><th>Metric</th><th>Value</th></tr>
<tr><td>Minimum recorded temperature</td><td>{df["temperature_c"].min():.2f}°C</td></tr>
<tr><td>Maximum recorded temperature</td><td>{df["temperature_c"].max():.2f}°C</td></tr>
<tr><td>Readings ≥20°C</td><td>{high_values:,}</td></tr>
<tr><td>Readings ≥25°C</td><td>{very_high_values:,}</td></tr>
</table>
<img src="reports/charts/raw_temperature_observations.png" alt="Raw smartwatch water temperature observations">
</div>

<div class="card">
<h2>Sampling behaviour</h2>
<table>
<tr><th>Metric</th><th>Value</th></tr>
<tr><td>Median sampling interval</td><td>{median_interval:.1f} seconds</td></tr>
<tr><td>Within-session intervals</td><td>{len(intervals):,}</td></tr>
</table>
<img src="reports/charts/sampling_intervals.png" alt="Sampling interval distribution">
</div>

<div class="card">
<h2>Session duration</h2>
<img src="reports/charts/session_durations.png" alt="Session duration distribution">
</div>

<div class="card">
<h2>Readings per session</h2>
<p>Sessions with only one or a small number of readings should be treated differently from continuous swim recordings where a stable temperature plateau can be identified.</p>
<img src="reports/charts/readings_per_session.png" alt="Readings per session">
</div>

<div class="card">
<h2>Initial interpretation</h2>
<ul>
<li>The smartwatch provides useful in-water temperature observations.</li>
<li>The data should not be treated as a complete diary of all swims.</li>
<li>Recording behaviour may differ between devices or software versions.</li>
<li>High values suggest some readings are affected by body heat or post-swim warming.</li>
<li>The preferred approach is to derive representative seawater temperature from a stable temperature plateau.</li>
</ul>
</div>

<div class="card">
<h2>Next steps</h2>
<ol>
<li>Implement stable plateau detection for continuous sessions.</li>
<li>Assign confidence categories based on readings, duration and plateau quality.</li>
<li>Compare representative smartwatch temperatures with Copernicus SST.</li>
<li>Compare with historical local water temperature records where dates overlap.</li>
<li>Produce a validated <code>smartwatch_sessions.csv</code> dataset.</li>
</ol>
</div>

</div>
</body>
</html>
"""

    report_path.write_text(html, encoding="utf-8")
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

    report_path = make_report(df, sessions, intervals)
    
    print(f"Report written to: {report_path}")
    print(f"Charts written to: {chart_dir}")
    print(f"Diagnostic session CSV written to: {output_dir / 'apple_watch_session_summary_diagnostic.csv'}")


if __name__ == "__main__":
    main()