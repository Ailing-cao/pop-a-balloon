#!/usr/bin/env python3
"""PC: preview the K230 camera; s saves a JPEG locally, q quits.

Disconnect the board in CanMV first. Its installed backend handles the USB
protocol, including legacy firmware. The camera source is launched
automatically; the board's main.py is never modified.
"""
import argparse
from collections import deque
from contextlib import contextmanager
import json
import os
from pathlib import Path
import queue
import select
import struct
import subprocess
import sys
import termios
import threading
import time
import tty

import cv2
import numpy as np

DEFAULT_SAVE_DIR = Path("/home/ailing/ballon_dateset/yolo_dataset/calib_dataset")
WINDOW = "K230 Camera - s: save / q: quit"


def find_backend():
    candidates = list((Path.home() / ".vscode/extensions").glob(
        "kendryte*.canmv-vscode-*/bin/linux-x64/canmv-backend"))
    if not candidates:
        raise RuntimeError("未找到 CanMV 后端，请先安装 CanMV VS Code 插件。")
    return max(candidates, key=lambda path: path.stat().st_mtime)


class Backend:
    """Client for the installed backend's CM framed JSON/JPEG protocol."""

    def __init__(self, executable):
        self.process = subprocess.Popen(
            [str(executable)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        self.pending = {}
        self.sequence = 0
        self.frame = None
        self.frame_lock = threading.Lock()
        self.logs = deque(maxlen=40)
        self.error = None
        self.board_ready = threading.Event()
        self.capture_ready = threading.Event()
        self.capture_ready_at = None
        self.output_tail = ""
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._read_errors, daemon=True).start()

    def _read_exact(self, size):
        data = bytearray()
        while len(data) < size:
            chunk = self.process.stdout.read(size - len(data))
            if not chunk:
                raise EOFError("CanMV 后端已退出。")
            data.extend(chunk)
        return bytes(data)

    def _read(self):
        try:
            while True:
                magic = self._read_exact(2)
                while magic != b"CM":
                    magic = magic[1:] + self._read_exact(1)
                kind, size = struct.unpack("<BI", self._read_exact(5))
                if size > 50 * 1024 * 1024:
                    raise RuntimeError("CanMV 返回的数据长度异常。")
                payload = self._read_exact(size)
                if kind == 4:
                    jpeg = payload[4:]
                    end = jpeg.rfind(b"\xff\xd9")
                    if jpeg.startswith(b"\xff\xd8") and end >= 2:
                        with self.frame_lock:
                            self.frame = (time.monotonic(), jpeg[:end + 2])
                    continue
                message = json.loads(payload)
                if "id" in message:
                    waiter = self.pending.get(message["id"])
                    if waiter is not None:
                        waiter.put(message)
                elif message.get("event") == "scriptOutput":
                    text = message.get("params", {}).get("text", "").replace("\x00", "")
                    self.logs.append(text)
                    self.output_tail = (self.output_tail + text)[-4096:]
                    if "CAPTURE_READY" in self.output_tail and not self.capture_ready.is_set():
                        self.capture_ready_at = time.monotonic()
                        self.capture_ready.set()
                    if text.strip():
                        print(text, end="", flush=True)
                elif message.get("event") == "boardReady":
                    self.board_ready.set()
                elif message.get("event") == "boardDisconnected":
                    self.error = "开发板 USB 连接已断开。"
        except Exception as error:
            self.error = str(error)
            for waiter in list(self.pending.values()):
                waiter.put({"error": {"message": self.error}})

    def _read_errors(self):
        for line in self.process.stderr:
            self.logs.append(line.decode(errors="replace"))

    def request(self, method, params=None, timeout=20):
        if self.error:
            raise RuntimeError(self.error)
        self.sequence += 1
        request_id = self.sequence
        waiter = queue.Queue()
        self.pending[request_id] = waiter
        try:
            data = json.dumps({"id": request_id, "method": method,
                               "params": params or {}}).encode()
            self.process.stdin.write(b"CM" + struct.pack("<BI", 1, len(data)) + data)
            self.process.stdin.flush()
            try:
                message = waiter.get(timeout=timeout)
            except queue.Empty:
                raise RuntimeError("CanMV 操作超时：" + method) from None
            if "error" in message:
                detail = message["error"].get("message", str(message["error"]))
                if "busy" in detail.lower():
                    detail += "；请在所有 CanMV 窗口中断开开发板，再运行此脚本。"
                raise RuntimeError(detail)
            return message.get("result", {})
        finally:
            self.pending.pop(request_id, None)

    def latest_frame(self):
        with self.frame_lock:
            return self.frame

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            stream.close()


@contextmanager
def terminal_keys():
    settings = None
    fd = None
    if sys.stdin.isatty():
        fd = sys.stdin.fileno()
        settings = termios.tcgetattr(fd)
        tty.setcbreak(fd)
    try:
        yield fd
    finally:
        if settings is not None:
            termios.tcsetattr(fd, termios.TCSADRAIN, settings)


def next_number(directory):
    numbers = [int(path.stem[6:]) for path in directory.glob("calib_*.jpg")
               if path.stem[6:].isdigit()]
    return max(numbers, default=0) + 1


def save_jpeg(directory, number, jpeg):
    while True:
        path = directory / ("calib_%06d.jpg" % number)
        try:
            output = path.open("xb")
        except FileExistsError:
            number += 1
            continue
        try:
            with output:
                output.write(jpeg)
                output.flush()
                os.fsync(output.fileno())
        except Exception:
            path.unlink(missing_ok=True)
            raise
        print("已保存：%s（%d 字节）" % (path, len(jpeg)), flush=True)
        return number + 1


def main():
    parser = argparse.ArgumentParser(description="K230 摄像头预览：s 保存到电脑，q 退出")
    parser.add_argument("--save-dir", type=Path, default=DEFAULT_SAVE_DIR)
    parser.add_argument("--port", help="USB 串口，默认自动检测，例如 /dev/ttyACM0")
    parser.add_argument("--backend", type=Path, help="可选 CanMV 后端可执行文件路径")
    parser.add_argument("--camera-script", type=Path,
                        default=Path(__file__).with_name("capture_calib.py"))
    parser.add_argument("--no-window", action="store_true", help="只用终端按键，不打开预览窗口")
    parser.add_argument("--once", action="store_true", help="保存首个有效实时帧后退出，用于检查相机")
    args = parser.parse_args()
    if args.no_window and not args.once and not sys.stdin.isatty():
        parser.error("无预览窗口时，请在交互式终端运行，以便读取 s 按键。")
    args.save_dir = args.save_dir.expanduser().absolute()
    args.save_dir.mkdir(parents=True, exist_ok=True)
    source = args.camera_script.read_text()
    number = next_number(args.save_dir)
    backend = Backend(args.backend or find_backend())
    connected = False
    camera_started = False
    window_started = False
    try:
        port = args.port
        if not port:
            boards = backend.request("detectBoards").get("boards", [])
            if not boards:
                raise RuntimeError("未检测到 K230，请检查 USB 连接。")
            if len(boards) > 1:
                raise RuntimeError("检测到多个开发板，请用 --port 指定串口。")
            port = boards[0]["port"]
        print("正在连接 %s；请先在 CanMV 中断开开发板。" % port, flush=True)
        info = backend.request("connectBoard", {"port": port, "baudRate": 12000000})
        connected = True
        if info.get("protocolVersion", 0) > 0 and not backend.board_ready.wait(20):
            raise RuntimeError("开发板尚未就绪。")
        backend.request("stopScript")
        backend.request("runScript", {"script": source})
        camera_started = True
        backend.request("startPreview", {"fps": 15})
        print("保存目录：", args.save_dir, flush=True)
        print("等待实时画面；按 s 保存，按 q 或 Esc 退出。", flush=True)
        deadline = time.monotonic() + 25
        last_received = None
        displayed = None
        with terminal_keys() as fd:
            while True:
                if backend.error:
                    raise RuntimeError(backend.error)
                frame = backend.latest_frame()
                # Legacy firmware retains the previous application's JPEG.
                # Only accept frames received after this camera reports ready.
                if (backend.capture_ready.is_set() and frame is not None
                        and frame[0] > backend.capture_ready_at
                        and frame[0] != last_received):
                    image = cv2.imdecode(np.frombuffer(frame[1], np.uint8), cv2.IMREAD_COLOR)
                    if image is not None:
                        if displayed is None:
                            print("相机就绪：%d×%d。" % (image.shape[1], image.shape[0]), flush=True)
                        displayed = frame
                        last_received = frame[0]
                        deadline = time.monotonic() + 10
                        if args.once:
                            save_jpeg(args.save_dir, number, displayed[1])
                            break
                        if not args.no_window:
                            if not window_started:
                                cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
                                window_started = True
                            cv2.imshow(WINDOW, image)
                if time.monotonic() > deadline:
                    raise RuntimeError("未收到有效实时画面，请查看上方开发板输出。")
                key = -1
                if window_started:
                    key = cv2.waitKey(20) & 0xFF
                    if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                        break
                else:
                    time.sleep(0.02)
                if fd is not None and select.select([fd], [], [], 0)[0]:
                    raw = os.read(fd, 1)
                    if raw:
                        key = raw[0]
                    else:
                        break
                if key in (ord("q"), ord("Q"), 27):
                    break
                if key in (ord("s"), ord("S")):
                    if displayed is None or time.monotonic() - displayed[0] > 2:
                        print("尚无有效实时画面，本次未保存。", flush=True)
                        continue
                    try:
                        number = save_jpeg(args.save_dir, number, displayed[1])
                    except OSError as error:
                        print("保存失败：", error, flush=True)
    finally:
        if window_started:
            cv2.destroyAllWindows()
        if connected:
            methods = (["stopPreview", "stopScript"] if camera_started else []) + ["disconnectBoard"]
            for method in methods:
                try:
                    backend.request(method, timeout=5)
                except Exception:
                    pass
        backend.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("已退出。")
    except Exception as error:
        print("错误：", error, file=sys.stderr)
        sys.exit(1)
