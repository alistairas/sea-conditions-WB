import json
from pathlib import Path

INPUT_GLOB = "PSC_Log_Vol*_archive.json"
OUTPUT_FILE = Path("historic_temperatures.json")


def normalise_temperature(value):
    if value is None:
        return None, None, "missing"

    if isinstance(value, (int, float)):
        return float(value), str(value), "high"

    raw = str(value).strip()

    if "/" in raw:
        parts = [float(p.strip()) for p in raw.split("/") if p.strip()]
        if parts:
            return sum(parts) / len(parts), raw, "medium"

    if "-" in raw:
        parts = [float(p.strip()) for p in raw.split("-") if p.strip()]
        if parts:
            return sum(parts) / len(parts), raw, "medium"

    try:
        return float(raw), raw, "high"
    except ValueError:
        return None, raw, "review"


def build_historic_temperatures():
    records = []

    for path in sorted(Path(".").glob(INPUT_GLOB)):
        with path.open("r", encoding="utf-8") as f:
            archive = json.load(f)

        volume = archive.get("volume")
        archive_name = archive.get("archive")

        for entry in archive.get("entries", []):
            temp_c, raw_temp, confidence = normalise_temperature(
                entry.get("water_temp_c")
            )

            if temp_c is None:
                continue

            records.append({
                "date": entry.get("date"),
                "date_display": entry.get("date_display"),
                "water_temp_c": round(temp_c, 2),
                "water_temp_raw": raw_temp,
                "source": "psc_logbook",
                "source_detail": entry.get("source"),
                "source_batch": entry.get("source_batch"),
                "archive": archive_name,
                "archive_volume": volume,
                "confidence": confidence,
                "notes": entry.get("notes", "")
            })

    records = sorted(records, key=lambda x: x["date"])

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(records)} historic temperature records to {OUTPUT_FILE}")


if __name__ == "__main__":
    build_historic_temperatures()