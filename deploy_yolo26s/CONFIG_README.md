# 模型更换与参数配置

**实际修改 [config/user_config.py](config/user_config.py)。**
模型、预处理、检测阈值、画面尺寸和电控串口都读取这一份配置。
保存后重启开发板生效。使用 CanMV IDE 时，可先软复位再运行主程序，
以便重新加载已导入的配置模块。

## 更换模型

1. 将新模型上传到开发板目录，例如 `/sdcard/ballon/deploy_yolo26s/`。
2. 修改 `MODEL_PATH`，填写模型在开发板上的完整路径。
3. 按训练/导出时的类别顺序修改 `LABELS`。
4. 根据模型的真实张量信息修改 `MODEL_INPUT_SIZE`、
   `MODEL_OUTPUT_SHAPE` 和 `YOLO_OUTPUT_LAYOUT`。
5. 按模型转换/校准时的设置填写 `LETTERBOX_MODE` 和 `LETTERBOX_COLOR`。
6. 使用电控时，将 `CONTROL_TARGET_LABEL` 改为新模型中对应的目标类别名称；
   不需要串口时将 `SERIAL_ENABLED` 改为 `False`。
7. 保存配置，给开发板重新上电；或在 CanMV IDE 中软复位后运行 `main.py`。

例如：新模型输入为 640×640、两类、输出为 `[1, 6, 8400]`，
且使用居中黑色补边时：

```python
MODEL_PATH = "/sdcard/ballon/deploy_yolo26s/new_balloon.kmodel"
LABELS = ["red", "blue"]
MODEL_INPUT_SIZE = [640, 640]
MODEL_OUTPUT_SHAPE = [1, 6, 8400]
YOLO_OUTPUT_LAYOUT = "channels_first"
LETTERBOX_MODE = "center"
LETTERBOX_COLOR = [0, 0, 0]
CONTROL_TARGET_LABEL = "red"
```

这只是参数填写示例，请使用新模型的真实尺寸、类别和输出形状。
当前启用 `/sdcard/ballon/light.kmodel`，输入为 320×320、8 类、
输出为 `[1, 12, 2100]`，类别顺序为 `redballon`、`pink`、`green`、
`blue`、`shallowblue`、`purple`、`brown`、`yellow`。
原 `exp.kmodel` 为 7 类、`[1, 11, 2100]`；切换模型时须同步修改类别和输出形状。

## 常用调参

| 参数 | 含义 |
| --- | --- |
| `CONFIDENCE_THRESHOLD` | 置信度阈值，0~1，越高保留的框越少 |
| `NMS_THRESHOLD` | 重叠框过滤的 IoU 阈值，0~1 |
| `MAX_BOXES` | 每帧最多保留的框数 |
| `RGB888P_SIZE` | 给 AI 的相机图像尺寸，[宽, 高] |
| `DISPLAY_SIZE` | 屏幕尺寸，[宽, 高] |
| `SERIAL_ENABLED` | 是否启用电控串口 |
| `UART_ID`、`TX_PIN`、`RX_PIN`、`BAUDRATE` | 串口号、引脚和波特率 |
| `CONTROL_TARGET_LABEL` | 面积最大的框为此类别时，发送目标数据包 |
| `CONTROL_TARGET_PACKET`、`CONTROL_OTHER_PACKET` | 目标/其他类别的 bytes 数据包 |

默认数据包为二进制单字节 `b"\x00"`、`b"\x01"`。
电控需要 ASCII 字符时，分别改为 `b"0"` 和 `b"1"`。
没有目标时不发送；每帧有多个目标时仅依据面积最大的有效框发送一次。

相机帧率、曝光和白平衡沿用 `config/sensor/` 下的配置。

## 可直接切换的模型格式

- 输入为单张 RGB、NCHW、uint8 图像；归一化已编译进 KModel。
- 单个 float32 输出张量，内容为 `cx, cy, w, h + 每个类别分数`；
  框坐标单位为模型输入图像的像素。
- 输出为 `[1, 4+类别数, 候选框数]` 时使用 `"channels_first"`；
  输出为 `[1, 候选框数, 4+类别数]` 时使用 `"channels_last"`。
- 输出需要 YOLOv8 格式解码及 NMS，无独立 objectness。

端到端检测、分类、分割、多输出、其他坐标格式、float 输入或需要板端
归一化的模型，还需适配推理代码，不能仅靠修改这些配置切换。

启动时会检查类别数与输出通道数是否对应、阈值范围和串口设置。
推理时会检查实际输出形状是否符合配置；配置错误会显示在开发板终端。
终端会打印出错阶段和完整异常栈。初始化屏幕后发生错误时，程序会释放
摄像头和屏幕资源，因此可能表现为屏幕亮一下后熄灭；应以终端报错定位原因。
这些检查不会自动识别模型的归一化方式、类别顺序或坐标语义。

`labels.txt` 和 `model-manifest.json` 是默认 exp.kmodel 的参考资料，
程序不会从中自动读取运行参数。`config/model_config.py` 保留为旧脚本的
兼容入口，以后请统一编辑 `config/user_config.py`。
