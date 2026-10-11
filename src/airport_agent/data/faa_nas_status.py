"""FAA NAS Status: live delay programs, ground stops and closures ("current conditions").

Right now only: no history, so it is never scored and is not part of `airport_metrics`. The XML
groups events by delay type; each event names the airport in an `ARPT` element. The parser keeps
every field of each event, so delay shapes the saved sample lacks (ground stops, ground delay
programs) still come through.
"""

import urllib.request
import xml.etree.ElementTree as ET

SOURCE = "FAA NAS Status"
URL = "https://nasstatus.faa.gov/api/airport-status-information"


def fetch_status(timeout=60):
    """The live status XML as bytes. Network."""
    with urllib.request.urlopen(URL, timeout=timeout) as response:
        return response.read()


def parse_status(xml):
    """{"updated": str, "events": [{"type": ..., "airport": ..., <other fields>}]}. Pure."""
    root = ET.fromstring(xml)
    events = []
    for delay_type in root.iter("Delay_type"):
        name = delay_type.findtext("Name")
        for element in delay_type.iter():
            code = element.findtext("ARPT")
            if code is None:
                continue
            event = {"type": name, "airport": code.strip().upper()}
            for child in element:
                if child.tag != "ARPT" and len(child) == 0 and child.text:
                    event[child.tag.lower()] = child.text.strip()
            events.append(event)
    return {"updated": root.findtext("Update_Time"), "events": events}


def airport_status(status, iata):
    """The events for one airport (IATA code) from `parse_status` output; [] means none listed."""
    code = iata.strip().upper()
    return [event for event in status["events"] if event["airport"] == code]
