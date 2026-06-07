import json
from datetime import datetime, timezone

data = {
    "version": 1,
    "sea_temp_c": 99.9,
    "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    "source": "Python test",
    "location": "Whitley Bay, near PSC",
    "sample_lat": 55.044,
    "sample_lon": -1.445,
    "sample_method": "Nearest valid offshore SST pixel close to Panama Swimming Club"
}

with open("data.json", "w") as f:
    json.dump(data, f, indent=2)
