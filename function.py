import json
import math
import win32api
import win32gui
from cryptography.fernet import Fernet
from pynput.keyboard import Key, KeyCode

# ── 按键映射：pynput key → 统一字符串 ──────────────────────────
_KEY_ALIAS = {
    Key.space: "space",
    Key.enter: "enter",
    Key.tab: "tab",
    Key.backspace: "backspace",
    Key.esc: "esc",
    Key.shift: "shift",
    Key.shift_l: "shift",
    Key.shift_r: "shift",
    Key.ctrl: "ctrl",
    Key.ctrl_l: "ctrl",
    Key.ctrl_r: "ctrl",
    Key.alt: "alt",
    Key.alt_l: "alt",
    Key.alt_r: "alt",
    Key.caps_lock: "caps_lock",
    Key.cmd: "cmd",
    Key.cmd_l: "cmd",
    Key.cmd_r: "cmd",
    Key.up: "up",
    Key.down: "down",
    Key.left: "left",
    Key.right: "right",
    Key.delete: "delete",
    Key.home: "home",
    Key.end: "end",
    Key.page_up: "page_up",
    Key.page_down: "page_down",
    Key.insert: "insert",
}

def key2str(key) -> str:
    """把 pynput 的 key 对象统一成字符串"""
    # 字母/数字等可打印键
    if isinstance(key, KeyCode):
        if key.char:  # 普通字符
            return key.char
        # 没有 char 时，用虚拟键码兜底
        if getattr(key, "vk", None) is not None:
            vk = key.vk
            # 小键盘 0-9
            if 96 <= vk <= 105:
                return f"kp_{vk - 96}"
            return f"vk_{vk}"
        return str(key)

    # 功能键 / 特殊键
    if isinstance(key, Key):
        if key in _KEY_ALIAS:
            return _KEY_ALIAS[key]
        # F1~F24
        name = getattr(key, "name", None) or str(key)
        if name.startswith("f") and name[1:].isdigit():
            return name  # e.g. 'f1'
        # 兜底
        return name.replace("Key.", "") if name.startswith("Key.") else name

    # 兜底
    return str(key)

def is_cursor_visible():
    cursor_info = win32gui.GetCursorInfo()
    if cursor_info[1] != 0:
        return True
    return False

def get_config():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            content = f.read()
            config = json.loads(content)
            return config
    except FileNotFoundError:
        print('配置文件未找到，请检查文件路径是否正确。')
        raise
    except json.JSONDecodeError as e:
        print(f'配置文件格式错误，无法解析JSON数据: {e}')
        raise
    except UnicodeDecodeError as e:
        print(f'解码配置文件时出错: {e}')
        raise

def get_linear_distance(x1, y1, x2, y2):
    return math.sqrt(math.pow(x1 - x2, 2) + math.pow(y1 - y2, 2))

def get_machine_code():
    code = win32api.GetVolumeInformation('C:\\')[1]
    return str(code) if code else '00000000'