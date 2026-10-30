# Sensor 调试配置

`sensor.yaml` 是运行时相机配置。程序启动时会调用 K230 的
`Sensor.list_mode()`，打印相机型号、支持的分辨率和帧率，并计算硬件宣称的
最高 FPS。`requested_fps` 是本次运行希望使用的帧率；如果超过硬件最高值，程序
会打印警告并自动使用最高值。

启动后先让自动白平衡在实际场地光线下稳定 `awb_settle_seconds` 秒，然后关闭
自动白平衡。接着关闭自动曝光并设置 `exposure_us`（单位为微秒）；曝光值会按
相机返回的有效范围自动限制。修改 YAML 后重启 `main.py` 即可生效。

当前工程的 K230 `media.sensor.Sensor` 接口支持
`auto_exposure(False)` + `exposure(value)`。白平衡和曝光控制同时保留了旧版
`set_auto_whitebal` / `set_auto_exposure` 的兼容调用。如果固件没有实现对应
控制，启动日志会明确打印 `unsupported`，便于判断是否需要升级固件。
