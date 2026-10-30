"""Camera setup shared by the YOLO demo and sensor debugging.

The K230 firmware used by this project exposes the camera through
``media.sensor.Sensor``.  Older CanMV firmware exposes a module-level
``sensor`` object instead.  This file keeps the configuration in one place
and supports both APIs where the firmware provides them.

``sensor.yaml`` intentionally contains only flat ``key: value`` entries.  A
small parser is used instead of PyYAML because PyYAML is not available in
CanMV MicroPython.  The file can therefore be edited directly on the SD card.
"""

import time


_MODULE_DIR = __file__.rsplit("/", 1)[0]
DEFAULT_CONFIG_PATH = _MODULE_DIR + "/sensor.yaml"

DEFAULTS = {
    "sensor_id": None,
    "requested_fps": 30,
    "exposure_us": 20000,
    "awb_settle_seconds": 2.0,
    "rgb_gain_db": None,
    "hmirror": None,
    "vflip": None,
    "print_modes": True,
}


def _strip_comment(value):
    """Remove a YAML comment without changing quoted ``#`` characters."""
    quoted = None
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quoted == '"':
            escaped = True
            continue
        if char in ("'", '"'):
            if quoted is None:
                quoted = char
            elif quoted == char:
                quoted = None
        elif char == "#" and quoted is None:
            return value[:index].rstrip()
    return value.strip()


def _parse_scalar(value):
    value = _strip_comment(value).strip()
    if not value:
        return None

    if value in ("null", "Null", "NULL", "~"):
        return None
    if value in ("true", "True", "TRUE"):
        return True
    if value in ("false", "False", "FALSE"):
        return False

    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]

    if value.startswith("[") and value.endswith("]"):
        contents = value[1:-1].strip()
        if not contents:
            return []
        return [_parse_scalar(part.strip()) for part in contents.split(",")]

    try:
        return int(value)
    except (TypeError, ValueError):
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def _read_flat_yaml(path):
    """Read the deliberately small, flat YAML subset used by sensor.yaml."""
    values = {}
    with open(path, "r") as config_file:
        for raw_line in config_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            if key and " " not in key and "\t" not in key:
                values[key] = _parse_scalar(value)
    return values


def _validate(config):
    requested_fps = config["requested_fps"]
    if requested_fps is not None:
        if not isinstance(requested_fps, (int, float)) or requested_fps <= 0:
            raise ValueError("requested_fps must be a positive number or null")
        config["requested_fps"] = int(requested_fps)

    exposure_us = config["exposure_us"]
    if exposure_us is not None:
        if not isinstance(exposure_us, (int, float)) or exposure_us <= 0:
            raise ValueError("exposure_us must be positive or null")
        config["exposure_us"] = int(exposure_us)

    settle_seconds = config["awb_settle_seconds"]
    if settle_seconds is None or settle_seconds < 0:
        raise ValueError("awb_settle_seconds must be zero or positive")
    config["awb_settle_seconds"] = float(settle_seconds)

    rgb_gain_db = config["rgb_gain_db"]
    if rgb_gain_db is not None:
        if not isinstance(rgb_gain_db, (list, tuple)) or len(rgb_gain_db) != 3:
            raise ValueError("rgb_gain_db must be [R, G, B] or null")
        config["rgb_gain_db"] = tuple(float(value) for value in rgb_gain_db)

    for key in ("hmirror", "vflip"):
        if config[key] is not None and not isinstance(config[key], bool):
            raise ValueError("%s must be true, false, or null" % key)
    if not isinstance(config["print_modes"], bool):
        raise ValueError("print_modes must be true or false")
    return config


def load_sensor_config(path=None):
    """Load and validate ``sensor.yaml``.

    Missing files fall back to the defaults so a copied ``sensor_config.py``
    remains usable during quick firmware experiments.
    """
    config = dict(DEFAULTS)
    path = path or DEFAULT_CONFIG_PATH
    try:
        values = _read_flat_yaml(path)
    except OSError:
        values = {}
    for key in config:
        if key in values:
            config[key] = values[key]
    return _validate(config)


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _mode_fps(mode):
    if isinstance(mode, dict):
        value = mode.get("fps")
    else:
        value = None
    return value if _number(value) else None


def probe_sensor_capabilities(sensor_id=None):
    """Return the sensor name, supported modes, and maximum advertised FPS.

    ``Sensor.list_mode`` is the hardware/driver capability query on K230.  A
    missing API is reported as an empty result instead of preventing the demo
    from starting; the actual frame rate is read after the pipeline starts.
    """
    result = {
        "sensor_name": None,
        "modes": [],
        "max_fps": None,
        "max_fps_modes": [],
    }
    try:
        from media.sensor import Sensor

        listed = Sensor.list_mode(id=sensor_id)
        if isinstance(listed, tuple) and len(listed) == 2:
            result["sensor_name"], modes = listed
        else:
            modes = listed
        if modes:
            result["modes"] = list(modes)
            fps_values = [_mode_fps(mode) for mode in result["modes"]]
            fps_values = [value for value in fps_values if value is not None]
            if fps_values:
                result["max_fps"] = max(fps_values)
                result["max_fps_modes"] = [
                    mode for mode in result["modes"] if _mode_fps(mode) == result["max_fps"]
                ]
            return result
    except (ImportError, AttributeError, OSError, RuntimeError, TypeError, ValueError) as error:
        result["error"] = repr(error)

    return result


def select_frame_rate(requested_fps, capabilities):
    """Choose a safe FPS and report when the requested value exceeds the max."""
    maximum = capabilities.get("max_fps") if capabilities else None
    if requested_fps is None:
        return int(maximum) if maximum is not None else None
    if maximum is not None and requested_fps > maximum:
        print(
            "requested_fps=%d exceeds the advertised sensor maximum %.2f; using %.2f"
            % (requested_fps, maximum, maximum)
        )
        return int(maximum)
    return int(requested_fps)


def _sleep_seconds(seconds):
    # ``sleep_ms`` is available on CanMV; ``sleep`` keeps this helper testable
    # with CPython and with older MicroPython builds.
    if hasattr(time, "sleep_ms"):
        time.sleep_ms(int(seconds * 1000))
    else:
        time.sleep(seconds)


def _legacy_sensor_module():
    """Return the old module-level sensor API when this firmware provides it."""
    try:
        import sensor as legacy_sensor

        return legacy_sensor
    except ImportError:
        return None


def _candidate_targets(sensor):
    # New K230 firmware uses a Sensor instance.  Older CanMV firmware exposes
    # the same controls as functions on a module-level ``sensor`` object.
    yield sensor
    legacy = _legacy_sensor_module()
    if legacy is not None and legacy is not sensor:
        yield legacy


def _set_awb(sensor, enable, rgb_gain_db=None):
    last_error = None
    for target in _candidate_targets(sensor):
        method = getattr(target, "set_auto_whitebal", None)
        if method is None:
            continue
        try:
            if not enable and rgb_gain_db is not None:
                try:
                    method(False, rgb_gain_db=rgb_gain_db)
                    return "manual_rgb_gain"
                except TypeError:
                    # New media.sensor.Sensor accepts only the enable flag.
                    pass
            method(enable)
            return "set_auto_whitebal"
        except (AttributeError, NotImplementedError, OSError, RuntimeError, TypeError) as error:
            last_error = error
    if last_error is not None:
        raise last_error
    raise AttributeError("camera API does not expose set_auto_whitebal")


def _set_manual_exposure(sensor, exposure_us):
    """Disable AE and set exposure using old or new CanMV method names."""
    last_error = None
    for target in _candidate_targets(sensor):
        auto_exposure = getattr(target, "auto_exposure", None)
        exposure = getattr(target, "exposure", None)
        if auto_exposure is not None:
            try:
                auto_exposure(False)
                if exposure is not None:
                    exposure(exposure_us)
                    return "auto_exposure/exposure"
            except (AttributeError, NotImplementedError, OSError, RuntimeError, TypeError) as error:
                last_error = error

        legacy = getattr(target, "set_auto_exposure", None)
        if legacy is not None:
            try:
                legacy(False, exposure_us=exposure_us)
            except TypeError:
                try:
                    legacy(False)
                    setter = getattr(target, "set_exposure", None)
                    if setter is None:
                        raise
                    setter(exposure_us)
                except (AttributeError, NotImplementedError, OSError, RuntimeError, TypeError) as error:
                    last_error = error
                    continue
            except (AttributeError, NotImplementedError, OSError, RuntimeError) as error:
                last_error = error
                continue
            return "set_auto_exposure"

    if last_error is not None:
        raise last_error
    raise AttributeError("camera API does not expose manual exposure control")


def _clamp_exposure(sensor, exposure_us):
    limits = None
    for target in _candidate_targets(sensor):
        get_range = getattr(target, "get_exposure_time_range", None)
        if get_range is None:
            continue
        try:
            limits = get_range()
            break
        except (AttributeError, NotImplementedError, OSError, RuntimeError, TypeError):
            continue
    if not limits or len(limits) < 2:
        return exposure_us
    low = min(limits[0], limits[1])
    high = max(limits[0], limits[1])
    bounded = max(low, min(high, exposure_us))
    if bounded != exposure_us:
        print("exposure_us=%d outside [%.2f, %.2f]; using %.2f" % (exposure_us, low, high, bounded))
    return bounded


def apply_sensor_config(sensor, config, capabilities=None):
    """Lock AWB after settling, then disable AE and set fixed exposure.

    The function is deliberately called after ``PipeLine.create`` so it also
    works when the pipeline owns the sensor and starts it internally.
    Unsupported controls are logged and returned in ``status``; this makes a
    firmware/API mismatch visible instead of silently claiming that the image
    is locked.
    """
    status = {
        "awb": "not_configured",
        "ae": "not_configured",
        "exposure_us": config.get("exposure_us"),
        "actual_fps": None,
    }

    settle_seconds = config.get("awb_settle_seconds", 2.0)
    try:
        # Keep AWB enabled during the settling interval, then freeze the
        # gains produced by the camera under the actual test lighting.
        _set_awb(sensor, True)
        if settle_seconds:
            print("AWB settling for %.1f s..." % settle_seconds)
            _sleep_seconds(settle_seconds)
        status["awb"] = _set_awb(sensor, False, config.get("rgb_gain_db"))
    except (AttributeError, NotImplementedError, OSError, RuntimeError, TypeError) as error:
        status["awb"] = "unsupported: %s" % error
        print("WARNING: automatic white balance could not be locked: %s" % error)

    exposure_us = config.get("exposure_us")
    if exposure_us is not None:
        try:
            exposure_us = _clamp_exposure(sensor, exposure_us)
            status["exposure_us"] = exposure_us
            status["ae"] = _set_manual_exposure(sensor, exposure_us)
        except (AttributeError, NotImplementedError, OSError, RuntimeError, TypeError, ValueError) as error:
            status["ae"] = "unsupported: %s" % error
            print("WARNING: automatic exposure could not be disabled: %s" % error)

    get_fps = getattr(sensor, "get_framerate", None)
    if get_fps is not None:
        try:
            status["actual_fps"] = get_fps()
        except (OSError, RuntimeError, TypeError, ValueError):
            pass
    print("Sensor controls:", status)
    return status
