# 按 s 保存 K230 摄像头图像到电脑

新版在电脑端接收实时 JPEG 并直接保存，不再通过 USB/MTP 文件请求拍照。

1. 在所有 CanMV 窗口中断开开发板连接，释放 USB 串口。保留 USB 线连接。
2. 在电脑终端运行：

       python3 /home/ailing/ballon_dateset/yolo_dataset/capture_calib_host.py

3. 等待预览窗口出现，点击窗口后按 s，或在启动脚本的终端里按 s。
   每按一次保存一张，无需回车。只有文件写入成功才显示完整路径。
   按 q 或 Esc 退出，并自动停止拍照程序、释放串口。

默认保存到 /home/ailing/ballon_dateset/yolo_dataset/calib_dataset。
图片名为 calib_000001.jpg 等，重启后继续编号，不覆盖已有文件。
图片为摄像头原始 640×360 JPEG，没有检测框、文字或 LCD 黑边。
曝光、白平衡、镜像设置沿用当前 YOLO 工程的 config/sensor。
程序自动运行相机代码，不改动 main.py。

本目录的 capture_calib_keys.py 也是电脑端入口，capture_calib.py 是
自动发送给开发板运行的摄像头代码。电脑本地副本位于数据集目录的上一层，
不依赖 USB 文件挂载即可启动。

可选参数：

    # 只通过电脑终端按 s，不打开预览窗口
    python3 /home/ailing/ballon_dateset/yolo_dataset/capture_calib_host.py --no-window

    # 保存一张实时照片后退出，用于检查连接和保存
    python3 /home/ailing/ballon_dateset/yolo_dataset/capture_calib_host.py --no-window --once

    # 改保存目录或指定 USB 串口
    python3 /home/ailing/ballon_dateset/yolo_dataset/capture_calib_host.py --save-dir /path/to/images --port /dev/ttyACM0

电脑端使用已安装的 OpenCV、NumPy 和 CanMV 插件自带的后端，支持当前旧版固件。
如出现 Serial port busy，请在所有 CanMV 窗口断开开发板后重试。
