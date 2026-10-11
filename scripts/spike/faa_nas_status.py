"""Spike: fetch FAA NAS Status (live delays, ground stops, closures) and save a sample.

The answer is XML and describes only "right now"; there is no history.
Run: uv run python scripts/spike/faa_nas_status.py
"""

import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

URL = "https://nasstatus.faa.gov/api/airport-status-information"
OUT = Path("data/samples/faa_nas_status.xml")

with urllib.request.urlopen(URL, timeout=60) as response:
    body = response.read()

root = ET.fromstring(body)
print("Updated:", root.findtext("Update_Time"))
for delay_type in root.iter("Delay_type"):
    airports = [a.findtext("ARPT") for a in delay_type.iter("Airport")]
    print(f"  {delay_type.findtext('Name')}: {', '.join(airports) or '(see XML)'}")
OUT.write_bytes(body)
print(f"Saved to {OUT} ({len(body)} bytes)")
