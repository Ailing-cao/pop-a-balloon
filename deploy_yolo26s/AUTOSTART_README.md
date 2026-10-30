# 开机自启动

SD 卡根目录的 `/sdcard/main.py` 是开机入口，其源码备份为本目录的
`autostart_main.py`。入口会自动运行
`/sdcard/ballon/deploy_yolo26s/main.py`，启动摄像头、屏幕检测和电控串口。

开发板断电后重新上电即可自动启动，无需在 CanMV IDE 中点击运行。
程序和模型继续保留在当前目录；修改本目录的 `main.py` 或配置后，
下次开机就会使用修改后的文件。

如需停用自启动，将 **SD 卡根目录** 的 `main.py` 重命名为
`main.py.autostart-disabled`，然后重新上电。调试时也可以在 CanMV IDE
中停止当前程序，手动运行本目录的 `main.py`。

重新安装时，将本目录的 `autostart_main.py` 复制到 SD 卡根目录并命名为
`main.py`；已有其他根目录启动程序时，应先备份。
