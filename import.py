#!/usr/bin/env python3
"""
Imports custom formats and quality profiles into arr instances.

Usage:
    python3 import.py

The script will prompt for each API key. Find them at:
    Radarr / Sonarr → Settings → General → Security → API Key
"""

import json
import urllib.request
import urllib.error
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

print("Enter API keys for each instance (Settings → General → Security → API Key)\n")
for instance in INSTANCES:
    key = input(f"  {instance['name']} ({instance['url']}): ").strip()
    if not key:
        print(f"ERROR: No API key provided for '{instance['name']}'. Aborting.")
        raise SystemExit(1)
    instance["api_key"] = key
print()


def api_post(url, api_key, endpoint, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{url}/api/v3/{endpoint}",
        data=body,
        headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def import_instance(instance):
    name    = instance["name"]
    url     = instance["url"]
    api_key = instance["api_key"]

    print(f"\n=== {name} ({url}) ===")

    cfs      = json.loads((SCRIPT_DIR / instance["custom_formats_file"]).read_text())
    profiles = json.loads((SCRIPT_DIR / instance["quality_profiles_file"]).read_text())

    # Import custom formats and build old_id -> new_id map
    id_map   = {}
    errors   = []
    print(f"  Importing {len(cfs)} custom formats...")
    for cf in cfs:
        old_id  = cf["id"]
        cf_copy = {k: v for k, v in cf.items() if k != "id"}
        try:
            result          = api_post(url, api_key, "customformat", cf_copy)
            id_map[old_id]  = result["id"]
        except urllib.error.HTTPError as e:
            errors.append(f"    CF '{cf.get('name')}': {e.code} {e.reason}")

    if errors:
        print("  Warnings:")
        for err in errors:
            print(err)

    # Import quality profiles, remapping custom format IDs
    print(f"  Importing {len(profiles)} quality profiles...")
    for profile in profiles:
        profile_copy = {k: v for k, v in profile.items() if k != "id"}
        for item in profile_copy.get("formatItems", []):
            if item.get("format") in id_map:
                item["format"] = id_map[item["format"]]
        try:
            api_post(url, api_key, "qualityprofile", profile_copy)
            print(f"    ✓ {profile_copy['name']}")
        except urllib.error.HTTPError as e:
            print(f"    ✗ '{profile_copy.get('name')}': {e.code} {e.reason}")

    print(f"  Done.")


if __name__ == "__main__":
    for instance in INSTANCES:
        import_instance(instance)
    print("\nAll done — check your arr instances to verify the profiles look correct.")
