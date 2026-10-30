"""Camera configuration and capability probing helpers."""

from .sensor_config import (
    apply_sensor_config,
    load_sensor_config,
    probe_sensor_capabilities,
    select_frame_rate,
)

__all__ = [
    "apply_sensor_config",
    "load_sensor_config",
    "probe_sensor_capabilities",
    "select_frame_rate",
]
