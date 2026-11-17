# arr-quality-profiles

Quality profiles and custom formats for Radarr and Sonarr, exported as JSON, with two scripts to load them into a new server or refresh them from a running one.

The profiles are built for a streaming library (Usenet through a WebDAV mount, played in Jellyfin). File size is not a concern, so the scoring favours the best audio and the best release groups. Custom format names follow [TRaSH Guides](https://trash-guides.info/).

Exported from Radarr 6.x and Sonarr 4.x on 2026-05-21. The live server still matched these files on 2026-11-16.

## Profiles

| Instance | Port | Profile | Files |
| --- | --- | --- | --- |
| radarr | 7878 | Remux + WEB 1080p | `radarr.json`, `radarr-customformats.json` (57 custom formats) |
| radarr4k | 7879 | WEB 2160p | `radarr4k.json`, `radarr4k-customformats.json` (59) |
| sonarr | 8989 | WEB-1080p (Alternative), [Anime] Remux-1080p | `sonarr.json`, `sonarr-customformats.json` (67) |
| sonarr4k | 8990 | WEB-2160p (Alternative) | `sonarr4k.json`, `sonarr4k-customformats.json` (63) |

Every profile has upgrades on and an upgrade-until score of 10000. In practice a title keeps upgrading whenever a release with a higher score appears.

Every profile blocks these with a score of -10000: `BR-DISK`, `LQ`, `LQ (Release Title)`, `Extras`. Keep `BR-DISK` blocked: disc images do not play from a streaming mount.

### Radarr: Remux + WEB 1080p

- **Qualities, low to high:** WEB 720p, Bluray-720p, WEB 1080p, Bluray-1080p, Remux-1080p
- **Cutoff:** Bluray-1080p
- **Minimum score:** 0
- **Language:** Original

| Score | Custom formats |
| --- | --- |
| 5000 to 2000 | Lossless and object audio: TrueHD ATMOS (5000), DTS X (4500), ATMOS (undefined) and DD+ ATMOS (3000), TrueHD (2750), DTS-HD MA (2500), FLAC and PCM (2250), DTS-HD HRA (2000) |
| 1950 to 1850 | Remux Tier 01, 02, 03 |
| 1750 to 750 | Lossy audio: DD+ (1750), DTS-ES (1500), DTS (1250), AAC (1000), DD (750) |
| 1700 to 1600 | WEB Tier 01, 02, 03 |
| 800 | HD Bluray Tier 01, 02 |
| 25 to 5 | Small tie-breakers: Hybrid, HD Bluray Tier 03, CRiT, MA, BCORE, Repack/Proper, Repack2, Repack3 |
| -10000 | 3D, AV1, Generated Dynamic HDR, Sing-Along Versions, x265 (HD), plus the common blocks |

Audio scores are larger than release-group scores. A remux with TrueHD ATMOS always beats a WEB release.

### Radarr 4K: WEB 2160p

- **Qualities, low to high:** WEB 1080p, Bluray-1080p, WEB 2160p
- **Cutoff:** WEB 2160p
- **Minimum score:** 0
- **Language:** Original

There is no 2160p Bluray or Remux in this profile. At 2160p it takes WEB releases only.

Scores are the same as the 1080p profile, with these changes:

| Score | Custom formats |
| --- | --- |
| 1800 to 1700 | HD Bluray and UHD Bluray Tier 01, 02, 03 |
| 500 | HDR |
| 100 | HDR10+ Boost |
| -10000 | DV (w/o HDR fallback), Upscaled, x265 (no HDR/DV), 3D, AV1, Generated Dynamic HDR, plus the common blocks |

`DV (w/o HDR fallback)` is blocked because a client without Dolby Vision shows wrong colours on those files.

### Sonarr: WEB-1080p (Alternative)

- **Qualities, low to high:** SDTV, DVD, Bluray-480p, WEB 480p, Bluray-576p, HDTV-720p, Bluray-720p, WEB 720p, HDTV-1080p, Bluray-1080p, WEB 1080p
- **Cutoff:** WEB 1080p
- **Minimum score:** 0

WEB 1080p ranks above Bluray-1080p. That is the "Alternative" in the name.

| Score | Custom formats |
| --- | --- |
| 1700 to 1600 | ATVP (1700), CC (1650), WEB Scene and WEB Tier 03 (1600) |
| 1400 to 500 | Anime BD Tier 01 to 08, Anime Web Tier 01 and 02 |
| 75 | Streaming services: AMZN, NF, DSNP, HMAX, MAX, HULU and others |
| 10 | Season Pack |
| 7 to 1 | Repacks and anime version tags |
| -10000 | Anime Raws, Dubs Only, PMTP, x265 (HD), plus the common blocks |

### Sonarr: [Anime] Remux-1080p

- **Qualities, low to high:** SDTV, DVD, WEB 480p, Bluray-480p, WEB 720p, Bluray-720p, WEB 1080p, Bluray 1080p (includes Remux)
- **Cutoff:** Bluray 1080p
- **Minimum score:** 100

This profile wants English audio.

| Score | Custom formats |
| --- | --- |
| 10000 | Anime Dual Audio, Dubs Only |
| 1600 | WEB Scene |
| 1400 to 700 | Anime BD Tier 01 to 08 |
| 600 to 500 | Anime Web Tier 01, 02 |
| 1050 to 75 | Streaming services |
| -10000 | Not English Audio, Anime Raws, Bad Dual Groups, VOSTFR, PMTP, x265 (HD), plus the common blocks |

### Sonarr 4K: WEB-2160p (Alternative)

- **Qualities, low to high:** every quality from SDTV to WEB 1080p, then Bluray-2160p, WEB 2160p
- **Cutoff:** WEB 2160p
- **Minimum score:** 0

| Score | Custom formats |
| --- | --- |
| 1700 to 1600 | WEB Tier 01, 02, 03, WEB Scene |
| 700 to 100 | Anime tiers |
| 500 | HDR |
| 100 | HDR10+ Boost, Hybrid |
| 75 | Streaming services, UHD Streaming Boost, HD Streaming Boost |
| -10000 | DV (w/o HDR fallback), AV1, x265 (HD), Anime LQ Groups, Anime Raws, plus the common blocks |

## Import into a new server

You need Python 3. The scripts use no extra packages. Run them on the machine where the arrs listen on `localhost`.

```bash
git clone https://github.com/beanbaganalytica/arr-quality-profiles
python3 arr-quality-profiles/import.py
```

The script asks for the API key of each instance. Find it under **Settings → General → Security → API Key**.

For each instance it creates the custom formats, then the profiles. Custom format IDs differ between servers, so the script maps the old IDs to the new ones.

If your ports differ, edit the `INSTANCES` list at the top of `import.py`.

After the import:

1. Delete the default profiles (`Any`, `HD-1080p`, and so on).
2. Select the new profile on each root folder, list and request tool.

## Export after a change

Change profiles in the arr UI, then save them here:

```bash
cd /opt/quality-profiles
python3 export.py
git add -A && git commit -m "update profiles"
git push
```

`export.py` overwrites the JSON files with the live state.

## Limits

- **Import only creates.** Run it on a fresh instance. On a second run, each custom format that already exists fails with an error, and its score can attach to the wrong format in the profile. To update an existing server, change it in the UI.
- **Four instances only.** The Spanish instances (`radarrES`, `sonarrES`) are not exported yet.
- **Quality definitions are not included.** These are the size limits per quality under **Settings → Quality**. Set them by hand.
- **Naming is not included.** Set the file and folder format by hand under **Settings → Media Management**.
