"""旧配置导入路径的兼容入口；请实际编辑 config/user_config.py。"""

from config.user_config import *

# 兼容旧脚本的派生参数；输入 shape 自动从 [宽, 高] 生成。
APP_DIR = "/sdcard/ballon/deploy_yolo26s"
MODEL_INPUT_SHAPE = [1, 3, MODEL_INPUT_SIZE[1], MODEL_INPUT_SIZE[0]]
