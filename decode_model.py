from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet
import base64

def generate_key(username: str) -> bytes:
    """用用户名生成固定密钥"""
    salt = username.encode()
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
    return base64.urlsafe_b64encode(kdf.derive(salt))

def build_model(path, username):
    try:
        modified_username = 'model_2025_SecureSalt_v1.0' + username + 'CodeBy:HuiyeStudio'
        key = generate_key(modified_username)
        cipher = Fernet(key)
        file_content = open(path, 'rb').read()
        model_bytes = cipher.decrypt(file_content)
        return model_bytes
    except Exception as e:
        print('解密模型失败')