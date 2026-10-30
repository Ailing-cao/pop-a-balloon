"""Install this launcher as /sdcard/main.py for power-on startup."""

import sys

APP_DIR = "/sdcard/ballon/deploy_yolo26s"
APP_MAIN = APP_DIR + "/main.py"

if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

print("Autostart:", APP_MAIN)
with open(APP_MAIN, "r") as app_file:
    app_source = app_file.read()

# Execute the entry point as a script, without importing the root main.py.
exec(app_source, {"__name__": "__main__", "__file__": APP_MAIN})
