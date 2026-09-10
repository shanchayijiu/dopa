# -*- coding: utf-8 -*-
import json
import base64
import os
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import time
import threading

# === 配置：优先从 server_config 导入，失败则使用默认值 ===
try:
    from .server_config import REMOTE_CONFIG_SERVER_URL, ENCRYPTION_KEY, REQUEST_TIMEOUT, DEBUG_MODE
except ImportError:
    REMOTE_CONFIG_SERVER_URL = ''
    ENCRYPTION_KEY = 'ZTX'
    REQUEST_TIMEOUT = 10
    DEBUG_MODE = True

# === 用户信息模块（已禁用，无需操作记录功能） ===
USER_INFO_AVAILABLE = False


class RemoteConfigManager:
    """
    管理远程配置的获取、解密、上传和心跳维持。
    """

    def __init__(self, server_url=None):
        self.server_url = server_url or REMOTE_CONFIG_SERVER_URL
        self.encryption_key = ENCRYPTION_KEY
        self.request_timeout = REQUEST_TIMEOUT
        self.debug_mode = DEBUG_MODE

        self.config_data = None
        self.cfg_file = 'cfg.json'              # 存储解密后的配置
        self.user_cards_id = None

        self._token = None
        self._token_exp = None
        self._token_lock = threading.Lock()
        self._heartbeat_thread = None
        self._heartbeat_stop = threading.Event()
        self._hwid = None

    # ---------- AES（与 PHP 端兼容：AES-CBC + PKCS7；KEY 32 字节；IV 头拼接/固定） ----------
    def _pad_key(self, key: str) -> bytes:
        """
        把文本密钥处理为 32 字节（截断或 0x00 填充），与 PHP 端约定保持一致。
        """
        key_bytes = key.encode('utf-8')
        if len(key_bytes) < 32:
            key_bytes += b'\x00' * (32 - len(key_bytes))
        elif len(key_bytes) > 32:
            key_bytes = key_bytes[:32]
        return key_bytes

    def _encrypt_data(self, data):
        """
        AES-CBC 加密（PKCS7），Base64(iv + ciphertext)
        - data 可为 str / bytes / dict(list)：非 bytes 会转 UTF-8 JSON/字符串
        """
        try:
            key = self._pad_key(self.encryption_key)
            iv = get_random_bytes(16)
            cipher_obj = AES.new(key, AES.MODE_CBC, iv)

            # 统一为 bytes
            if isinstance(data, bytes):
                plain = data
            elif isinstance(data, str):
                plain = data.encode('utf-8')
            else:
                # 允许传 dict/list，自动转 JSON
                plain = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')

            # PKCS7
            pad_len = 16 - (len(plain) % 16)
            padded = plain + bytes([pad_len]) * pad_len

            encrypted = cipher_obj.encrypt(padded)
            return base64.b64encode(iv + encrypted).decode('utf-8')
        except Exception as e:
            print(f"加密失败: {e}")
            return None

    def _decrypt_data(self, encrypted_data: str):
        """
        AES-CBC 解密（PKCS7），输入为 Base64(iv + ciphertext)
        """
        try:
            raw = base64.b64decode(encrypted_data)
            if len(raw) < 16:
                raise ValueError("密文长度异常")
            key = self._pad_key(self.encryption_key)
            iv, ct = raw[:16], raw[16:]
            if len(ct) == 0 or (len(ct) % 16) != 0:
                raise ValueError("密文块大小非法")

            cipher_obj = AES.new(key, AES.MODE_CBC, iv)
            decrypted = cipher_obj.decrypt(ct)
            if not decrypted:
                raise ValueError('解密后数据为空')

            # PKCS7 去填充
            pad_len = decrypted[-1]
            if not (1 <= pad_len <= 16):
                raise ValueError(f"无效的填充长度: {pad_len}")
            if len(decrypted) < pad_len or decrypted[-pad_len:] != bytes([pad_len]) * pad_len:
                raise ValueError('填充验证失败')

            return decrypted[:-pad_len].decode('utf-8')
        except Exception as e:
            print(f"解密失败: {e}")
            return None

    # ---------- 令牌 & 心跳 ----------
    def _parse_jwt_exp(self, token: str):
        """从 JWT token 中解析 exp 字段，失败返回 None。"""
        try:
            parts = token.split('.')
            if len(parts) == 3:
                p = parts[1]
                p += '=' * ((4 - len(p) % 4) & 3)
                payload = json.loads(base64.urlsafe_b64decode(p.encode()).decode())
                return int(payload.get('exp', 0))
        except Exception:
            pass
        return None

    def _apply_token(self, token: str):
        """线程安全地设置 token 和 exp，并同步到 user_info_manager（如可用）。"""
        exp = self._parse_jwt_exp(token)
        with self._token_lock:
            self._token = token
            self._token_exp = exp
        if self.debug_mode:
            exp_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(exp)) if exp else 'unknown'
            left = exp - int(time.time()) if exp else -1
            print(f"[AUTH] 令牌更新: exp={exp_str}, 剩余={left}s")
        if USER_INFO_AVAILABLE:
            try:
                from user_info_manager import user_info_manager
                user_info_manager.set_token(token)
            except Exception:
                pass

    def _set_token_from_response(self, result: dict):
        data = result.get('data', {}) if isinstance(result, dict) else {}
        token = data.get('token')
        if not token:
            return
        self._apply_token(token)

    def _auth_headers(self):
        headers = {'Content-Type': 'application/json'}
        with self._token_lock:
            token = self._token
        if token:
            headers['Authorization'] = f"Bearer {token}"
        if self.debug_mode:
            print(f"[AUTH] 请求携带Authorization: {bool(token)}")
        return headers

    def _start_heartbeat(self):
        # Offline mode: heartbeat disabled
        pass

    def _heartbeat_loop(self):
        # Offline mode: heartbeat disabled
        pass

    def _renew_token(self):
        # Offline mode: token renewal disabled
        pass

    def read_local_cfg(self):
        """读取本地 cfg.json（解密后的配置缓存）。"""
        try:
            if os.path.exists(self.cfg_file):
                with open(self.cfg_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.config_data = config
                    return config
        except Exception as e:
            print(f"读取本地 cfg 失败: {e}")
    # ---------- 远程交互 ----------
    def get_remote_config(self):
        """本地加载配置，不进行网络请求。"""
        if self.debug_mode:
            print("[info] get_remote_config (offline mode)")
        cfg = self.read_local_cfg()
        if cfg:
            self.config_data = cfg
        return cfg

    def upload_config(self, config_data: dict) -> bool:
        """本地保存配置，不进行网络请求。"""
        if self.debug_mode:
            print("[info] upload_config (offline mode)")
        return self.save_config(config_data)

    # ---------- 高层入口 ----------
    def validate_and_load_config(self) -> bool:
        """
        跳过网络验证，直接读取本地cfg.json配置
        """
        print('跳过网络验证，直接加载本地cfg.json配置')
        
        # 优先读取cfg.json文件
        cfg = self.read_local_cfg()
        if not cfg:
            print('cfg.json文件不存在或格式错误，使用默认配置')
            # 如果cfg.json不存在，使用默认配置
            cfg = self.get_default_config()
        
        self.config_data = cfg
        
        # 不启动心跳
        print('网络验证已禁用，程序将直接运行')
        
        return True

    def get_config(self):
        return self.config_data

    def save_config(self, config_data: dict) -> bool:
        """
        保存配置：直接保存到本地 cfg 文件，并更新内存。
        """
        # 跳过网络验证，直接保存到本地
        if self.debug_mode:
            print(f"正在保存配置到本地文件，配置数据大小: {len(json.dumps(config_data, ensure_ascii=False))} 字符")

        try:
            # 始终与 read_local_cfg 使用同一路径；自定义路径时自动创建父目录。
            cfg_dir = os.path.dirname(os.path.abspath(self.cfg_file))
            os.makedirs(cfg_dir, exist_ok=True)
            with open(self.cfg_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=4)
            
            # 更新内存中的配置
            self.config_data = dict(config_data)
            
            if self.debug_mode:
                print('配置已成功保存到本地文件')
            
            return True
        except Exception as e:
            print(f'保存配置到本地文件失败: {e}')
            return False

    def is_config_loaded(self) -> bool:
        return self.config_data is not None


# ---------- 全局封装 ----------
remote_config_manager = RemoteConfigManager()

def init_remote_config(server_url=None):
    if server_url:
        remote_config_manager.server_url = server_url
    return remote_config_manager.validate_and_load_config()

def get_remote_config():
    return remote_config_manager.get_config()

def save_remote_config(config_data):
    return remote_config_manager.save_config(config_data)

def is_remote_config_loaded():
    return remote_config_manager.is_config_loaded()
