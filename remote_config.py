# -*- coding: utf-8 -*-
import json
import requests
import base64
import os
from cryptography.fernet import Fernet  # 原文件有导入，保留（即便当前未直接使用）
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import hashlib
import time
import threading

# === 配置：优先从 server_config 导入，失败则使用默认值 ===
try:
    from server_config import REMOTE_CONFIG_SERVER_URL, ENCRYPTION_KEY, REQUEST_TIMEOUT, DEBUG_MODE
except ImportError:
    REMOTE_CONFIG_SERVER_URL = 'http://ztx.ztxfkw.top'
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

        self.card_key = None
        self.config_data = None
        self.local_config_file = 'config.json'  # 仅存储 card_key
        self.cfg_file = 'cfg.json'              # 存储解密后的配置
        self.user_cards_id = None

        self._token = None
        self._token_exp = None
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
    def _set_token_from_response(self, result: dict):
        data = result.get('data', {}) if isinstance(result, dict) else {}
        token = data.get('token')
        if not token:
            return
        self._token = token
        try:
            parts = token.split('.')
            if len(parts) == 3:
                p = parts[1]
                p += '=' * ((4 - len(p) % 4) & 3)
                payload = json.loads(base64.urlsafe_b64decode(p.encode()).decode())
                self._token_exp = int(payload.get('exp', 0))
        except Exception:
            self._token_exp = None

        if self.debug_mode:
            exp_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self._token_exp)) if self._token_exp else 'unknown'
            left = self._token_exp - int(time.time()) if self._token_exp else -1
            print(f"[AUTH] 获取令牌: exp={exp_str}, 剩余={left}s")

        if USER_INFO_AVAILABLE:
            try:
                from user_info_manager import user_info_manager
                user_info_manager.set_token(self._token)
            except Exception:
                pass

    def _auth_headers(self):
        headers = {'Content-Type': 'application/json'}
        if self._token:
            headers['Authorization'] = f"Bearer {self._token}"
        if self.debug_mode:
            print(f"[AUTH] 请求携带Authorization: {bool(self._token)}")
        return headers

    def _start_heartbeat(self):
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
        if self.debug_mode:
            print('[HB] 心跳线程已启动')

    def _stop_heartbeat(self):
        self._heartbeat_stop.set()
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=0.1)

    def _heartbeat_loop(self):
        interval = 60
        while not self._heartbeat_stop.is_set():
            try:
                if not self._token:
                    time.sleep(interval)
                    continue
                # 是否接近过期（<5 分钟）
                near = (self._token_exp and self._token_exp - int(time.time()) < 300)
                if self.debug_mode:
                    left = self._token_exp - int(time.time()) if self._token_exp else -1
                    print(f"[HB] {'即将过期，续期' if near else '心跳续期'}，剩余={left}s")
                self._renew_token()
            except Exception as e:
                if self.debug_mode:
                    print(f"[HB] 心跳失败: {e}")
            finally:
                time.sleep(interval)

    def _renew_token(self):
        url = f"{self.server_url}/heartbeat.php"
        response = requests.post(url, json={}, headers=self._auth_headers(), timeout=self.request_timeout)
        response.raise_for_status()
        res = response.json()
        if res.get('success') and res.get('token'):
            self._token = res['token']
            try:
                parts = self._token.split('.')
                if len(parts) == 3:
                    p = parts[1]
                    p += '=' * ((4 - len(p) % 4) & 3)
                    payload = json.loads(base64.urlsafe_b64decode(p.encode()).decode())
                    self._token_exp = int(payload.get('exp', 0))
            except Exception:
                self._token_exp = None
            if self.debug_mode:
                exp_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self._token_exp)) if self._token_exp else 'unknown'
                left = self._token_exp - int(time.time()) if self._token_exp else -1
                print(f"[HB] 续期成功: exp={exp_str}, 剩余={left}s")
            if USER_INFO_AVAILABLE:
                try:
                    from user_info_manager import user_info_manager
                    user_info_manager.set_token(self._token)
                except Exception:
                    pass
        elif self.debug_mode:
            print(f"[HB] 心跳续期失败: {res}")

    # ---------- 本地读写 ----------
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
        return None

    def read_local_card_key(self):
        """从 config.json 读取卡密。"""
        try:
            if os.path.exists(self.local_config_file):
                with open(self.local_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get('card_key', None)
        except Exception as e:
            print(f"读取本地卡密失败: {e}")
        return None

    def save_local_card_key(self, card_key: str) -> bool:
        """把卡密保存到 config.json。"""
        try:
            with open(self.local_config_file, 'w', encoding='utf-8') as f:
                json.dump({'card_key': card_key}, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存本地卡密失败: {e}")
            return False

    def write_local_config(self, card_key: str, config_data: dict) -> bool:
        """把解密后的 cfg 保存到 cfg.json。"""
        try:
            with open(self.cfg_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存本地 cfg 失败: {e}")
            return False

    # ---------- 远程交互 ----------
    def get_remote_config(self, card_key: str):
        """
        拉取并解密服务器配置：
        POST {server}/index.php  { card_key, hwid }
        响应：{ success, config(Base64[AES_CBC(iv+ct)]), data{token?, user_cards_id?}, ... }
        """
        if self.debug_mode:
            print(f"[info] get_remote_config")

        try:
            url = f"{self.server_url}/index.php"
            hwid = None
            try:
                from buff import Buff_Single
                hwid = Buff_Single().GetMacCode()
                if self.debug_mode:
                    print(f"[info] get_remote_config: hwid={hwid}")
            except Exception as e:
                if self.debug_mode:
                    print(f"获取 Buff 机器码失败，回退到系统信息: {e}")
                if USER_INFO_AVAILABLE:
                    try:
                        hwid = get_system_info().get('hwid')
                    except Exception:
                        pass
            if not hwid:
                hwid = 'unknown'
            self._hwid = hwid

            req = {'card_key': card_key, 'hwid': hwid}
            headers = {'Content-Type': 'application/json'}
            if self.debug_mode:
                print(f"[CFG] 请求远程配置: url={url}, hwid={hwid}")

            resp = requests.post(url, json=req, headers=headers, timeout=self.request_timeout)
            resp.raise_for_status()
            result = resp.json()

            if not result.get('success', False):
                print(f"获取配置失败: {result.get('message', '未知错误')}")
                return None

            enc_cfg = result.get('config')
            if not enc_cfg:
                print('服务器返回的配置数据为空')
                return None

            dec = self._decrypt_data(enc_cfg)
            if not dec:
                print('配置解密失败')
                return None

            cfg = json.loads(dec)

            # 卡密一致性校验
            if cfg.get('card_key') != card_key:
                print('配置中的卡密与输入的卡密不一致！')
                return None

            # 令牌
            self._set_token_from_response(result)
            if self.debug_mode:
                print(f"[AUTH] 服务器返回令牌: {'有' if self._token else '无'}")

            # 用户信息
            user_data = result.get('data', {}) or {}
            if 'user_cards_id' in user_data:
                self.user_cards_id = user_data['user_cards_id']
                if USER_INFO_AVAILABLE:
                    init_user_info_manager(card_key, self.user_cards_id, self.server_url)
                    record_config_download()

            # 心跳
            self._start_heartbeat()
            return cfg

        except requests.RequestException as e:
            print(f"网络请求失败: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"JSON 解析失败: {e}")
            return None
        except Exception as e:
            print(f"获取远程配置失败: {e}")
            return None

    def upload_config(self, card_key: str, config_data: dict) -> bool:
        """
        加密并上传配置到服务器：
        POST {server}/upload.php  { card_key, config(enc), action='upload', hwid }
        成功则记录上传操作
        """
        try:
            # 附带卡密到上传数据（与服务器约定）
            payload_for_encrypt = dict(config_data)
            payload_for_encrypt['card_key'] = card_key
            cfg_json = json.dumps(payload_for_encrypt, ensure_ascii=False, separators=(',', ':'))

            enc = self._encrypt_data(cfg_json)
            if not enc:
                print('配置加密失败')
                return False

            url = f"{self.server_url}/upload.php"
            hwid = self._hwid
            if not hwid:
                try:
                    from buff import Buff_Single
                    hwid = Buff_Single().GetMacCode()
                except Exception as e:
                    if self.debug_mode:
                        print(f"获取 Buff 机器码失败: {e}")
                    hwid = 'unknown'

            data = {'card_key': card_key, 'config': enc, 'action': 'upload', 'hwid': hwid}
            if self.debug_mode:
                print(f"[CFG] 上传配置，携带Authorization: {bool(self._token)}")

            resp = requests.post(url, json=data, headers=self._auth_headers(), timeout=self.request_timeout)
            resp.raise_for_status()
            result = resp.json()
            if self.debug_mode:
                print(f"保存配置服务器响应: {result}")

            if result.get('success', False):
                if USER_INFO_AVAILABLE:
                    try:
                        user_data = result.get('data', {}) or {}
                        if 'user_cards_id' in user_data and (not self.user_cards_id):
                            self.user_cards_id = user_data['user_cards_id']
                            init_user_info_manager(card_key, self.user_cards_id, self.server_url)
                        record_config_upload()
                    except Exception as e:
                        if self.debug_mode:
                            print(f"记录上传操作失败: {e}")
                return True
            else:
                print(f"配置上传失败: {result.get('message', '未知错误')}")
                return False

        except requests.RequestException as e:
            print(f"网络请求失败: {e}")
            return False
        except json.JSONDecodeError as e:
            print(f"JSON 解析失败: {e}")
            return False
        except Exception as e:
            print(f"上传配置失败: {e}")
            return False

    # ---------- 高层入口 ----------
    def validate_and_load_config(self, card_key: str = None) -> bool:
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
            # 直接写入本地配置文件
            with open('cfg.json', 'w', encoding='utf-8') as f:
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


# ---------- 附：卡密校验（保持原逻辑/接口） ----------
def DecryptCard(iCard: str, iMacCode: str) -> bool:
    """
    安全版 AES-256-CBC 解密验证函数。
    - 固定密钥: b'huiyestudio' → 填充至 32 字节
    - 固定 IV: 16 字节 0x00
    - PKCS7 填充
    - 输入 iCard 为 Base64 编码的纯密文（不含 IV）
    - 任何错误均返回 False
    """
    try:
        if not isinstance(iCard, str) or not isinstance(iMacCode, str):
            return False
        if not iCard or not iMacCode:
            return False

        key = b'huiyestudio'
        if len(key) < 32:
            key = key + b'\x00' * (32 - len(key))
        else:
            key = key[:32]

        iv = b'\x00' * 16
        ciphertext = base64.b64decode(iCard)

        if len(ciphertext) == 0 or len(ciphertext) % 16 != 0:
            return False

        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(ciphertext)

        pad_len = decrypted[-1]
        if not (1 <= pad_len <= 16):
            return False
        if len(decrypted) < pad_len:
            return False
        if decrypted[-pad_len:] != bytes([pad_len]) * pad_len:
            return False

        plaintext = decrypted[:-pad_len].decode('utf-8')
        return plaintext == iMacCode

    except (ValueError, TypeError, UnicodeDecodeError, MemoryError, OverflowError):
        return False
    except Exception:
        return False
