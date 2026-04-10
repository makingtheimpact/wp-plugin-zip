# wp-plugin-zip

A Python script for packaging WordPress plugins into installable zip files. It helps with testing and release builds by copying the plugin tree (with optional exclusions), producing a clean archive, and keeping a CSV history of each build.

## Features

- **Profiles** — Store plugin paths, output folder, main PHP file, and exclude lists in `plugin_profiles.txt`, or enter everything manually when you run the script.
- **Selective packaging** — Omit configured directories and files (for example `node_modules`, `.git`, lockfiles) from the zip.
- **Stable output name** — Each build writes `{plugin-folder-name}.zip` in the output directory (the folder name is the last segment of the plugin path).
- **Archiving the previous zip** — If that zip already exists, it is renamed before the new build. The archived name uses the **Version:** header read from the main plugin file **inside that zip**, the **sanitized build note** from the last log row for that profile, and the old file’s modification time (`YYYY-MM-DD_HHMM`). Your answer about how that build worked adds an optional suffix: **`_nonworking`**, **`_partial`**, or **`_unsure`** (no suffix if you chose **yes** / working).
- **Build log** — Appends one row per successful build to `wp-plugin-build-log.csv` in the **same directory as the zips** (the profile’s output directory). Older log files are upgraded in place when new columns are added.

## How it works

1. Clone or download the repository.
2. Edit `plugin_profiles.txt` with your plugin entries (optional if you use manual entry at runtime).
3. From the directory that contains `wp-plugin.py` and `plugin_profiles.txt`, run:

   ```bash
   python3 wp-plugin.py
   ```

   On some systems the command is `python wp-plugin.py` instead.

4. Choose a profile or manual entry, then enter a **build note** (free text; a filename-safe slug is derived for archived zips).
5. If a previous `{folder}.zip` is present, the script asks how that **previous packaged version** worked. Reply with **1–4** or **y / n / p / u** (see the on-screen menu).
6. The script copies the plugin to a unique temporary folder under the output directory (name like `wp-plugin-temp-*`), zips it, removes that folder (even if a step fails), and updates the CSV.

### Build log columns

| Column | Purpose |
|--------|---------|
| `build_timestamp` | When the build finished (local timezone, ISO-8601). |
| `plugin_name` | Name from the profile. |
| `plugin_version` | Parsed from the main plugin file’s `Version:` header when possible. |
| `build_note` | The note you entered for this build. |
| `prior_version_working` | Your answer about the **previous** zip (`yes` / `no` / `partially` / `not sure`, or `n/a` if there was no previous zip). |
| `zip_filename` | Name of the new zip (usually `{folder}.zip`). |
| `zip_size_bytes` | Size of the new zip. |
| `zip_sha256` | SHA-256 of the new zip (useful to detect changed outputs). |
| `plugin_source_dir` | Absolute path to the plugin source directory. |

## Requirements

- Python 3 (uses the standard library only).

## Changelog

- **1.1.0** — Build notes, prior-version menu (`1–4` / `y`/`n`/`p`/`u`), archive tags `_nonworking` / `_partial` / `_unsure`, CSV build log with version/hash and schema migration.
- **1.0.0** — Initial release.
