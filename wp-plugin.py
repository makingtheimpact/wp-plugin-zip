import os
import shutil
import zipfile
import re
from datetime import datetime

# Get version from the main plugin file (assuming version is in plugin.php)
def get_plugin_version(plugin_dir, plugin_name):
    version_pattern = r"Version:\s*(\d+\.\d+\.\d+)"
    main_plugin_file = os.path.join(plugin_dir, plugin_name)
    
    if not os.path.isfile(main_plugin_file):
        print(f"Error: {main_plugin_file} does not exist.")
        return None
    
    with open(main_plugin_file, 'r') as f:
        content = f.read()
        match = re.search(version_pattern, content)
        if match:
            return match.group(1)
    
    print("Version not found in the main plugin file.")
    return "unknown_version"

# Copy plugin files to a temp directory
def copy_plugin_files(plugin_dir, temp_dir, exclude_dirs, exclude_files):
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    
    if exclude_dirs == ['none'] and exclude_files == ['none']:
        ignore_patterns = []
    else:
        ignore_patterns = shutil.ignore_patterns(*exclude_dirs, *exclude_files)
    
    shutil.copytree(plugin_dir, temp_dir, ignore=ignore_patterns)

# Zip the plugin directory
def zip_plugin(plugin_dir, temp_dir, output_dir, version):
    plugin_name = os.path.basename(os.path.normpath(plugin_dir))
    zip_filename = f"{plugin_name}_v{version}_{datetime.now().strftime('%Y%m%d%H%M')}.zip"
    zip_filepath = os.path.join(output_dir, zip_filename)
    
    with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, temp_dir)
                zipf.write(file_path, arcname)
    return zip_filepath

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
                exclude_dirs = line.split(":")[1].strip()
                current_profile['exclude_dirs'] = exclude_dirs.split(",") if exclude_dirs else ['none']
            elif line.startswith("EXCLUDE FILES:"):
                exclude_files = line.split(":")[1].strip()
                current_profile['exclude_files'] = exclude_files.split(",") if exclude_files else ['none']
        
        if current_profile:
            profiles.append(current_profile)
    
    return profiles

# Select a profile or enter information manually
def select_plugin_profile(profiles):
    print("Select a plugin profile or enter information manually:")
    for i, profile in enumerate(profiles):
        print(f"{i + 1}. {profile['plugin_name']}")
    
    print(f"{len(profiles) + 1}. Enter plugin information manually")
    
    choice = int(input("Enter your choice: ")) - 1
    
    if 0 <= choice < len(profiles):
        return profiles[choice]
    else:
        plugin_dir = str(input('Path to the plugin directory (/path/to/your/plugin): '))
        output_dir = str(input('Location to save zip file (/path/to/output/directory): '))
        main_file = str(input('Main plugin file name with extension: '))
        exclude_dirs = str(input('Exclude directories (comma-separated or "none" for no exclusion): ')).split(",")
        exclude_files = str(input('Exclude files (comma-separated or "none" for no exclusion): ')).split(",")
        
        return {
            'plugin_name': os.path.basename(plugin_dir),
            'plugin_dir': plugin_dir,
            'output_dir': output_dir,
            'main_file': main_file,
            'exclude_dirs': exclude_dirs if exclude_dirs != ['none'] else ['none'],
            'exclude_files': exclude_files if exclude_files != ['none'] else ['none']
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
    
    plugin_dir = profile['plugin_dir']
    output_dir = profile['output_dir']
    main_file = profile['main_file']
    exclude_dirs = profile.get('exclude_dirs', ['none'])
    exclude_files = profile.get('exclude_files', ['none'])
    
    version = get_plugin_version(plugin_dir, main_file)
    if not version:
        return
    
    temp_dir = os.path.join(output_dir, 'temp_plugin')
    
    print(f"Packaging plugin version: {version}")
    
    # Copy files excluding unnecessary ones
    copy_plugin_files(plugin_dir, temp_dir, exclude_dirs, exclude_files)
    
    # Zip the copied files
    zip_filepath = zip_plugin(plugin_dir, temp_dir, output_dir, version)
    
    # Clean up temp directory
    shutil.rmtree(temp_dir)
    
    print(f"Plugin packaged successfully: {zip_filepath}")

# Run the packaging script
if __name__ == "__main__":
    package_plugin()
