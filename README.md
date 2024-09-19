# wp-plugin-zip
A python script that aids in the testing and development of WordPress plugins by automating the packaging of a testable plugin zip file.

# Features
- Supports quick packaging of plugins using profiles
- Removes directories and files that should not be included plugin zip folder
- Automatic naming with versions with timestamps

# How It Works
1. Download the repo. 
2. Make a copy of plugin_profiles.txt and rename it to plugin_profiles.txt.
3. Input the plugin information into the plugin_profiles.txt file (optional).
4. Run the python script by using the command: `python wp-plugin.py`
5. The script will create a zip file in the output directory.

# Change Log
- 1.0.0 - Initial release