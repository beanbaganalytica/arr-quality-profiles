#!/usr/bin/env python3
"""
Exports custom formats and quality profiles from arr instances to JSON files.

Usage:
    python3 export.py

The script will prompt for each API key. Find them at:
    Radarr / Sonarr → Settings → General → Security → API Key
"""

import json
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

INSTANCES = [
    {
        "name":                  "radarr",
        "url":                   "http://localhost:7878",
        "custom_formats_file":   "radarr-customformats.json",
        "quality_profiles_file": "radarr.json",
    },
    {
        "name":                  "radarr4k",
        "url":                   "http://localhost:7879",
        "custom_formats_file":   "radarr4k-customformats.json",
        "quality_profiles_file": "radarr4k.json",
    },
    {
        "name":                  "sonarr",
        "url":                   "http://localhost:8989",
        "custom_formats_file":   "sonarr-customformats.json",
        "quality_profiles_file": "sonarr.json",
    },
    {
        "name":                  "sonarr4k",
        "url":                   "http://localhost:8990",
        "custom_formats_file":   "sonarr4k-customformats.json",
        "quality_profiles_file": "sonarr4k.json",
    },
]


def api_get(url, api_key, endpoint):
    req = urllib.request.Request(
        f"{url}/api/v3/{endpoint}",
        headers={"X-Api-Key": api_key},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def export_instance(instance):
    name    = instance["name"]
    url     = instance["url"]
    api_key = instance["api_key"]

    print(f"\n=== {name} ({url}) ===")

    cfs = api_get(url, api_key, "customformat")
    cf_path = SCRIPT_DIR / instance["custom_formats_file"]
    cf_path.write_text(json.dumps(cfs, indent=2))
    print(f"  ✓ {len(cfs)} custom formats → {instance['custom_formats_file']}")

    profiles = api_get(url, api_key, "qualityprofile")
    profile_path = SCRIPT_DIR / instance["quality_profiles_file"]
    profile_path.write_text(json.dumps(profiles, indent=2))
    print(f"  ✓ {len(profiles)} quality profiles → {instance['quality_profiles_file']}")


print("Enter API keys for each instance (Settings → General → Security → API Key)\n")
for instance in INSTANCES:
    key = input(f"  {instance['name']} ({instance['url']}): ").strip()
    if not key:
        print(f"ERROR: No API key provided for '{instance['name']}'. Aborting.")
        raise SystemExit(1)
    instance["api_key"] = key
print()

if __name__ == "__main__":
    for instance in INSTANCES:
        export_instance(instance)
    print("\nAll done — JSON files updated in the quality-profiles/ folder.")
