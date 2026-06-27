import sys
from pathlib import Path
from datetime import timedelta

import pandas as pd
import matplotlib.pyplot as plt


PROJECT_TITLE = "Whitley Bay Multi-Source Sea Temperature Record"
REPORT_TITLE = "Smartwatch Water Temperature Observations"

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

    df["elapsed_seconds"] = (
        df["timestamp"]
        - df.groupby("session_id")["timestamp"].transform("min")
    ).dt.total_seconds()

    df["elapsed_minutes"] = df["elapsed_seconds"] / 60

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

def save_plot(output_path):
    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close()

def plot_sampling_intervals(intervals, output_path):
    series = intervals.dropna()
    shown = series[series <= 150]
    excluded = len(series) - len(shown)

    plt.figure(figsize=(9, 5))
    plt.hist(shown, bins=30)
    plt.title("Typical sampling intervals within sessions")
    plt.xlabel("Seconds between readings")
    plt.ylabel("Count")
    plt.xlim(0, 150)

    if excluded:
        plt.figtext(
            0.01, 0.01,
            f"Note: {excluded:,} intervals greater than 150 seconds excluded from chart scale.",
            fontsize=9
        )

    save_plot(output_path)

def plot_session_durations(sessions, output_path):
    durations = sessions["duration_minutes"].dropna()
    shown = durations[durations <= 90]
    excluded = len(durations) - len(shown)

    plt.figure(figsize=(9, 5))
    plt.boxplot(shown, vert=False)
    plt.title("Session duration distribution")
    plt.xlabel("Duration (minutes)")

    if excluded:
        plt.figtext(
            0.01, 0.01,
            f"Note: {excluded:,} sessions longer than 90 minutes excluded from chart scale.",
            fontsize=9
        )

    save_plot(output_path)


def plot_readings_per_session(sessions, output_path):
    counts = {
        "Single reading": (sessions["readings"] == 1).sum(),
        "2–4 readings": ((sessions["readings"] >= 2) & (sessions["readings"] <= 4)).sum(),
        "5–14 readings": ((sessions["readings"] >= 5) & (sessions["readings"] <= 14)).sum(),
        "15+ readings": (sessions["readings"] >= 15).sum(),
    }

    plt.figure(figsize=(9, 5))
    plt.barh(list(counts.keys()), list(counts.values()))
    plt.title("Readings per session")
    plt.xlabel("Number of sessions")
    plt.ylabel("Session type")

    save_plot(output_path)

def plot_cooling_curves(df, output_path):
    plt.figure(figsize=(9, 6))

    long_sessions = []

    for _, g in df.groupby("session_id"):
        if len(g) >= 10:
            g = g.sort_values("elapsed_minutes")
            long_sessions.append(g)

            plt.plot(
                g["elapsed_minutes"],
                g["temperature_c"],
                linewidth=0.8,
                alpha=0.25
            )

    if long_sessions:
        combined = pd.concat(long_sessions)

        # Round elapsed time to the nearest minute so sessions can be compared.
        median_curve = (
            combined
            .assign(elapsed_minute_bin=combined["elapsed_minutes"].round(0))
            .groupby("elapsed_minute_bin")["temperature_c"]
            .median()
        )

        plt.plot(
            median_curve.index,
            median_curve.values,
            linewidth=3,
            label="Median curve"
        )

        plt.legend()

    plt.title("Smartwatch cooling behaviour during swim sessions")
    plt.xlabel("Minutes since first reading")
    plt.ylabel("Temperature (°C)")
    plt.xlim(left=0)

    save_plot(output_path)

def plot_monthly_counts(df, output_path):
    monthly = df.set_index("timestamp").resample("ME").size()

    plt.figure(figsize=(8, 4.5))
    monthly.plot(kind="bar")
    plt.title("Water temperature observations by month")
    plt.xlabel("Month")
    plt.ylabel("Observations")
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def plot_temperature_range(df, output_path):
    plt.figure(figsize=(8, 4.5))
    df.plot(x="timestamp", y="temperature_c", kind="scatter", s=8)
    plt.title("Raw Apple Watch water temperature observations")
    plt.xlabel("Date")
    plt.ylabel("Temperature (°C)")
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()

def plot_cooling_curves(df, output_path):
    plt.figure(figsize=(9, 6))

    long_sessions = []

    for _, g in df.groupby("session_id"):
        if len(g) >= 10:
            g = g.sort_values("elapsed_minutes").copy()

            # Normalise each session so first reading = 0°C.
            # This shows sensor cooling behaviour rather than seasonal temperature.
            g["temperature_change_c"] = (
                g["temperature_c"] - g["temperature_c"].iloc[0]
            )

            long_sessions.append(g)

            plt.plot(
                g["elapsed_minutes"],
                g["temperature_change_c"],
                linewidth=0.8,
                alpha=0.25
            )

    if long_sessions:
        combined = pd.concat(long_sessions)

        median_curve = (
            combined
            .assign(elapsed_minute_bin=combined["elapsed_minutes"].round(0))
            .groupby("elapsed_minute_bin")["temperature_change_c"]
            .median()
        )

        plt.plot(
            median_curve.index,
            median_curve.values,
            linewidth=3,
            label="Median change"
        )

        plt.legend()

    plt.axhline(0, linewidth=1)
    plt.title("Smartwatch cooling behaviour during swim sessions")
    plt.xlabel("Minutes since first reading")
    plt.ylabel("Temperature change from first reading (°C)")
    plt.xlim(left=0)

    save_plot(output_path)
    
def plot_temperature_by_reading_number(df, output_path):
    rows = []

    for _, g in df.groupby("session_id"):
        if len(g) >= 10:
            g = g.sort_values("timestamp").copy()
            g["reading_number"] = range(1, len(g) + 1)
            g["temperature_change_c"] = (
                g["temperature_c"] - g["temperature_c"].iloc[0]
            )
            rows.append(g[["reading_number", "temperature_change_c"]])

    plt.figure(figsize=(9, 5))

    if rows:
        combined = pd.concat(rows)

        median_by_reading = (
            combined
            .groupby("reading_number")["temperature_change_c"]
            .median()
            .head(40)
        )

        plt.plot(
            median_by_reading.index,
            median_by_reading.values,
            linewidth=3,
            marker="o"
        )

    plt.axhline(0, linewidth=1)
    plt.title("Median temperature change by reading number")
    plt.xlabel("Reading number within session")
    plt.ylabel("Median change from first reading (°C)")

    save_plot(output_path)

def plot_first_stable_minute (stability, output_path):
    shown = stability["first_stable_minute"].dropna()
    
    plt.figure(figsize=(9, 5) )
    plt.hist(shown, bins=20)
    plt.title("Time to first stable temperature window")
    plt.xlabel("Minutes since first reading")
    plt.ylabel("Sessions")
    save_plot(output_path)

def plot_plateau_variability(stability, output_path):
    shown = stability["median_rolling_range_c"].dropna()
    
    plt.figure(figsize=(9, 5) )
    plt.hist(shown,
    bins=20)
    plt.title("Within-session temperature stability") plt.xlabel("Median rolling 5-reading range (°C)") plt.ylabel("Sessions")
    save_plot(output_path)

def calculate_stability_metrics(df, window=5):
    rows = []

    for session_id, g in df.groupby("session_id"):
        if len(g) < window:
            continue

        g = g.sort_values("timestamp").copy()
        g = g[g["temperature_c"] < 20]

        if len(g) < window:
            continue

        g["rolling_range_c"] = (
            g["temperature_c"]
            .rolling(window=window)
            .max()
            - g["temperature_c"].rolling(window=window).min()
        )

        g["rolling_sd_c"] = (
            g["temperature_c"]
            .rolling(window=window)
            .std()
        )

        g["temp_change_c"] = g["temperature_c"].diff()
        g["time_change_min"] = g["timestamp"].diff().dt.total_seconds() / 60
        g["cooling_rate_c_per_min"] = g["temp_change_c"] / g["time_change_min"]

        stable = g[
            (g["rolling_range_c"] <= 0.3) &
            (g["rolling_sd_c"] <= 0.15)
        ]

        if len(stable):
            first_stable_time = stable["elapsed_minutes"].iloc[0]
            plateau_length = g["elapsed_minutes"].max() - first_stable_time
        else:
            first_stable_time = None
            plateau_length = None

        rows.append({
            "session_id": session_id,
            "readings": len(g),
            "duration_minutes": g["elapsed_minutes"].max(),
            "first_stable_minute": first_stable_time,
            "plateau_length_minutes": plateau_length,
            "median_rolling_range_c": g["rolling_range_c"].median(),
            "median_rolling_sd_c": g["rolling_sd_c"].median(),
        })

    return pd.DataFrame(rows)

def format_percentiles(series):
    p = series.dropna().quantile([0.1, 0.25, 0.5, 0.75, 0.9, 0.95])
    return "\n".join(
        f"- {int(q * 100)}th percentile: **{v:.1f}**"
        for q, v in p.items()
    )

def make_report(df, sessions, intervals, stability):
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

    continuous_pct = (continuous_n / session_n * 100) if session_n else 0
    avg_readings_per_session = raw_n / session_n if session_n else 0
    high_pct = (high_values / raw_n * 100) if raw_n else 0
    very_high_pct = (very_high_values / raw_n * 100) if raw_n else 0
    
    duration_median = sessions["duration_minutes"].median()
    duration_p75 = sessions["duration_minutes"].quantile(0.75)
    duration_p95 = sessions["duration_minutes"].quantile(0.95)

    avg_readings_per_session = raw_n / session_n if session_n else 0
    high_pct = (high_values / raw_n * 100) if raw_n else 0
    very_high_pct = (very_high_values / raw_n * 100) if raw_n else 0

    stable_sessions = stability["first_stable_minute"].notna().sum()
    stable_pct = (stable_sessions / len(stability) * 100) if len(stability) else 0
    
    first_stable_median = stability["first_stable_minute"].median()
    first_stable_p75 = stability["first_stable_minute"].quantile(0.75)
    first_stable_p90 = stability["first_stable_minute"].quantile(0.90)
    
    plateau_range_median = stability["median_rolling_range_c"].median()
    plateau_range_p75 = stability["median_rolling_range_c"].quantile(0.75)
    plateau_range_p90 = stability["median_rolling_range_c"].quantile(0.90)

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
<h1>Smartwatch Water Temperature Observations</h1>
<p><em>Automatically generated analysis of smartwatch-derived water temperature observations.</em></p>
<p class="small">Part of the Whitley Bay Multi-Source Sea Temperature Record.</p>
<p class="badge">Experimental · Version 0.1</p>
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
<h2>Key findings</h2>

<ul>
<li><strong>{raw_n:,}</strong> smartwatch water temperature observations were analysed.</li>
<li>These observations formed <strong>{session_n:,}</strong> swim sessions using a 30-minute gap rule.</li>
<li><strong>{continuous_n:,} sessions ({continuous_pct:.1f}%)</strong> contained five or more readings and provide sufficient observations to investigate stable temperature plateau detection. </li>
<li>The median sampling interval was <strong>{median_interval:.1f} seconds</strong>, providing high temporal resolution within sessions.</li>
<li>The data support deriving <strong>one representative temperature per swim session</strong>, rather than treating observations as independent temperature measurements.</li>
</ul>

<table>
<tr><th>Finding</th><th>Value</th></tr>
<tr><td>Average readings per session</td><td>{avg_readings_per_session:.1f}</td></tr>
<tr><td>Readings ≥20°C</td><td>{high_values:,} ({high_pct:.1f}%)</td></tr>
<tr><td>Readings ≥25°C</td><td>{very_high_values:,} ({very_high_pct:.1f}%)</td></tr>
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

<table>
<tr><th>Metric</th><th>Value</th></tr>
<tr><td>Median duration</td><td>{duration_median:.1f} minutes</td></tr>
<tr><td>75th percentile</td><td>{duration_p75:.1f} minutes</td></tr>
<tr><td>95th percentile</td><td>{duration_p95:.1f} minutes</td></tr>
</table>

<img src="reports/charts/session_durations.png" alt="Session duration distribution">
</div>

<div class="card">
<h2>Readings per session</h2>
<p>Sessions with only one or a small number of readings should be treated differently from continuous swim recordings where a stable temperature plateau can be identified.</p>
<img src="reports/charts/readings_per_session.png" alt="Readings per session">
</div>

<div class="card">
<h2>Sensor cooling behaviour</h2>

<p>
The chart below shows longer swim sessions aligned to the first recorded
temperature measurement. Each session is normalised so that its first reading
starts at 0°C. This shows how the smartwatch sensor changes after entering
the water, rather than showing seasonal differences in sea temperature.
</p>

<img src="reports/charts/cooling_curves.png" alt="Smartwatch cooling behaviour during swim sessions">

<p>
The second chart summarises the median temperature change by reading number.
This helps assess how many readings are typically needed before the sensor
approaches a stable value.
</p>

<img src="reports/charts/temperature_by_reading_number.png" alt="Median temperature change by reading number">
</div>

<div class="card">
<h2>Stability and plateau behaviour</h2>

<p>
This section uses a provisional rolling 5-reading window to investigate when
temperature readings become stable within a swim session. Readings of 20°C or
above are excluded before this analysis.
</p>

<table>
<tr><th>Metric</th><th>Value</th></tr>
<tr><td>Sessions analysed for stability</td><td>{len(stability):,}</td></tr>
<tr><td>Sessions with provisional stable window</td><td>{stable_sessions:,} ({stable_pct:.1f}%)</td></tr>
<tr><td>Median time to first stable window</td><td>{first_stable_median:.1f} minutes</td></tr>
<tr><td>75th percentile time to stability</td><td>{first_stable_p75:.1f} minutes</td></tr>
<tr><td>90th percentile time to stability</td><td>{first_stable_p90:.1f} minutes</td></tr>
<tr><td>Median rolling 5-reading range</td><td>{plateau_range_median:.2f}°C</td></tr>
<tr><td>75th percentile rolling range</td><td>{plateau_range_p75:.2f}°C</td></tr>
<tr><td>90th percentile rolling range</td><td>{plateau_range_p90:.2f}°C</td></tr>
</table>

<img src="reports/charts/first_stable_minute.png" alt="Time to first stable temperature window">

<img src="reports/charts/plateau_variability.png" alt="Plateau variability distribution">

<p>
These values are diagnostic rather than final. Their purpose is to help select
evidence-based thresholds for the stable plateau algorithm.
</p>
</div>

<div class="card">
<h2>Initial interpretation</h2>
<ul>
<li>The smartwatch data are best interpreted at swim-session level, not individual-reading level.</li>
<li>The data should not be treated as a complete diary of all swims.</li>
<li>Recording behaviour may differ between devices or software versions.</li>
<li>High values suggest some readings are affected by body heat or post-swim warming.</li>
<li>Produce a validated <code>smartwatch_sessions.csv</code> dataset containing one representative temperature per swim session.</li>
</ul>
</div>


<div class="card">
<h2>Methodological implications</h2>

<p>
This report demonstrates that smartwatch water temperature observations are best
interpreted as <strong>swim sessions</strong> rather than independent temperature measurements.
</p>

<ul>
<li>Repeated measurements within a swim session provide information about sensor equilibration behaviour.</li>
<li>Representative water temperatures should therefore be derived at the session level rather than from individual observations.</li>
<li>High temperature observations are consistent with body heat or post-swim warming and should not automatically be interpreted as seawater temperature.</li>
<li>The representative water temperature for each swim session will be derived from a stable temperature plateau following sensor equilibration.</li>
<li>Thresholds used within the stable plateau algorithm will be selected using evidence from this sensor characterisation rather than predetermined values.</li>
</ul>

</div>

<div class="card">
<h2>Questions under investigation</h2>

<p>
The purpose of this report is to characterise smartwatch behaviour as a
water temperature sensor and to provide evidence for a reproducible
processing methodology.
</p>

<ol>

<li>How quickly does the smartwatch sensor equilibrate with surrounding seawater?</li>

<li>How stable are temperature observations once thermal equilibrium has been reached?</li>

<li>How many observations are required to estimate a representative session temperature reliably?</li>

<li>Which stable plateau detection method provides the most robust and reproducible representative water temperature?</li>

<li>How closely do representative smartwatch-derived temperatures agree with independent coastal sea temperature observations?</li>

</ol>

</div>

<div class="card">
<h2>Next steps</h2>
<ol>
<li>Characterise smartwatch cooling behaviour.</li>
<li>Quantify time to thermal equilibrium.</li>
<li>Define an evidence-based stable plateau algorithm.</li>
<li>Validate representative temperatures against independent observations.</li>
<li>Publish a reproducible session-level dataset.</li>
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
    stability = calculate_stability_metrics(df, window=5)

    plot_temperature_range(df, chart_dir / "raw_temperature_observations.png")
    plot_monthly_counts(df, chart_dir / "monthly_observations.png")
    plot_sampling_intervals(intervals, chart_dir / "sampling_intervals.png")
    plot_session_durations(sessions, chart_dir / "session_durations.png")
    plot_readings_per_session(sessions, chart_dir / "readings_per_session.png")
    plot_cooling_curves(df, chart_dir / "cooling_curves.png")
    plot_temperature_by_reading_number(
        df,
        chart_dir / "temperature_by_reading_number.png"
    )
    plot_first_stable_minute(
        stability,
        chart_dir / "first_stable_minute.png"
    )
    
    plot_plateau_variability(
        stability,
        chart_dir / "plateau_variability.png"
    )
    
    
    sessions.to_csv(output_dir / "apple_watch_session_summary_diagnostic.csv", index=False)

    report_path = make_report(df, sessions, intervals, stability)
    
    print(f"Report written to: {report_path}")
    print(f"Charts written to: {chart_dir}")
    print(f"Diagnostic session CSV written to: {output_dir / 'apple_watch_session_summary_diagnostic.csv'}")


if __name__ == "__main__":
    main()