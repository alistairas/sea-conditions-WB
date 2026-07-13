import csv
from pathlib import Path
from datetime import datetime

HISTORIC_FILE = Path("water_temperatures.csv")
EXISTING_RAW_FILE = Path("data/apple_health_water_temperature_raw.csv")
RECENT_FILE = Path("data/apple_health_water_temperature_recent.csv")
OUTPUT_FILE = Path("data/apple_health_water_temperature_raw.csv")


def clean_header(name):
    return name.strip().replace("\ufeff", "")


def normalise_source(source):
    if not source:
        return ""

    source = source.strip()
    source = source.replace("’", "'")
    return source


def read_csv_rows(path, input_label):
    if not path.exists():
        print(f"Skipping missing file: {path}")
        return []

    rows = []

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            return []

        reader.fieldnames = [clean_header(h) for h in reader.fieldnames]

        for row in reader:
            row = {
                clean_header(k): (
                    v.strip() if isinstance(v, str) else v
                )
                for k, v in row.items()
            }

            date = row.get("Date", "")
            time = row.get("Time", "")
            temp_raw = row.get("Temperature", "")
            source = normalise_source(row.get("Source", ""))

            if not date or not time or not temp_raw:
                continue

            try:
                temp = round(float(temp_raw), 2)
            except ValueError:
                print(f"Skipping invalid temperature in {path}: {temp_raw}")
                continue

            try:
                timestamp = datetime.strptime(
                    f"{date} {time}",
                    "%Y-%m-%d %H:%M:%S"
                )
            except ValueError:
                print(f"Skipping invalid timestamp in {path}: {date} {time}")
                continue

            rows.append({
                "Date": date,
                "Time": time,
                "Temperature": f"{temp:.2f}".rstrip("0").rstrip("."),
                "Source": source,
                "_timestamp": timestamp,
                "_input": input_label,
            })

    return rows


def merge_rows(*row_groups):
    merged = {}

    # Order matters:
    # historic first, then existing cumulative file, then newest Shortcut data.
    # Later rows replace earlier duplicates.
    for rows in row_groups:
        for row in rows:
            key = (
                row["Date"],
                row["Time"],
                row["Temperature"],
            )
            merged[key] = row

    return sorted(
        merged.values(),
        key=lambda r: r["_timestamp"]
    )


def write_output(rows):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8", newline="") as f:
        fieldnames = ["Date", "Time", "Temperature", "Source"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow({
                "Date": row["Date"],
                "Time": row["Time"],
                "Temperature": row["Temperature"],
                "Source": row["Source"],
            })


def main():
    historic_rows = read_csv_rows(HISTORIC_FILE, "historic")
    existing_rows = read_csv_rows(EXISTING_RAW_FILE, "existing_raw")
    recent_rows = read_csv_rows(RECENT_FILE, "recent")

    print(f"Historic rows read: {len(historic_rows)}")
    print(f"Existing cumulative rows read: {len(existing_rows)}")
    print(f"Recent rows read: {len(recent_rows)}")

    merged_rows = merge_rows(
        historic_rows,
        existing_rows,
        recent_rows,
    )

    print(f"Merged rows written: {len(merged_rows)}")

    write_output(merged_rows)


if __name__ == "__main__":
    main()