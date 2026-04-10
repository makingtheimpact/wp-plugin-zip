import csv
import hashlib
import os
import re
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime

BUILD_LOG_FILENAME = 'wp-plugin-build-log.csv'

BUILD_LOG_FIELDS = [
    'build_timestamp',
    'plugin_name',
    'plugin_version',
    'build_note',
    'prior_version_working',
    'zip_filename',
    'zip_size_bytes',
    'zip_sha256',
    'plugin_source_dir',
]

# Copy plugin files to a temp directory
def copy_plugin_files(plugin_dir, temp_dir, exclude_dirs, exclude_files):
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

    if exclude_dirs == ['none'] and exclude_files == ['none']:
        ignore_patterns = []
    else:
        ignore_patterns = shutil.ignore_patterns(*exclude_dirs, *exclude_files)

    shutil.copytree(plugin_dir, temp_dir, ignore=ignore_patterns)

def sanitize_for_filename(text, max_len=60):
    """Lowercase slug safe for use in zip filenames (no path separators or wildcards)."""
    if not text or not str(text).strip():
        return 'no-note'
    s = text.strip().lower()
    s = re.sub(r'[\s_]+', '-', s)
    s = re.sub(r'[^a-z0-9.-]+', '-', s)
    s = re.sub(r'-+', '-', s).strip('-')
    if not s:
        return 'no-note'
    return s[:max_len].rstrip('-') or 'no-note'

def version_slug_for_filename(version):
    if not version or not str(version).strip():
        return 'v-unknown'
    v = str(version).strip()
    if not v.lower().startswith('v'):
        v = 'v' + v
    v = re.sub(r'[^a-zA-Z0-9._-]', '', v)
    return v or 'v-unknown'

def read_last_build_log_row_for_plugin(log_path, plugin_name):
    if not os.path.isfile(log_path):
        return None
    try:
        with open(log_path, 'r', encoding='utf-8', newline='') as f:
            rows = list(csv.DictReader(f))
    except OSError:
        return None
    for row in reversed(rows):
        if (row.get('plugin_name') or '').strip() == plugin_name:
            return row
    return None

def unique_zip_path(output_dir, base_name):
    """Ensure path does not collide with an existing file."""
    candidate = os.path.join(output_dir, base_name)
    if not os.path.exists(candidate):
        return candidate
    stem, ext = os.path.splitext(base_name)
    n = 2
    while True:
        alt = os.path.join(output_dir, f'{stem}_{n}{ext}')
        if not os.path.exists(alt):
            return alt
        n += 1

# Rename the current plugin-name.zip (only) before a new build.
# Version comes from the main plugin file inside that zip; build note from the last log row.
def rename_existing_zip(
    output_dir,
    zip_stem,
    plugin_name_for_log,
    main_file,
    prior_version_working,
):
    old_file = os.path.join(output_dir, f'{zip_stem}.zip')
    if not os.path.isfile(old_file):
        return

    log_path = os.path.join(output_dir, BUILD_LOG_FILENAME)
    prev = read_last_build_log_row_for_plugin(log_path, plugin_name_for_log)
    ver = extract_plugin_version_from_plugin_zip(old_file, main_file)
    if prev:
        note = (prev.get('build_note') or '').strip()
    else:
        note = ''

    ts = datetime.fromtimestamp(os.path.getmtime(old_file))
    date_part = ts.strftime('%Y-%m-%d_%H%M')
    vpart = version_slug_for_filename(ver)
    npart = sanitize_for_filename(note)
    suffix_map = {
        'yes': '',
        'no': '_nonworking',
        'partially': '_partial',
        'not sure': '_unsure',
    }
    suffix = suffix_map.get(prior_version_working, '')
    new_name = f'{zip_stem}_{vpart}_{date_part}_{npart}{suffix}.zip'
    new_file = unique_zip_path(output_dir, new_name)
    os.rename(old_file, new_file)
    print(f"Renamed existing file {os.path.basename(old_file)} to {os.path.basename(new_file)}")
    tag_hint = {
        '_nonworking': 'Tagged _nonworking (not working); safe to delete if you no longer need it.',
        '_partial': 'Tagged _partial (partially working).',
        '_unsure': 'Tagged _unsure (working status uncertain).',
    }
    if suffix in tag_hint:
        print(tag_hint[suffix])

def prompt_prior_version_working():
    print('Was the previous packaged version working?')
    print('  1 / y — Yes, working')
    print('  2 / n — No, not working')
    print('  3 / p — Partially working')
    print('  4 / u — Not sure')
    while True:
        raw = input('Enter 1–4 or y/n/p/u: ').strip().lower()
        if not raw:
            print('Please enter a number 1–4 or letter y, n, p, or u.')
            continue
        if raw in ('1', 'y', 'yes'):
            return 'yes'
        if raw in ('2', 'n', 'no'):
            return 'no'
        if raw in ('3', 'p', 'partial', 'partially'):
            return 'partially'
        if raw in ('4', 'u', 'not sure', 'notsure', 'unsure', '?'):
            return 'not sure'
        print('Please enter 1–4 or y / n / p / u.')

# Zip the plugin directory
def zip_plugin(plugin_dir, temp_dir, output_dir):
    plugin_name = os.path.basename(os.path.normpath(plugin_dir))
    zip_filename = f"{plugin_name}.zip"
    zip_filepath = os.path.join(output_dir, zip_filename)

    with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, temp_dir)
                zipf.write(file_path, arcname)
    return zip_filepath

def _parse_exclude_list(raw):
    s = (raw or '').strip()
    if not s:
        return ['none']
    items = [x.strip() for x in s.split(',')]
    items = [x for x in items if x]
    return items if items else ['none']

# Load plugin profiles from a text file
def load_plugin_profiles(profile_file):
    profiles = []
    current_profile = {}

    with open(profile_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith("PLUGIN NAME:"):
                if current_profile:  # Save the last profile if one is being processed
                    profiles.append(current_profile)
                    current_profile = {}
                current_profile['plugin_name'] = line.split(":")[1].strip()
            elif line.startswith("PLUGIN DIRECTORY:"):
                current_profile['plugin_dir'] = line.split(":")[1].strip()
            elif line.startswith("OUTPUT DIRECTORY:"):
                current_profile['output_dir'] = line.split(":")[1].strip()
            elif line.startswith("MAIN PLUGIN FILE:"):
                current_profile['main_file'] = line.split(":")[1].strip()
            elif line.startswith("EXCLUDE DIRS:"):
                current_profile['exclude_dirs'] = _parse_exclude_list(line.split(":", 1)[1])
            elif line.startswith("EXCLUDE FILES:"):
                current_profile['exclude_files'] = _parse_exclude_list(line.split(":", 1)[1])

        if current_profile:
            profiles.append(current_profile)

    return profiles

def _version_from_php_text(text):
    m = re.search(
        r'(?:^|\n)\s*\*?\s*Version:\s*([^\r\n]+)',
        text,
        re.MULTILINE | re.IGNORECASE,
    )
    return m.group(1).strip() if m else ''

def _zip_member_for_main_plugin(z, main_file):
    want = os.path.basename((main_file or '').strip())
    if not want:
        return None
    want_lower = want.lower()
    for name in z.namelist():
        if name.endswith('/'):
            continue
        norm = name.replace('\\', '/')
        base = os.path.basename(norm)
        if base == want or base.lower() == want_lower:
            return name
    return None

def extract_plugin_version_from_plugin_zip(zip_path, main_file):
    """Read Version: from the main plugin PHP entry inside the zip (the artifact being archived)."""
    if not os.path.isfile(zip_path):
        return ''
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            member = _zip_member_for_main_plugin(z, main_file)
            if not member:
                return ''
            with z.open(member) as f:
                chunk = f.read(16384).decode('utf-8', errors='replace')
    except (OSError, zipfile.BadZipFile, KeyError, RuntimeError):
        return ''
    return _version_from_php_text(chunk)

def extract_plugin_version(main_file_path):
    if not os.path.isfile(main_file_path):
        return ''
    try:
        with open(main_file_path, 'r', encoding='utf-8', errors='replace') as f:
            chunk = f.read(16384)
    except OSError:
        return ''
    return _version_from_php_text(chunk)

def file_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for block in iter(lambda: f.read(65536), b''):
            h.update(block)
    return h.hexdigest()

def migrate_build_log_schema_if_needed(log_path):
    if not os.path.isfile(log_path):
        return
    with open(log_path, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        old_fields = reader.fieldnames
        if not old_fields:
            return
        if set(BUILD_LOG_FIELDS).issubset(set(old_fields)):
            return
        rows = list(reader)
    with open(log_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=BUILD_LOG_FIELDS, extrasaction='ignore')
        w.writeheader()
        for row in rows:
            out = {}
            for k in BUILD_LOG_FIELDS:
                v = row.get(k)
                out[k] = '' if v is None else v
            w.writerow(out)

def append_build_log(
    output_dir,
    plugin_name,
    plugin_dir,
    main_file,
    zip_filepath,
    build_note,
    prior_version_working,
):
    log_path = os.path.join(output_dir, BUILD_LOG_FILENAME)
    migrate_build_log_schema_if_needed(log_path)
    main_path = os.path.join(plugin_dir, main_file)
    version = extract_plugin_version(main_path)
    zip_size = os.path.getsize(zip_filepath)
    sha = file_sha256(zip_filepath)
    ts = datetime.now().astimezone().isoformat(timespec='seconds')
    row = {
        'build_timestamp': ts,
        'plugin_name': plugin_name,
        'plugin_version': version,
        'build_note': build_note,
        'prior_version_working': prior_version_working,
        'zip_filename': os.path.basename(zip_filepath),
        'zip_size_bytes': zip_size,
        'zip_sha256': sha,
        'plugin_source_dir': os.path.abspath(plugin_dir),
    }
    new_file = not os.path.isfile(log_path)
    with open(log_path, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=BUILD_LOG_FIELDS, extrasaction='ignore')
        if new_file:
            w.writeheader()
        w.writerow(row)

# Select a profile or enter information manually
def select_plugin_profile(profiles):
    print("Select a plugin profile or enter information manually:")
    for i, profile in enumerate(profiles):
        print(f"{i + 1}. {profile['plugin_name']}")

    manual_option = len(profiles) + 1
    print(f"{manual_option}. Enter plugin information manually")

    while True:
        raw = input("Enter your choice: ").strip()
        if not raw:
            print("Please enter a number.")
            continue
        try:
            num = int(raw, 10)
        except ValueError:
            print(f"Invalid input; enter a number from 1 to {manual_option}.")
            continue
        if not 1 <= num <= manual_option:
            print(f"Please enter a number from 1 to {manual_option}.")
            continue
        choice = num - 1
        break

    if 0 <= choice < len(profiles):
        return profiles[choice]
    else:
        plugin_dir = str(input('Path to the plugin directory (/path/to/your/plugin): '))
        output_dir = str(input('Location to save zip file (/path/to/output/directory): '))
        main_file = str(input('Main plugin file name with extension: '))
        exclude_dirs = _parse_exclude_list(
            str(input('Exclude directories (comma-separated or "none" for no exclusion): '))
        )
        exclude_files = _parse_exclude_list(
            str(input('Exclude files (comma-separated or "none" for no exclusion): '))
        )

        return {
            'plugin_name': os.path.basename(plugin_dir),
            'plugin_dir': plugin_dir,
            'output_dir': output_dir,
            'main_file': main_file,
            'exclude_dirs': exclude_dirs,
            'exclude_files': exclude_files,
        }

# Main function
def package_plugin():
    print('*** WP Plugin Generator ***')

    # Load profiles from file
    profile_file = 'plugin_profiles.txt'  # Path to the profile file
    if os.path.exists(profile_file):
        profiles = load_plugin_profiles(profile_file)
    else:
        print(f"Profile file {profile_file} not found.")
        profiles = []

    # Select a profile or enter manually
    profile = select_plugin_profile(profiles)

    build_note = input('Build note: ').strip()

    plugin_dir = profile['plugin_dir']
    output_dir = profile['output_dir']
    main_file = profile['main_file']
    exclude_dirs = profile.get('exclude_dirs', ['none'])
    exclude_files = profile.get('exclude_files', ['none'])
    zip_stem = os.path.basename(os.path.normpath(plugin_dir))
    main_path = os.path.join(plugin_dir, main_file)

    if not os.path.isdir(plugin_dir):
        print(f"Error: Plugin directory does not exist or is not a directory:\n  {plugin_dir}")
        sys.exit(1)
    if not os.path.isdir(output_dir):
        print(f"Error: Output directory does not exist or is not a directory:\n  {output_dir}")
        sys.exit(1)
    if not os.path.isfile(main_path):
        print(f"Error: Main plugin file not found:\n  {main_path}")
        sys.exit(1)

    detected_version = extract_plugin_version(main_path)
    if detected_version:
        print(f"Detected plugin version: {detected_version}")
    else:
        print("Warning: Could not detect plugin version from main plugin file.")

    temp_dir = None
    zip_filepath = None
    try:
        temp_dir = tempfile.mkdtemp(dir=output_dir, prefix='wp-plugin-temp-')

        migrate_build_log_schema_if_needed(os.path.join(output_dir, BUILD_LOG_FILENAME))

        old_zip_path = os.path.join(output_dir, f'{zip_stem}.zip')
        prior_version_working = 'n/a'
        if os.path.isfile(old_zip_path):
            prior_version_working = prompt_prior_version_working()

        # Archive previous plugin-name.zip using version + note from last log row (mtime for date/time)
        rename_existing_zip(
            output_dir,
            zip_stem,
            profile['plugin_name'],
            main_file,
            prior_version_working,
        )

        print(f"Packaging plugin: {profile['plugin_name']}")

        copy_plugin_files(plugin_dir, temp_dir, exclude_dirs, exclude_files)
        zip_filepath = zip_plugin(plugin_dir, temp_dir, output_dir)
    except Exception as exc:
        print(f"Build failed: {exc}")
        raise
    finally:
        if temp_dir is not None and os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

    if zip_filepath and os.path.isfile(zip_filepath):
        append_build_log(
            output_dir,
            profile['plugin_name'],
            plugin_dir,
            main_file,
            zip_filepath,
            build_note,
            prior_version_working,
        )
        print(f"Plugin packaged successfully: {zip_filepath}")
        print(f"Build log updated: {os.path.join(output_dir, BUILD_LOG_FILENAME)}")
    else:
        print("Build failed: packaging did not produce a valid zip file.")
        sys.exit(1)

# Run the packaging script
if __name__ == "__main__":
    package_plugin()
