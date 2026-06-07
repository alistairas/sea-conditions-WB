import json
import os
from datetime import datetime, timezone

# Placeholder until we connect the real Copernicus query
# This proves secrets are accessible

username = os.environ.get("COPERNICUS_USERNAME")
password = os.environ.get("COPERNICUS_PASSWORD")

if not username:
    raise Exception("COPERNICUS_USERNAME secret not found")

if not password:
    raise Exception("COPERNICUS_PASSWORD secret not found")

data = {
    "version": 1,
    "sea_temp_c": 11.0,
    "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    "source": "Copernicus authentication test",
    "dataset": "METOFFICE-GLO-SST-L4-NRT-OBS-SST-V2",
    "location": "Whitley Bay, near PSC",
    "sample_lat": 55.044,
    "sample_lon": -1.445,
    "sample_method": "Nearest valid offshore SST pixel close to Panama Swimming Club"
}

with open("data.json", "w") as f:
    json.dump(data, f, indent=2)