"""K230 camera source, started automatically by capture_calib_host.py.

The PC receives clean JPEG preview frames over USB and saves them locally.
"""
import gc
import os
import sys
import time

APP_DIR = "/sdcard/ballon/deploy_yolo26s"
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from config.user_config import RGB888P_SIZE
FRAME_SIZE = tuple(RGB888P_SIZE)

from media.sensor import Sensor
from media.display import Display
from media.media import MediaManager
from config.sensor.sensor_config import (
    apply_sensor_config, load_sensor_config,
    probe_sensor_capabilities, select_frame_rate,
)


def main():
    sensor = None
    display_started = False
    media_started = False
    try:
        config = load_sensor_config()
        capabilities = probe_sensor_capabilities(config["sensor_id"])
        fps = select_frame_rate(config["requested_fps"], capabilities)
        options = {}
        if config["sensor_id"] is not None:
            options["id"] = config["sensor_id"]
        if fps is not None:
            options["fps"] = fps
        sensor = Sensor(**options)
        sensor.reset()
        sensor.set_framesize(width=FRAME_SIZE[0], height=FRAME_SIZE[1])
        sensor.set_pixformat(Sensor.RGB888)
        if config["hmirror"] is not None:
            sensor.set_hmirror(config["hmirror"])
        if config["vflip"] is not None:
            sensor.set_vflip(config["vflip"])

        # Export just the camera frame, without LCD padding or detection boxes.
        Display.init(Display.VIRT, width=FRAME_SIZE[0], height=FRAME_SIZE[1],
                     to_ide=True, quality=95)
        display_started = True
        MediaManager.init()
        media_started = True
        sensor.run()
        apply_sensor_config(sensor, config, capabilities)
        for _ in range(10):
            os.exitpoint()
            sensor.snapshot()
        print("CAPTURE_READY", FRAME_SIZE)
        while True:
            os.exitpoint()
            frame = sensor.snapshot()
            Display.show_image(frame)
            gc.collect()
    except KeyboardInterrupt:
        print("Camera stopped.")
    finally:
        try:
            if sensor is not None:
                sensor.stop()
        finally:
            try:
                if display_started:
                    Display.deinit()
            finally:
                os.exitpoint(os.EXITPOINT_ENABLE_SLEEP)
                time.sleep_ms(100)
                if media_started:
                    MediaManager.deinit()
                gc.collect()


if __name__ == "__main__":
    main()
