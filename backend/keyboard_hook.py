"""
键盘钩子模块
使用 pynput 监控键盘输入
"""

import os
import sys
import time
import logging
from datetime import datetime
from threading import Thread, Lock
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# 跨平台支持
if sys.platform == "darwin":
    from pynput import keyboard
    from AppKit import NSWorkspace
else:
    logger.warning("Keyboard monitoring is best supported on macOS")


class KeyboardHook:
    """键盘钩子 - 监控按键事件"""

    def __init__(self, on_keystroke: Optional[Callable] = None):
        self.on_keystroke = on_keystroke
        self.listener = None
        self.is_running = False
        self.lock = Lock()

        # 输入法检测
        self.ime_check_interval = 0.5  # 秒
        self.last_ime_check = 0
        self.current_ime = "ABC"
        self._ime_thread = None

    def start(self):
        """启动键盘监控"""
        if self.is_running:
            logger.warning("Keyboard hook already running")
            return

        try:
            from pynput import keyboard

            self.listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release
            )
            self.listener.start()
            self.is_running = True

            # 启动IME检测线程
            self._ime_thread = Thread(target=self._ime_check_loop, daemon=True)
            self._ime_thread.start()

            logger.info("Keyboard hook started")
        except ImportError:
            logger.error("pynput not installed. Run: pip install pynput")
        except Exception as e:
            logger.error(f"Failed to start keyboard hook: {e}")

    def stop(self):
        """停止键盘监控"""
        if self.listener:
            self.listener.stop()
            self.listener = None
        self.is_running = False
        logger.info("Keyboard hook stopped")

    def _on_press(self, key):
        """按键按下回调"""
        try:
            # 获取键名和字符
            key_name = str(key)
            key_char = None
            key_code = 0

            if hasattr(key, 'char') and key.char:
                key_char = key.char
                key_code = key.vk
            elif hasattr(key, 'vk'):
                key_code = key.vk
                key_name = f"Key.vk_{key.vk}"

            # 获取当前应用
            app = self._get_active_app()

            # 获取当前输入法
            ime = self._get_current_ime()

            # 回调
            if self.on_keystroke:
                self.on_keystroke({
                    "key_code": key_code,
                    "key_name": key_name,
                    "key_char": key_char,
                    "input_method": ime,
                    "application": app.get("name", "Unknown"),
                    "window_title": app.get("title", ""),
                    "timestamp": datetime.now()
                })

        except Exception as e:
            logger.error(f"Error in on_press: {e}")

    def _on_release(self, key):
        """按键释放回调"""
        pass

    def _get_active_app(self) -> dict:
        """获取当前活动应用"""
        try:
            if sys.platform == "darwin":
                from AppKit import NSWorkspace
                front_app = NSWorkspace.sharedWorkspace().frontmostApplication()
                return {
                    "name": front_app.localizedName() or "Unknown",
                    "pid": front_app.processIdentifier()
                }
        except:
            pass
        return {"name": "Unknown", "pid": 0}

    def _get_current_ime(self) -> str:
        """获取当前输入法"""
        try:
            if sys.platform == "darwin":
                script = '''
                tell application "System Events"
                    try
                        tell process "WeChat"
                            set imeMarked to value of attribute "AXMarkedText" of text area 1 of window 1
                            if imeMarked is not "" then
                                return "Chinese"
                            end if
                        end tell
                    end try
                    return "ABC"
                end tell
                '''
                import subprocess
                result = subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True,
                    text=True,
                    timeout=0.5
                )
                if "Chinese" in result.stdout:
                    return "拼音"
                return "ABC"
        except:
            pass
        return "ABC"

    def _ime_check_loop(self):
        """IME检测循环"""
        while self.is_running:
            try:
                self.current_ime = self._get_current_ime()
                time.sleep(self.ime_check_interval)
            except:
                pass


# ==================== 演示模式 ====================

def demo_mode():
    """演示模式 - 模拟按键数据"""
    import requests
    import random

    api_url = "http://127.0.0.1:65500/api/keystroke"

    demo_text = "你好世界Hello World这是一个测试This is a test"
    chars = list(demo_text)

    print("🎮 Demo Mode - Simulating keystrokes...")

    for i, char in enumerate(chars):
        data = {
            "key_code": ord(char) if len(char) == 1 else 0,
            "key_name": char,
            "key_char": char,
            "input_method": "拼音" if ord(char) > 127 else "ABC",
            "application": "WeChat",
            "window_title": "微信"
        }

        try:
            requests.post(api_url, json=data, timeout=1)
            print(f"  Sent: {char}")
        except Exception as e:
            print(f"  Error: {e}")

        time.sleep(random.uniform(0.1, 0.3))

    print("✅ Demo complete!")


if __name__ == "__main__":
    # 测试演示模式
    demo_mode()
