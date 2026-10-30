"""K230 与电控的串口通信：每帧仅按面积最大的检测框发送一次。

默认 redballon -> 0x00；其他有效标签 -> 0x01；没有检测框 -> 不发送。
目标类别、数据包、引脚和波特率均在 config/user_config.py 中设置。
检测结果沿用 libs.YOLO 的 (boxes, class_ids, scores)，框为 (x, y, w, h)。
"""

# 实际参数统一在 config/user_config.py 中修改。
from config.user_config import (
    BAUDRATE,
    CONTROL_OTHER_PACKET,
    CONTROL_TARGET_LABEL,
    CONTROL_TARGET_PACKET,
    RX_PIN,
    TX_PIN,
    UART_ID,
)

# 保留旧名称以兼容直接导入这些变量的脚本。
RED_LABEL = CONTROL_TARGET_LABEL
PACKETS = (CONTROL_TARGET_PACKET, CONTROL_OTHER_PACKET)


def select_largest_index(result, labels):
    """返回最大有效框的下标；无目标返回 None，面积相同时选第一个。"""
    if result is None or len(result) == 0:
        return None

    boxes, class_ids = result[0], result[1]
    largest_index = None
    largest_area = 0
    for index in range(len(boxes)):
        class_id = int(class_ids[index])
        if class_id < 0 or class_id >= len(labels):
            continue
        width, height = boxes[index][2], boxes[index][3]
        if width <= 0 or height <= 0:
            continue
        area = width * height
        if area > largest_area:
            largest_index = index
            largest_area = area

    return largest_index


class SerialControl:
    """波特率可配置，8 数据位、无校验、1 停止位；同一标签逐帧发送。"""

    def __init__(self, labels, uart_id=UART_ID, tx_pin=TX_PIN,
                 rx_pin=RX_PIN, baudrate=BAUDRATE):
        from machine import FPIOA, UART

        if tx_pin == rx_pin:
            raise ValueError("UART TX and RX must use different pins")
        self.labels = labels
        self._fpioa = FPIOA()
        self._fpioa.set_function(tx_pin, getattr(FPIOA, "UART%d_TXD" % uart_id))
        self._fpioa.set_function(rx_pin, getattr(FPIOA, "UART%d_RXD" % uart_id))
        self._uart = UART(
            uart_id,
            baudrate=baudrate,
            bits=UART.EIGHTBITS,
            parity=UART.PARITY_NONE,
            stop=UART.STOPBITS_ONE,
        )
        print("Control UART%d: %d baud, TX=IO%d, RX=IO%d, 8N1" %
              (uart_id, baudrate, tx_pin, rx_pin))

    def send_result(self, result):
        """发送最大框对应的包；返回 0/1，无目标则不写串口并返回 None。"""
        index = select_largest_index(result, self.labels)
        if index is None:
            return None

        label = self.labels[int(result[1][index])]
        value = 0 if label == RED_LABEL else 1
        packet = PACKETS[value]
        written = self._uart.write(packet)
        if written != len(packet):
            raise OSError("Control UART packet was not fully written")
        return value

    def deinit(self):
        """退出识别时释放串口。"""
        if self._uart is not None:
            self._uart.deinit()
            self._uart = None
