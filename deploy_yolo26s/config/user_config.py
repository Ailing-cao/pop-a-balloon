"""用户配置：更换模型和调参时编辑本文件，保存后重启开发板生效。

支持单输出、需要 NMS 的 YOLOv8 格式检测模型，输出为 float32 的
cx, cy, w, h 加各类别分数，框坐标单位为模型输入图像的像素。
输入固定为 RGB、NCHW、uint8，归一化须已编译进 KModel。
其他模型格式需另行适配推理代码，不能仅修改下面的参数。
详细步骤及示例见项目根目录 CONFIG_README.md。
"""

# ==================== 1. 模型文件与类别 ====================

# 模型在开发板上的完整路径。上传新模型后修改文件名即可。
# 必须使用 /sdcard/...，不要填写电脑的 /run/user/... 挂载路径。
MODEL_PATH = "/sdcard/ballon/light.kmodel"

# 类别名称及顺序必须与模型训练/导出时一致，不能按名字自行排序。
# 程序实际读取这里；修改 labels.txt 不会改变识别类别配置。
LABELS = [
    "redballon",
    "pink",
    "green",
    "blue",
    "shallowblue",
    "purple",
    "brown",
    "yellow",
]

# ==================== 2. 输入输出与预处理 ====================

# 模型输入尺寸：[宽, 高]。与相机、屏幕分辨率是不同的参数。
MODEL_INPUT_SIZE = [320, 320]

# 模型的真实输出 shape，需依据导出信息填写，不能仅凭输入尺寸推测。
# 当前 light.kmodel 为 [1, 4个框坐标+8类分数, 2100个候选框]。
MODEL_OUTPUT_SHAPE = [1, 12, 2100]

# "channels_first": [1, 4+类别数, 候选框数]（当前模型）
# "channels_last":  [1, 候选框数, 4+类别数]
YOLO_OUTPUT_LAYOUT = "channels_first"

# 补边方式必须与模型转换/校准时一致：
# "center"：居中补边；"top_left"：图像靠左上角，右侧/底部补边。
LETTERBOX_MODE = "center"
LETTERBOX_COLOR = [0, 0, 0]  # 补边颜色 [R, G, B]，每项 0~255

# ==================== 3. 检测阈值 ====================

CONFIDENCE_THRESHOLD = 0.25  # 0~1，越高保留的检测框越少
NMS_THRESHOLD = 0.45        # 0~1，越低重叠框抑制越强
MAX_BOXES = 50             # 每帧最多保留的检测框数，正整数

# ==================== 4. 相机与屏幕 ====================

# 顺序均为 [宽, 高]。模型输入由相机帧等比缩放、补边得到。
# 采集校准图片的 capture_calib.py 也读取 RGB888P_SIZE。
RGB888P_SIZE = [640, 360]
DISPLAY_SIZE = [640, 480]

# 曝光、白平衡、帧率仍在 config/sensor/ 下配置。

# ==================== 5. 电控串口 ====================

SERIAL_ENABLED = True  # 不需要串口输出时改成 False
UART_ID = 1
TX_PIN = 9             # K230 TX -> 电控 RX
RX_PIN = 10            # K230 RX <- 电控 TX；两端 GND 需相连
BAUDRATE = 115200

# 每帧只选择面积最大的有效框。该框标签等于此名称时发目标包，
# 其他类别发其他包，没有检测框时不发包。
# 更换模型类别名称后，请同步修改此项；必须是 LABELS 中的名称。
CONTROL_TARGET_LABEL = "redballon"

# 默认发送单字节二进制 0x00 / 0x01；如需 ASCII 字符，改为 b"0" / b"1"。
# 也可填写电控协议要求的完整 bytes 数据包。
CONTROL_TARGET_PACKET = b"\x00"
CONTROL_OTHER_PACKET = b"\x01"

# ==================== 以下为程序校验，无需修改 ====================


def validate_config():
    """主程序在启动摄像头前调用；报告配置之间的明显冲突。"""
    if not isinstance(MODEL_PATH, str) or not MODEL_PATH.startswith("/sdcard/"):
        raise ValueError("MODEL_PATH 必须是开发板上的 /sdcard/... 路径")
    if not MODEL_PATH.endswith(".kmodel"):
        raise ValueError("MODEL_PATH 必须指向 .kmodel 文件")
    if not isinstance(LABELS, (list, tuple)) or not LABELS:
        raise ValueError("LABELS 必须是非空类别列表")
    for index, label in enumerate(LABELS):
        if not isinstance(label, str) or not label or label in LABELS[:index]:
            raise ValueError("LABELS 必须包含互不重复的非空类别名称")
    for name, size in (("MODEL_INPUT_SIZE", MODEL_INPUT_SIZE),
                       ("RGB888P_SIZE", RGB888P_SIZE),
                       ("DISPLAY_SIZE", DISPLAY_SIZE)):
        if (not isinstance(size, (list, tuple)) or len(size) != 2
                or any(type(value) is not int or value <= 0 for value in size)):
            raise ValueError(name + " 必须是 [正整数宽度, 正整数高度]")
    if YOLO_OUTPUT_LAYOUT not in ("channels_first", "channels_last"):
        raise ValueError("YOLO_OUTPUT_LAYOUT 只能是 channels_first 或 channels_last")
    if (not isinstance(MODEL_OUTPUT_SHAPE, (list, tuple))
            or len(MODEL_OUTPUT_SHAPE) != 3
            or any(type(value) is not int or value <= 0
                   for value in MODEL_OUTPUT_SHAPE)):
        raise ValueError("MODEL_OUTPUT_SHAPE 必须包含三个正整数")
    channel_axis = 1 if YOLO_OUTPUT_LAYOUT == "channels_first" else 2
    if (MODEL_OUTPUT_SHAPE[0] != 1
            or MODEL_OUTPUT_SHAPE[channel_axis] != 4 + len(LABELS)):
        raise ValueError("模型输出 batch 必须为 1，通道数必须为 4 + 类别数")
    if LETTERBOX_MODE not in ("center", "top_left"):
        raise ValueError("LETTERBOX_MODE 只能是 center 或 top_left")
    if (not isinstance(LETTERBOX_COLOR, (list, tuple)) or len(LETTERBOX_COLOR) != 3
            or any(type(value) is not int or not 0 <= value <= 255
                   for value in LETTERBOX_COLOR)):
        raise ValueError("LETTERBOX_COLOR 必须是三个 0~255 的整数")
    for name, value in (("CONFIDENCE_THRESHOLD", CONFIDENCE_THRESHOLD),
                        ("NMS_THRESHOLD", NMS_THRESHOLD)):
        if not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise ValueError(name + " 必须在 0~1 之间")
    if type(MAX_BOXES) is not int or MAX_BOXES <= 0:
        raise ValueError("MAX_BOXES 必须是正整数")
    if type(SERIAL_ENABLED) is not bool:
        raise ValueError("SERIAL_ENABLED 必须是 True 或 False")
    if SERIAL_ENABLED:
        for name, value in (("UART_ID", UART_ID), ("TX_PIN", TX_PIN),
                            ("RX_PIN", RX_PIN), ("BAUDRATE", BAUDRATE)):
            if type(value) is not int or value < 0:
                raise ValueError(name + " 必须是非负整数")
        if BAUDRATE == 0 or TX_PIN == RX_PIN:
            raise ValueError("BAUDRATE 必须大于 0，TX_PIN 和 RX_PIN 必须不同")
        if CONTROL_TARGET_LABEL not in LABELS:
            raise ValueError("CONTROL_TARGET_LABEL 必须是 LABELS 中的类别名称")
        for packet in (CONTROL_TARGET_PACKET, CONTROL_OTHER_PACKET):
            if not isinstance(packet, bytes) or not packet:
                raise ValueError("电控数据包必须是非空 bytes，例如 b'0'")
