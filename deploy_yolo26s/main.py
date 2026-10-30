"""CanMV K230 real-time YOLOv8 detection and control UART.

Keep the application files under ``/sdcard/ballon/deploy_yolo26s``.  The
SD-card-root main.py launches this file on boot; it can also run from CanMV
IDE.  User-editable settings live in config/user_config.py.
"""

import sys

# CanMV IDE runs this file with /sdcard as the working directory, so the
# application folder is not on sys.path on its own and ``import config``
# fails.  Add it explicitly, as the official multi-file examples do.
APP_DIR = "/sdcard/ballon/deploy_yolo26s"
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from libs.PipeLine import PipeLine
from serial_control import SerialControl
from exp_detector import ExpDetector as _Detector

from config.user_config import (
    CONFIDENCE_THRESHOLD,
    DISPLAY_SIZE,
    LABELS,
    MAX_BOXES,
    MODEL_INPUT_SIZE,
    MODEL_OUTPUT_SHAPE,
    MODEL_PATH,
    NMS_THRESHOLD,
    RGB888P_SIZE,
    SERIAL_ENABLED,
    validate_config,
)

from config.sensor.sensor_config import (
    apply_sensor_config,
    load_sensor_config,
    probe_sensor_capabilities,
    select_frame_rate,
)

DETECTOR_IMPL = "YOLOv8 dense output + NMS"

import gc
import os
import time


# ``None`` lets CanMV choose the default camera.  The value in
# ``config/sensor/sensor.yaml`` takes precedence when it is set.
SENSOR_ID = None


def _print_sensor_capabilities(capabilities, print_modes):
    """Print the hardware mode table returned by ``Sensor.list_mode``."""
    name = capabilities.get("sensor_name") or "unknown"
    modes = capabilities.get("modes") or []
    maximum = capabilities.get("max_fps")
    print("Camera sensor:", name)
    if maximum is None:
        print("Camera hardware maximum FPS: unavailable")
    else:
        print("Camera hardware maximum FPS: %.2f" % maximum)
    if print_modes:
        for mode in modes:
            print("  mode:", mode)


def main():
    pipeline = None
    detector = None
    serial_control = None
    stage = "configuration"

    try:
        validate_config()
        print("Model config:", MODEL_PATH, "classes=", len(LABELS),
              "input=", MODEL_INPUT_SIZE, "output=", MODEL_OUTPUT_SHAPE)
        stage = "camera configuration"
        sensor_config = load_sensor_config()
        sensor_id = sensor_config["sensor_id"]
        if sensor_id is None:
            sensor_id = SENSOR_ID
        capabilities = probe_sensor_capabilities(sensor_id)
        _print_sensor_capabilities(capabilities, sensor_config["print_modes"])
        frame_rate = select_frame_rate(sensor_config["requested_fps"], capabilities)
        print("Configured capture FPS:", frame_rate)

        pipeline = PipeLine(
            rgb888p_size=RGB888P_SIZE,
            display_mode="lcd",
            display_size=DISPLAY_SIZE,
        )
        create_options = {
            "hmirror": sensor_config["hmirror"],
            "vflip": sensor_config["vflip"],
        }
        if sensor_id is not None:
            create_options["sensor_id"] = sensor_id
        if frame_rate is not None:
            create_options["fps"] = frame_rate
        stage = "camera and display initialization"
        pipeline.create(**create_options)

        # PipeLine owns and starts this Sensor internally.  Apply controls now
        # so the exact object used by inference receives the fixed AWB/AE.
        stage = "sensor controls"
        apply_sensor_config(pipeline.sensor, sensor_config, capabilities)

        display_size = pipeline.get_display_size()
        detector_options = dict(
            task_type="detect",
            mode="video",
            kmodel_path=MODEL_PATH,
            labels=LABELS,
            rgb888p_size=RGB888P_SIZE,
            model_input_size=MODEL_INPUT_SIZE,
            display_size=display_size,
            conf_thresh=CONFIDENCE_THRESHOLD,
            nms_thresh=NMS_THRESHOLD,
            max_boxes_num=MAX_BOXES,
            debug_mode=0,
        )
        stage = "model loading"
        print("Loading model:", MODEL_PATH)
        detector = _Detector(**detector_options)
        stage = "preprocessing initialization"
        detector.config_preprocess()
        if SERIAL_ENABLED:
            stage = "UART initialization"
            serial_control = SerialControl(LABELS)
        print("Detector started:", MODEL_PATH, "implementation=", DETECTOR_IMPL)

        first_frame = True
        while True:
            os.exitpoint()
            stage = "camera capture"
            frame = pipeline.get_frame()
            if frame is None:
                gc.collect()
                continue
            stage = "inference and postprocessing"
            result = detector.run(frame)
            stage = "UART output"
            if serial_control is not None:
                serial_control.send_result(result)
            stage = "display output"
            detector.draw_result(result, pipeline.osd_img)
            pipeline.show_image()
            if first_frame:
                print("First detection frame displayed:", MODEL_PATH)
                first_frame = False
            gc.collect()

    except KeyboardInterrupt:
        print("user stop")
    except BaseException as error:
        print("Detection error:", error, "stage=", stage)
        sys.print_exception(error)
    finally:
        if serial_control is not None:
            serial_control.deinit()
        if detector is not None:
            detector.deinit()
        if pipeline is not None:
            pipeline.destroy()
        gc.collect()
        time.sleep_ms(100)


if __name__ == "__main__":
    main()
