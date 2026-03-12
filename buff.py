             """
验证模块（已禁用）
保留 Buff_Single / Buff_User 类导出以满足 core.py、remote_config.py 的 import 依赖。
原始文件约 2500 行，已精简为存根。
"""
import hashlib
import wmi
import winreg


# ── 唯一保留的业务逻辑：获取机器码 ──────────────────────────────
def g_GetMacCode():
    """通过 CPU ProcessorId 或 MachineGuid 生成机器码"""
    cpuMd5 = ""
    s = wmi.WMI()
    cp = s.Win32_Processor()

    for u in cp:
        if u.ProcessorId is not None:
            cpuMd5 = hashlib.md5(u.ProcessorId.encode('utf-8')).hexdigest()
            break

    if cpuMd5 == "":
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            machineGuid = str(value)
            cpuMd5 = hashlib.md5(machineGuid.encode('utf-8')).hexdigest()
        except Exception:
            print("无法获取机器码")
            return ""
    macCode = (cpuMd5[8:14] + cpuMd5[2:8] + cpuMd5[3:12] + cpuMd5[1:5]
               + cpuMd5[6:8] + cpuMd5[9:11] + cpuMd5[(len(cpuMd5) - 3):]).upper()
    return macCode


# ── 存根类：验证逻辑已禁用，仅保留被外部调用的接口 ────────────────

class Buff_Single:
    """单码验证（已禁用）— 仅保留 GetMacCode()"""

    def __init__(self, *args, **kwargs):
        pass

    def GetMacCode(self):
        return g_GetMacCode()

    # 以下方法保留签名以防外部反射调用，全部返回空值
    def initialize(self, *args, **kwargs):
        return None

    def SingleLogin(self, *args, **kwargs):
        return None

    def LegitimacyTesting(self, *args, **kwargs):
        return None


class Buff_User:
    """注册码验证（已禁用）— 保留类导出"""

    def __init__(self, *args, **kwargs):
        pass

    def GetMacCode(self):
        return g_GetMacCode()

    def initialize(self, *args, **kwargs):
        return None

    def User_Login(self, *args, **kwargs):
        return None

    def LegitimacyTesting(self, *args, **kwargs):
        return None
