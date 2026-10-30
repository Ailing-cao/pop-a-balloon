# 默认 exp.kmodel 部署与推理

默认运行 `main.py`，加载 `/sdcard/ballon/deploy_yolo26s/exp.kmodel`。
更换模型及调参请编辑 `config/user_config.py`，步骤见 `CONFIG_README.md`。
电脑上的 `/run/user/1000/gvfs/.../exp.kmodel` 是同一文件的挂载路径，
开发板推理必须使用 `/sdcard/...` 路径。

## 模型参数

| 参数 | 当前值 |
| --- | --- |
| KModel 输入 | 单个张量，`uint8 [1,3,320,320]`，RGB、NCHW |
| KModel 输出 | 单个张量，`float32 [1,11,2100]` |
| 输出通道 | `cx, cy, w, h` + 7 类分数，无独立 objectness |
| 类别顺序 | redballon、pink、green、blue、shallowblue、purple、brown |
| 预处理 | 等比缩放、居中补黑边；原始 uint8 像素 |
| 归一化 | `/255` 已在 KModel 内部，无需在板端重复处理 |
| 后处理 | YOLOv8 格式解码、NMS，再映射至屏幕坐标 |
| 置信度阈值 | 0.25 |
| NMS IoU 阈值 | 0.45 |
| 最大检测框数 | 50 |
| 相机给 AI 的图像尺寸 | 640×360 |
| 屏幕配置 | 640×480 |

这些参数集中在 `config/user_config.py`。`config/model_config.py` 仅保留为
旧导入路径的兼容入口。采集校准图像的
`capture_calib.py` 也读取同一份相机尺寸配置。相机帧率、白平衡和曝光
继续由 `config/sensor/sensor_config.py` 及可选的 `sensor.yaml` 控制。
置信度、NMS 阈值和最大框数属于运行参数，未存储在这个 KModel 中。
下文的模型核对和推理记录仅适用于默认 `exp.kmodel`。

## 预处理和框坐标

本地转换脚本使用居中黑色补边生成校准输入。对 640×360 的相机帧，
等比缩放到 320×180，顶部和底部各补 70 像素，形成 320×320 输入。
板端 `exp_detector.py` 使用相同几何关系和颜色。

此模型导出时 `end2end=False`，需要 NMS。程序固定使用
`aidemo.yolov8_det_postprocess`，传入 `[2100,11]` 的连续预测数组。
原生接口按左上角对齐的补边方式恢复坐标，因此先从预测中心坐标中扣除
居中补边偏移，再执行解码及 NMS。最终仍返回
`(boxes, class_ids, scores)`，其中框格式为 `(x,y,w,h)`。

## 电控

波特率为 115200。每帧只按 NMS 后面积最大的有效框发送：
`redballon` 发 `0x00`，其他标签发 `0x01`，无检测框不发送。
目标类别、数据包和串口参数可在 `config/user_config.py` 中修改。
接线和数据包配置见 `SERIAL_README.md`。

## 核对依据

目录中的 `exp.kmodel` 与本地 `/home/ailing/Kmodel/exp.kmodel` 的
SHA-256 完全一致；对应 `/home/ailing/Kmodel/exp.onnx` 提供输入、输出、
标签顺序和导出模式信息。KModel 张量描述核对结果为：
输入 uint8 / 307200 字节，输出 float32 / 92400 字节。
完整参数及文件摘要记录在 `model-manifest.json`。

已用两张实际气球图片完成 K230 模拟器推理，均输出 `[1,11,2100]`
且检出超过 0.25 阈值的候选框；同时通过主程序的模拟串口验证。
预处理配置、补边坐标修正和原生后处理的传入参数已在主机核对，
尚未进行开发板摄像头及电控实机联调。
