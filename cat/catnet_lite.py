"""
CatNetLite 虚拟模块
用于绕过缺失的cat模块导入错误
"""

# 错误码定义
class ErrorCode:
    SUCCESS = 0
    FAILED = -1
    CONNECTION_ERROR = -2
    TIMEOUT = -3
    INVALID_PARAM = -4

# 鼠标按钮常量
BTN_LEFT = 1
BTN_RIGHT = 2
BTN_MIDDLE = 3
BTN_SIDE = 4
BTN_EXTRA = 5

class CatNetLite:
    """CatNetLite 虚拟类"""
    
    def __init__(self):
        self.is_connected = False
        self.device_info = {
            'name': 'Virtual CatBox Device',
            'version': '1.0.0',
            'status': 'Virtual Mode'
        }
        print("CatNetLite: 虚拟模式初始化")
    
    def connect(self, ip: str = "192.168.7.1", port: int = 8888, uuid: str = "ad60ecf0") -> int:
        """虚拟连接方法"""
        print(f"CatNetLite: 虚拟连接到 {ip}:{port} (UUID: {uuid})")
        self.is_connected = True
        return ErrorCode.SUCCESS
    
    def disconnect(self) -> int:
        """虚拟断开连接"""
        print("CatNetLite: 虚拟断开连接")
        self.is_connected = False
        return ErrorCode.SUCCESS
    
    def move(self, x: int, y: int) -> int:
        """虚拟鼠标移动"""
        if not self.is_connected:
            print("CatNetLite: 设备未连接，无法移动鼠标")
            return ErrorCode.CONNECTION_ERROR
        print(f"CatNetLite: 虚拟鼠标移动 x={x}, y={y}")
        return ErrorCode.SUCCESS
    
    def click(self, button: int) -> int:
        """虚拟鼠标点击"""
        if not self.is_connected:
            print("CatNetLite: 设备未连接，无法点击")
            return ErrorCode.CONNECTION_ERROR
        
        button_names = {
            BTN_LEFT: "左键",
            BTN_RIGHT: "右键", 
            BTN_MIDDLE: "中键",
            BTN_SIDE: "侧键",
            BTN_EXTRA: "扩展键"
        }
        
        button_name = button_names.get(button, f"未知按钮({button})")
        print(f"CatNetLite: 虚拟鼠标{button_name}点击")
        return ErrorCode.SUCCESS
    
    def press(self, button: int) -> int:
        """虚拟鼠标按下"""
        if not self.is_connected:
            print("CatNetLite: 设备未连接，无法按下")
            return ErrorCode.CONNECTION_ERROR
        
        button_names = {
            BTN_LEFT: "左键",
            BTN_RIGHT: "右键",
            BTN_MIDDLE: "中键",
            BTN_SIDE: "侧键", 
            BTN_EXTRA: "扩展键"
        }
        
        button_name = button_names.get(button, f"未知按钮({button})")
        print(f"CatNetLite: 虚拟鼠标{button_name}按下")
        return ErrorCode.SUCCESS
    
    def release(self, button: int) -> int:
        """虚拟鼠标释放"""
        if not self.is_connected:
            print("CatNetLite: 设备未连接，无法释放")
            return ErrorCode.CONNECTION_ERROR
        
        button_names = {
            BTN_LEFT: "左键",
            BTN_RIGHT: "右键",
            BTN_MIDDLE: "中键",
            BTN_SIDE: "侧键",
            BTN_EXTRA: "扩展键"
        }
        
        button_name = button_names.get(button, f"未知按钮({button})")
        print(f"CatNetLite: 虚拟鼠标{button_name}释放")
        return ErrorCode.SUCCESS
    
    def block(self, enable: bool) -> int:
        """虚拟鼠标屏蔽"""
        if not self.is_connected:
            print("CatNetLite: 设备未连接，无法设置屏蔽")
            return ErrorCode.CONNECTION_ERROR
        
        status = "启用" if enable else "禁用"
        print(f"CatNetLite: 虚拟鼠标屏蔽{status}")
        return ErrorCode.SUCCESS
    
    def get_device_info(self) -> dict:
        """获取虚拟设备信息"""
        return self.device_info
    
    def is_device_connected(self) -> bool:
        """检查虚拟设备连接状态"""
        return self.is_connected