"""由用户配置驱动的 letterbox、YOLOv8 格式解码及 NMS。"""

import aidemo
import nncase_runtime as nn
import ulab.numpy as np
from libs.YOLO import YOLOv8

from config.user_config import (
    LETTERBOX_COLOR,
    LETTERBOX_MODE,
    MODEL_OUTPUT_SHAPE,
    YOLO_OUTPUT_LAYOUT,
)


class ExpDetector(YOLOv8):
    """保持 (boxes, class_ids, scores) 输出，供画框和电控串口使用。"""

    def config_preprocess(self, input_image_size=None):
        """RGB888P -> 等比缩放和补边 -> 配置尺寸的 uint8 NCHW 输入。"""
        self._exp_input_size = list(input_image_size or self.rgb888p_size)
        source_width, source_height = self._exp_input_size
        target_width, target_height = self.model_input_size
        self.scale = min(target_width / source_width,
                         target_height / source_height)
        resized_width = max(1, int(round(source_width * self.scale)))
        resized_height = max(1, int(round(source_height * self.scale)))
        if LETTERBOX_MODE == "center":
            self._pad_left = (target_width - resized_width) // 2
            self._pad_top = (target_height - resized_height) // 2
        elif LETTERBOX_MODE == "top_left":
            self._pad_left = 0
            self._pad_top = 0
        else:
            raise ValueError("Unsupported LETTERBOX_MODE: %s" % LETTERBOX_MODE)
        pad_right = target_width - resized_width - self._pad_left
        pad_bottom = target_height - resized_height - self._pad_top

        self.ai2d.set_ai2d_dtype(nn.ai2d_format.NCHW_FMT,
                               nn.ai2d_format.NCHW_FMT, np.uint8, np.uint8)
        self.ai2d.pad([0, 0, 0, 0, self._pad_top, pad_bottom,
                      self._pad_left, pad_right], 0, LETTERBOX_COLOR)
        self.ai2d.resize(nn.interp_method.tf_bilinear,
                         nn.interp_mode.half_pixel)
        self.ai2d.build([1, 3, source_height, source_width],
                        [1, 3, target_height, target_width])

    def postprocess(self, results):
        """移除补边偏移，再调用原生 YOLOv8 解码/NMS/显示坐标映射。"""
        actual_shapes = [list(result.shape) for result in results]
        if len(results) != 1 or tuple(results[0].shape) != tuple(MODEL_OUTPUT_SHAPE):
            raise ValueError("Model output mismatch: expected one %s, got %s" %
                             (MODEL_OUTPUT_SHAPE, actual_shapes))

        # 统一为 [候选框数, 4+类别数]；前四列为 cx, cy, w, h。
        # 原生后处理按左上角对齐的 letterbox 映射框坐标，因此先去掉
        # 居中补边偏移，否则检测框在屏幕上会出现纵向偏移。
        if YOLO_OUTPUT_LAYOUT == "channels_first":
            predictions = results[0][0].transpose().copy()
        elif YOLO_OUTPUT_LAYOUT == "channels_last":
            predictions = results[0][0].copy()
        else:
            raise ValueError("Unsupported YOLO_OUTPUT_LAYOUT: %s" % YOLO_OUTPUT_LAYOUT)
        if self._pad_left:
            predictions[:, 0] = predictions[:, 0] - self._pad_left
        if self._pad_top:
            predictions[:, 1] = predictions[:, 1] - self._pad_top

        source_width, source_height = self._exp_input_size
        target_width, target_height = self.model_input_size
        display_width, display_height = self.display_size
        return aidemo.yolov8_det_postprocess(
            predictions,
            [source_height, source_width],
            [target_height, target_width],
            [display_height, display_width],
            len(self.labels),
            self.conf_thresh,
            self.nms_thresh,
            self.max_boxes_num,
        )
