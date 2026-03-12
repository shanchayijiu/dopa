import time
import json
import wmi
import hashlib
import string
import random
import binascii
import base64
import requests
import os
import winreg

# import requests.packages.urllib3.util.urlencode as urlencode
#from base64 import b64encode, b64decode
from arc4 import ARC4

# 网络验证已禁用
RequestURL = None

#定义效验时间误差范围  上下误差在-60 到 300 之间
Mix_Valid = -60
Max_Valid = 60

# 功能线路
CloudFlag =      "/validate/CloudFlag"   # 获取云下发标识
JavaScript_ =    "/validate/javascript"  # 单码调用远程JS
Timestamp =      "/validate/timestamp"   # 获取服务器时间戳
Special =        "/validate/Special"
SingleLogin =    "/validate/login"
SingleTwoLogin = "/validate/twologin"
Notice =         "/validate/notice"
Version =        "/validate/version"
IsVersion =      "/validate/isversion"
Expiretime =     "/validate/expiretime"
Expiretimes =    "/validate/expiretimes"
Updatacode =     "/validate/updatacode"
Updataip =       "/validate/updataip"
Variable =       "/validate/variable"
UserData =       "/validate/setuserdata"
GetuserData =    "/validate/getuserdata"
Blacklist =      "/validate/blacklist"
Updata =         "/validate/updata"
AppData =        "/validate/appdata"
VarData =        "/validate/vardata"
IsUse =          "/validate/isuse"
Status =         "/validate/statusA"
Localip =        "/validate/localip"

User_CloudFlag = "/validate/user/CloudFlag"   # 获取云下发标识
JavaScript_user= "/validate/user/javascript"  # 注册码调用远程JS
User_reg =       "/validate/user/reg"
User_rec =       "/validate/user/recharge"
User_login =     "/validate/user/login"
User_expire =    "/validate/user/expiretime"
User_expires =   "/validate/user/expiretimes"
User_updatacode= "/validate/user/updatacode"
User_updataip =  "/validate/user/updataip"
User_var =       "/validate/user/variable"
User_setdata =   "/validate/user/setuserdata"
User_getdata =   "/validate/user/getuserdata"
User_status =    "/validate/user/status"
User_MailCode =  "/validate/GetMailCode"
User_password =  "/validate/user/updata/password"
User_Update =    "/validate/user/updateaddr"



# RC4加密
def RC4_encrypt(text: str,Key) -> str:
    result = ""
    try:
        arc4 = ARC4(Key)
        result = str(binascii.b2a_hex(arc4.encrypt(text.encode())), "utf-8")
    except Exception as e:
        print("异常了:", str(e))
        result = "异常了"
    return result

# RC4解密
def RC4_decrypt( text: str,Key) -> str:
    result = ""
    try:
         arc4 = ARC4(Key)
         b = binascii.a2b_hex(text.encode("utf-8"))
         result = arc4.decrypt(b)
    except:
        result = ""
    return result


# 获取机器码
def g_GetMacCode():
    cpuMd5 = ""
    s = wmi.WMI()
    cp = s.Win32_Processor()

    for u in cp:
        if u.ProcessorId is not None:
            cpuMd5 = hashlib.md5(u.ProcessorId.encode('utf-8')).hexdigest()
            break

    # print("机器码:", cpuMd5)
    if cpuMd5 == "":
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            machineGuid = str(value)
            cpuMd5 = hashlib.md5(machineGuid.encode('utf-8')).hexdigest()
        except:  # 捕获全部异常
            print("无法获取机器码:", str(e))
            return ""
    macCode = (cpuMd5[8:14] + cpuMd5[2:8] + cpuMd5[3:12] + cpuMd5[1:5] + cpuMd5[6:8] + cpuMd5[9:11] + cpuMd5[(
                                                                                                                         len(cpuMd5) - 3):]).upper()
    # print("机器码:", macCode,len(macCode))
    return macCode


# 获取本地时间戳 10位
def GetlocalTime():
    timestamp = int(round(time.time() // 1))
    return timestamp

# 获取随机文本 默认长度16
def get_random_text(length=16):
    # 字符集包括小写字母、大写字母和数字
    char_set = string.ascii_letters + string.digits
    return ''.join(random.choice(char_set) for _ in range(length))

def ReturntoDefinition(flag:str) -> str:
	if flag == "400":
		return "成功";
	elif flag ==  "-1":
		return "软件不存在";
	elif flag ==  "-2":
		return "当前软件已停用";
	elif flag ==  "-3":
		return "版本不存在";
	elif flag ==  "-4":
		return "程序版本不是最新";
	elif flag ==  "-5":
		return "版本已停用";
	elif flag ==  "-6":
		return "您已被添加到黑名单";
	elif flag ==  "-7":
		return "远程变量不存在";
	elif flag ==  "-8":
		return "获取公告失败";
	elif flag ==  "-9":
		return "未设置更新地址";
	elif flag ==  "-10":
		return "未设置程序数据";
	elif flag ==  "-11":
		return "未设置版本数据";
	elif flag ==  "-12":
		return "还未登录";
	elif flag ==  "-13":
		return "用户数据设置成功";
	elif flag ==  "-14":
		return "添加成功";
	elif flag ==  "-15":
		return "强制下线";
	elif flag ==  "-16":
		return "未设置软件版本";
	elif flag ==  "-17":
		return "未设置用户数据";
	elif flag ==  "-18":
		return "已被顶下线";
	elif flag ==  "-19":
		return "未在绑定的 IP 登录";
	elif flag ==  "-20":
		return "未在绑定电脑登录";
	elif flag ==  "-21":
		return "未开启机器码验证,无需转绑";
	elif flag ==  "-22":
		return "未开启IP地址验证,无需转绑";
	elif flag ==  "-23":
		return "重绑次数超过限制";
	elif flag ==  "-24":
		return "登录版本不一致";
	elif flag ==  "-25":
		return "登录用户已达上限";
	elif flag ==  "-26":
		return "注册码卡密不能用于单码登陆";
	elif flag ==  "-27":
		return "单码卡密不能用于充值";
	elif flag ==  "-100":
		return "卡密不存在";
	elif flag ==  "-101":
		return "卡密已删除";
	elif flag ==  "-102":
		return "卡密已被封停";
	elif flag ==  "-103":
		return "卡密已到期";
	elif flag ==  "-104":
		return "卡密未使用";
	elif flag ==  "-105":
		return "卡密已使用";
	elif flag ==  "-106":
		return "未查询到卡密信息";
	elif flag ==  "-107":
		return "机器码一致 无需转绑";
	elif flag ==  "-108":
		return "ip一致无需转绑";
	elif flag ==  "-200":
		return "充值卡密不存在";
	elif flag ==  "-201":
		return "充值卡密与账号不符";
	elif flag ==  "-202":
		return "充值卡密已使用";
	elif flag ==  "-300":
		return "用户名已存在";
	elif flag ==  "-301":
		return "昵称已存在";
	elif flag ==  "-302":
		return "邮箱已存在";
	elif flag ==  "-303":
		return "用户编号设置错误";
	elif flag ==  "-304":
		return "用户不存在";
	elif flag ==  "-305":
		return "密码不正确";
	elif flag ==  "-306":
		return "新密码输入错误";
	elif flag ==  "-307":
		return "用户已被封停";
	elif flag ==  "-308":
		return "用户已到期";
	elif flag ==  "-309":
		return "账号已删除";
	elif flag ==  "-310":
		return "注册配置不存在";
	elif flag ==  "-311":
		return "未开启注册功能";
	elif flag ==  "-312":
		return "用户状态正常";
	elif flag ==  "-313":
		return "注册用户达到上限";
	elif flag ==  "-314":
		return "充值成功!填写的推荐人不存在";
	elif flag ==  "-315":
		return "充值成功!填写推荐人获赠时间失败";
	elif flag ==  "-316":
		return "充值成功!添加推荐信息失败";
	elif flag ==  "-317":
		return "用户名格式不正确";
	elif flag ==  "-318":
		return "密码格式不正确";
	elif flag ==  "-319":
		return "QQ格式不正确";
	elif flag ==  "-320":
		return "机器码格式不正确";
	elif flag ==  "-321":
		return "邮箱格式不正确";
	elif flag ==  "-322":
		return "昵称格式不正确";
	elif flag ==  "-323":
		return "邮箱验证码不存在";
	elif flag ==  "-324":
		return "邮箱验证码不正确";
	elif flag ==  "-325":
		return "邮箱和账户不匹配";
	elif flag ==  "-401":
		return "作者使用时间已到期";
	elif flag ==  "-402":
		return "操作频繁,请重试!";
	elif flag ==  "-403":
		return "系统禁止登录!";
	elif flag ==  "-404":
		return "网络链接失败";
	elif flag ==  "-405":
		return "错误的参数,请检查参数是否正确.";
	elif flag ==  "-406":
		return "已被顶下线";
	elif flag ==  "-407":
		return "状态码有误";
	elif flag ==  "-408":
		return "注册用户达到系统上限";
	elif flag ==  "-409":
		return "该功能为付费功能，将软件改为收费即可使用";
	elif flag ==  "-410":
		return "生成一机一码失败";
	elif flag ==  "-411":
		return "作者余额不足";
	elif flag ==  "-412":
		return "点卡不足";
	else:
		return flag








#存放全局密钥
g_key=""

class Result:
    code: int = 0
    msg: str = ""
    data: str = ""
    time: int = 0
    sign: str = ""


class RunStatus:
    status: bool = False
    info: str = "未初始化"
    expirationTime:int =0 # 到期时间
    statusCode:str="" #状态码
    deduct:int=0 # 扣除时间

def to_sendJson(send_info:str,uuid:str,key) -> str:
    jsonData = json.dumps(send_info)
    utf8_data = jsonData.encode('utf-8')  # 将字符串编码为UTF-8
    utf8_data = utf8_data.decode("utf-8")  # 去除 b‘
    ciphertext = RC4_encrypt(str(utf8_data), key)
    data = base64.b64encode(ciphertext.encode("utf-8"))
    data2 = base64.b64encode(uuid.encode('utf-8'))
    send_data = {
        "data": data.decode("utf-8"),
        "data2": data2.decode("utf-8")
    }
    return send_data
def ParsingData(str:str,sing:str,time:int) ->Result:
    result = Result()
    text = str.split('|')
    if len(text)<5:
        if str.find("对不起,操作失败,请联系管理")!=-1:
            result.code=0
            result.msg="执行方法时发生异常,请联系管理"
            result.sign
            result.time=time
            return result
        result.code=0
        result.msg=str
        result.sign=sing
        result.time=time
        return result

    #print("原始数据：", text[0])
    if text[0].find("code")!=-1:
        result.code=int(text[0].replace("code:",""))

    if text[1].find("msg") != -1:
        result.msg = text[1].replace("msg:", "")

    if text[2].find("sign") != -1:
        result.sign = text[2].replace("sign:", "")

    if text[3].find("time") != -1:
        result.time = int(text[3].replace("time:", ""))

    if text[4].find("data") != -1:
        result.data = text[4].replace("data:", "")
    return result

def ParsingData2(str:str)->Result:
    result = Result()
    result.code = 0
    text = str.replace("Return(","")
    text = text.replace(")","")
    text2 = text.split(',')
    if len(text2)<3:
        result.code = 0
        result.msg = str
        return result
    if text2[0].find("expirationTime")!=-1:
        result.time = int(text2[0].replace("expirationTime=",""))

    if text2[1].find("statusCode") != -1:
        result.data = text2[1].replace("statusCode=", "")

    if text2[2].find("deduct") != -1:
        result.sign = text2[2].replace("deduct=", "")
    result.code=1
    return result;

# 发送POST请求
def SendHttp(Url,json_data,key) -> Result:
    result = Result()
    result.code = 1  # 直接返回成功
    result.msg = "网络验证已禁用"
    result.data = {"status": "success", "message": "网络验证已跳过"}
    result.sign = key
    result.time = str(GetlocalTime())
    
    print(f"网络验证已禁用，跳过请求: {Url}")
    return result


class Buff_Single:
    __sname = ""           # 软件名
    __versionID = ""       # 软件版本
    __machineCode = ""     # 机器码
    __key = ""             # 软件密钥
    __uuid = ""            # 软件UUID
    __initStatus = ""      # 初始化状态
    __loginStatus = False  # 登录状态
    __expirationTime = 0   # 到期时间
    __card = ""            # 保存临时卡密
    __loginTime = 0        # 登录时间戳


    # 获取时间戳   用于数据包时效判断 为了避免本地时间和服务器时间不一致 故而采用先获取 服务器时间然后计算
    def GetTimestamp(self) -> RunStatus:
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data=to_sendJson(send_info,self.__uuid,self.__key)
        result= SendHttp(Timestamp,send_data,sing)
        if result.sign!=sing:
            resultStatus.status=False
            resultStatus.info="非法数据"
            return resultStatus
        resultStatus.status=True
        resultStatus.info=result.data
        return resultStatus

    def GetMacCode(self):
        return g_GetMacCode()

    # 初始化
    def initialize(self,sname,versionID,machineCode,uuid,key,time_) -> RunStatus:
        resultStatus = RunStatus()
        self.__sname = sname
        self.__versionID = versionID
        self.__machineCode = machineCode
        self.__uuid = uuid
        self.__key = key
        global g_key
        g_key = key
        #print("机器码:", machineCode)
       # print("本地时间:", timestamp)
        self.__init=True
        if time_==True:
            timeStatus = self.GetTimestamp()
            if timeStatus.status==False:
                resultStatus.status=False
                resultStatus.info=timeStatus.info
                self.__init = False
                return resultStatus
            localTime= GetlocalTime()
            Valid=localTime-int(timeStatus.info)
            if Valid<Mix_Valid or Valid > Max_Valid:
                resultStatus.status = False
                resultStatus.info = "本地时间和服务器时间相差过大，请将时间同步到北京时间!"
                self.__init = False
                return resultStatus
        resultStatus.status = True
        return resultStatus

    # 获取专码 根据IP计算出专属编码，可用于配置文件名等，从而减少特征
    def GetSpecialCode(self, len: int) -> RunStatus:
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if len < 2:
            len = 2
        if len > 20:
            len = 20
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "status": str(len),
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(Special, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 获取公告
    def GetNotice(self):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(Notice, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 获取最新版本号
    def GetNewVersion(self):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(Version, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 检测是否最新版  1 最新版, 2 不是最新版  3 测试版
    def IsNewVersion(self,VersionID:str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "versionID":VersionID,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(IsVersion, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 获取程序数据
    def GetAppData(self):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(AppData, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus
     # 获取版本数据
    def GetVersionData(self,VersionID:str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "versionID":VersionID,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(VarData, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 获取本机IP
    def GetlocalIP(self):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(Localip, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 单码登录
    def SingleLogin(self,cardKey:str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if cardKey=="":
            resultStatus.info="卡密不能为空"
            return resultStatus
        if len(cardKey) != 32:
            resultStatus.info = "卡密长度不正确"
            return resultStatus
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "cardKey":cardKey,
            "version":self.__versionID,
            "machineCode":self.__machineCode,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(SingleLogin, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            result2 = ParsingData2(result.data) # 解析返回的数
            if result2.code == 1:
               self.__card = cardKey
               self.__loginStatus = True
               self.__loginTime= GetlocalTime()
               self.__expirationTime=result2.time
               resultStatus.status = True
               resultStatus.expirationTime = result2.time # 到期时间
               resultStatus.statusCode = result2.data # 状态码
               return resultStatus
            else: # 如果解析失败就返回全部信息
                resultStatus.info=result2.msg

        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 单码登录
    def SingleTwologin(self,cardKey:str,statusCode:str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if cardKey=="":
            resultStatus.info="卡密不能为空"
            return resultStatus
        if len(cardKey) != 32:
            resultStatus.info = "卡密长度不正确"
            return resultStatus
        if statusCode == "":
            resultStatus.info = "状态码不能为空"
            return resultStatus
        if self.__loginStatus == False:
            resultStatus.info = "请先未登录"
            return resultStatus


        cardKey = cardKey.replace(" ", "")
        statusCode = statusCode.replace(" ","")
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "cardKey":cardKey,
            "statusCode":statusCode,
            "version":self.__versionID,
            "machineCode":self.__machineCode,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(SingleTwoLogin, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            result2 = ParsingData2(result.data) # 解析返回的数
            if result2.code == 1:
               self.__card = cardKey
               self.__loginStatus = True
               self.__loginTime = GetlocalTime()
               self.__expirationTime = result2.time
               resultStatus.status = True
               resultStatus.expirationTime = result2.time # 到期时间
               resultStatus.statusCode = result2.data # 状态码
               return resultStatus
            else: # 如果解析失败就返回全部信息
                resultStatus.info=result2.msg

        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 合法性检测  - 此函数不联网 必须在登录以后使用建议周期调用
    def LegitimacyTesting(self):
        if self.__loginStatus==False:
            os.kill(pid, 0)  # 发送0信号来检查进程是否存在
            return
        time = self.__expirationTime*60-(GetlocalTime()-self.__loginTime/1000)
        if time<1:
            os.kill(pid, 0)  # 发送0信号来检查进程是否存在
            return


    # 获取到期时间
    def GetExpireTime(self,cardKey:str,statusCode:str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if cardKey=="":
            resultStatus.info="卡密不能为空"
            return resultStatus
        if len(cardKey) != 32:
            resultStatus.info = "卡密长度不正确"
            return resultStatus
        if statusCode == "":
            resultStatus.info = "状态码不能为空"
            return resultStatus
        if self.__loginStatus==False:
            resultStatus.info = "请先登录"
            return resultStatus
        if len(self.__card)!= 32:
            resultStatus.info = "未登录"
            return resultStatus

        cardKey = cardKey.replace(" ", "")
        statusCode = statusCode.replace(" ","")
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "cardKey":cardKey,
            "statusCode":statusCode,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(Expiretime, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 获取到期时间_分钟
    def GetExpireTime_minute(self,cardKey:str,statusCode:str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if cardKey=="":
            resultStatus.info="卡密不能为空"
            return resultStatus
        if len(cardKey) != 32:
            resultStatus.info = "卡密长度不正确"
            return resultStatus
        if statusCode == "":
            resultStatus.info = "状态码不能为空"
            return resultStatus
        if self.__loginStatus==False:
            resultStatus.info = "请先登录"
            return resultStatus
        if len(self.__card)!= 32:
            resultStatus.info = "未登录"
            return resultStatus

        cardKey = cardKey.replace(" ", "")
        statusCode = statusCode.replace(" ","")
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "cardKey":cardKey,
            "statusCode":statusCode,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(Expiretimes, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 解绑机器码
    def UnbindMachineCode(self, cardKey: str, NewMachineCode: str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if cardKey == "":
            resultStatus.info = "卡密不能为空"
            return resultStatus
        if len(cardKey) != 32:
            resultStatus.info = "卡密长度不正确"
            return resultStatus
        if NewMachineCode == "":
            resultStatus.info = "新机器码不能为空"
            return resultStatus
        cardKey = cardKey.replace(" ", "")
        NewMachineCode = NewMachineCode.replace(" ", "")
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "cardKey": cardKey,
            "machineCode": NewMachineCode,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(Updatacode, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            result2 = ParsingData2(result.data)  # 解析返回的数
            if result2.code == 1:
                resultStatus.status = True
                resultStatus.info = result2.data  # 状态码
                resultStatus.deduct=result2.sign  # 扣除的时间
                return resultStatus
            else:  # 如果解析失败就返回全部信息
                resultStatus.info = result2.msg
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 解绑IP
    def UnbindIP(self, cardKey: str, NewIP: str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if cardKey == "":
            resultStatus.info = "卡密不能为空"
            return resultStatus
        if len(cardKey) != 32:
            resultStatus.info = "卡密长度不正确"
            return resultStatus
        if NewIP == "":
            resultStatus.info = "新机器码不能为空"
            return resultStatus
        cardKey = cardKey.replace(" ", "")
        NewIP = NewIP.replace(" ", "")
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "cardKey": cardKey,
            "ip": NewIP,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(Updataip, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            result2 = ParsingData2(result.data)  # 解析返回的数
            if result2.code == 1:
                resultStatus.status = True
                resultStatus.info = result2.data  # 状态码
                resultStatus.deduct=result2.sign  # 扣除的时间
                return resultStatus
            else:  # 如果解析失败就返回全部信息
                resultStatus.info = result2.msg
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 获取远程变量数据
    def GetRemoteVariables(self, cardKey: str, statusCode: str,varNumber:str,varName:str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if cardKey == "":
            resultStatus.info = "卡密不能为空"
            return resultStatus
        if len(cardKey) != 32:
            resultStatus.info = "卡密长度不正确"
            return resultStatus
        if statusCode == "":
            resultStatus.info = "状态码不能为空"
            return resultStatus
        if self.__loginStatus == False:
            resultStatus.info = "请先登录"
            return resultStatus
        if len(self.__card) != 32:
            resultStatus.info = "未登录"
            return resultStatus
        if varNumber == "":
            resultStatus.info = "变量编号不能为空"
            return resultStatus
        if varName == "":
            resultStatus.info = "变量名不能为空"
            return resultStatus
        cardKey = cardKey.replace(" ", "")
        statusCode = statusCode.replace(" ", "")
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "cardKey": cardKey,
            "statusCode": statusCode,
            "varName":varName,
            "varNumber":varNumber,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(Variable, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 设置用户数据
    def SetUserdata(self, cardKey: str, statusCode: str, userdata: str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if cardKey == "":
            resultStatus.info = "卡密不能为空"
            return resultStatus
        if len(cardKey) != 32:
            resultStatus.info = "卡密长度不正确"
            return resultStatus
        if statusCode == "":
            resultStatus.info = "状态码不能为空"
            return resultStatus
        if self.__loginStatus == False:
            resultStatus.info = "请先登录"
            return resultStatus
        if len(self.__card) != 32:
            resultStatus.info = "未登录"
            return resultStatus
        if len(userdata) > 2000:
            resultStatus.info = "用户数据过长"
            return resultStatus
        cardKey = cardKey.replace(" ", "")
        statusCode = statusCode.replace(" ", "")
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "cardKey": cardKey,
            "statusCode": statusCode,
            "userData": userdata,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(UserData, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 获取用户数据
    def GetUserdata(self, cardKey: str, statusCode: str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if cardKey == "":
            resultStatus.info = "卡密不能为空"
            return resultStatus
        if len(cardKey) != 32:
            resultStatus.info = "卡密长度不正确"
            return resultStatus
        if statusCode == "":
            resultStatus.info = "状态码不能为空"
            return resultStatus
        if self.__loginStatus == False:
            resultStatus.info = "请先登录"
            return resultStatus
        if len(self.__card) != 32:
            resultStatus.info = "未登录"
            return resultStatus
        cardKey = cardKey.replace(" ", "")
        statusCode = statusCode.replace(" ", "")
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "cardKey": cardKey,
            "statusCode": statusCode,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(GetuserData, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus


    # 获取更新地址
    def GetUpdateAddress(self, cardKey: str):
            resultStatus = RunStatus()
            if self.__init == False:
                return resultStatus
            cardKey = cardKey.replace(" ", "")
            sing = get_random_text()
            send_info = {
                "sname": self.__sname,
                "uuid": self.__uuid,
                "cardKey": cardKey,
                "remarks": sing,
                "timestamp": str(GetlocalTime())
            }
            send_data = to_sendJson(send_info, self.__uuid, self.__key)
            result = SendHttp(Updata, send_data, sing)
            if result.sign != sing:
                resultStatus.status = False
                resultStatus.info = "非法数据"
                return resultStatus
            Valid = GetlocalTime() - int(result.time)
            if Valid < Mix_Valid or Valid > Max_Valid:
                resultStatus.status = False
                resultStatus.info = "数据包过期"
                return resultStatus
            if result.code == 1:
                resultStatus.status = True
                resultStatus.info = result.data
                return resultStatus
            resultStatus.status = False
            resultStatus.info = result.msg
            return resultStatus

    # 查询是否使用
    def QueryWhetherTouse(self, cardKey: str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if cardKey == "":
            resultStatus.info = "卡密不能为空"
            return resultStatus
        if len(cardKey) != 32:
            resultStatus.info = "卡密长度不正确"
            return resultStatus
        cardKey = cardKey.replace(" ", "")
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "cardKey": cardKey,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(IsUse, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

     # 获取用户状态
    def GetUserStatus(self, cardKey: str,statusCode: str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if cardKey == "":
            resultStatus.info = "卡密不能为空"
            return resultStatus
        if len(cardKey) != 32:
            resultStatus.info = "卡密长度不正确"
            return resultStatus
        if statusCode == "":
            resultStatus.info = "状态码不能为空"
            return resultStatus
        if self.__loginStatus == False:
            resultStatus.info = "请先登录"
            return resultStatus
        if len(self.__card) != 32:
            resultStatus.info = "未登录"
            return resultStatus
        cardKey = cardKey.replace(" ", "")
        statusCode = statusCode.replace(" ", "")
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "cardKey": cardKey,
            "statusCode":statusCode,
            "machineCode":self.__machineCode,
            "loginVersion":self.__versionID,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(Status, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 调用远程JS算法
    def RunJScode(self, jsName: str, params: str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if jsName == "":
            resultStatus.info = "JS函数名不能为空"
            return resultStatus
        if len(jsName) > 20:
            resultStatus.info = "JS函数名过长"
            return resultStatus
        if self.__loginStatus == False:
            resultStatus.info = "请先登录"
            return resultStatus
        if len(self.__card) != 32:
            resultStatus.info = "未登录"
            return resultStatus
        params = params.replace("，", ",")
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "cardKey": self.__card,
            "machineCode": self.__machineCode,
            "javascript": jsName,
            "params":params,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(JavaScript_, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 获取云下发标识   成功返回 文件标志  5分钟内有效且只能使用一次   私有
    def __GetCloudFileflag(self, cardKey: str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "cardKey": cardKey,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(CloudFlag, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 添加黑名单 IP会自动添加到黑名单
    def AddBlacklist(self,remarks: str):
            resultStatus = RunStatus()
            if self.__init == False:
                return resultStatus
            sing = get_random_text()
            send_info = {
                "sname": self.__sname,
                "uuid": self.__uuid,
                "cardKey": self.__card,
                "machineCode": self.__machineCode,
                "remarks": remarks,
                "ipAnalysis":sing,
                "timestamp": str(GetlocalTime())
            }
            send_data = to_sendJson(send_info, self.__uuid, self.__key)
            result = SendHttp(Blacklist, send_data, sing)
            if result.sign != sing:
                resultStatus.status = False
                resultStatus.info = "非法数据"
                return resultStatus
            Valid = GetlocalTime() - int(result.time)
            if Valid < Mix_Valid or Valid > Max_Valid:
                resultStatus.status = False
                resultStatus.info = "数据包过期"
                return resultStatus
            if result.code == 1:
                resultStatus.status = True
                resultStatus.info = result.data
                return resultStatus
            resultStatus.status = False
            resultStatus.info = result.msg
            return resultStatus

    # 下载更新文件
    def DownloadedUpdatafile(self,url :str,path:str):
        resultStatus = RunStatus()
        r=requests.get(url=url)
        with open(path, "wb") as code:
            code.write(r.content)

        resultStatus.status=True
        resultStatus.info="下载完成"
        return resultStatus

    # 下载云下发文件
    def DownloadCloudFile(self,key:str,url :str,path:str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        resultStatus = __GetCloudFileflag(key)
        if resultStatus.status == False:
            print("获取云下发标识:失败", ReturntoDefinition_(int(resultStatus.info)))
            return
        newUrl=url+"&uuid"+resultStatus.info
        DownloadedUpdatafile(newUrl,path)
        return



    # 解析返回释义
    def ReturntoDefinition_(self,flag:str) ->str:
        return ReturntoDefinition(flag)


# ======================================================= 注册码模式 ===========================================================
class Buff_User:
    __sname = ""  # 软件名
    __versionID = ""  # 软件版本
    __machineCode = ""  # 机器码
    __key = ""  # 软件密钥
    __uuid = ""  # 软件UUID
    __initStatus = ""  # 初始化状态
    __loginStatus = False  # 登录状态
    __expirationTime = 0  # 到期时间
    __username = ""  # 保存临时卡密
    __loginTime = 0  # 登录时间戳
    __statusCode = "" #状态码

    # 获取时间戳   用于数据包时效判断 为了避免本地时间和服务器时间不一致 故而采用先获取 服务器时间然后计算
    def GetTimestamp(self) -> RunStatus:
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(Timestamp, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        resultStatus.status = True
        resultStatus.info = result.data
        return resultStatus

    def GetMacCode(self):
        return g_GetMacCode()

    # 初始化
    def initialize(self, sname, versionID, machineCode, uuid, key, time_) -> RunStatus:
        resultStatus = RunStatus()
        self.__sname = sname
        self.__versionID = versionID
        self.__machineCode = machineCode
        self.__uuid = uuid
        self.__key = key
        global g_key
        g_key = key
        # print("机器码:", machineCode)
        # print("本地时间:", timestamp)
        self.__init = True
        if time_ == True:
            timeStatus = self.GetTimestamp()
            if timeStatus.status == False:
                resultStatus.status = False
                resultStatus.info = timeStatus.info
                self.__init = False
                return resultStatus
            localTime = GetlocalTime()
            Valid = localTime - int(timeStatus.info)
            if Valid < Mix_Valid or Valid > Max_Valid:
                resultStatus.status = False
                resultStatus.info = "本地时间和服务器时间相差过大，请将时间同步到北京时间!"
                self.__init = False
                return resultStatus
        resultStatus.status = True
        return resultStatus

    # 获取专码 根据IP计算出专属编码，可用于配置文件名等，从而减少特征
    def GetSpecialCode(self, len: int) -> RunStatus:
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if len < 2:
            len = 2
        if len > 20:
            len = 20
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "status": str(len),
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(Special, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 获取公告
    def GetNotice(self) -> RunStatus:
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(Notice, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 获取最新版本号
    def GetNewVersion(self) -> RunStatus:
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(Version, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 检测是否最新版  1 最新版, 2 不是最新版  3 测试版
    def IsNewVersion(self, VersionID: str)  -> RunStatus:
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "versionID": VersionID,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(IsVersion, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 获取程序数据
    def GetAppData(self) -> RunStatus:
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(AppData, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 获取版本数据
    def GetVersionData(self, VersionID: str) -> RunStatus:
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "versionID": VersionID,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(VarData, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 获取本机IP
    def GetlocalIP(self) -> RunStatus:
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(Localip, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

        # 注册码用户_登录
     # 注册码用户_注册
    def User_reg(self, username: str, password: str,nickname:str,mail:str,qq:str, referralCode:str) -> RunStatus:
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if username == "":
            resultStatus.info = "用户名不能为空"
            return resultStatus
        if password == "":
            resultStatus.info = "密码不能为空"
            return resultStatus
        if nickname == "":
            resultStatus.info = "昵称不能为空"
            return resultStatus
        if mail == "":
            resultStatus.info = "邮箱不能为空"
            return resultStatus

        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "username": username,
            "password": password,
            "nickname": nickname,
            "mail":mail,
            "qq":qq,
            "referralCode":referralCode,
            "machineCode": self.__machineCode,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(User_reg, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            result2 = ParsingData2(result.data)  # 解析返回的数
            if result2.code == 1:
                resultStatus.status = True
                resultStatus.expirationTime = result2.time  # 赠送时间
                resultStatus.info = result2.data  # 状态码
                return resultStatus
            else:  # 如果解析失败就返回全部信息
                resultStatus.info = result2.msg
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

     # 注册码用户_充值
    def User_Recharge(self,username:str,cardKey:str,referralCode:str) -> RunStatus:
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if username == "":
            resultStatus.info = "用户名不能为空"
            return resultStatus
        if cardKey == "":
            resultStatus.info = "充值卡不能为空"
            return resultStatus

        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "username":username,
            "cardKey":cardKey,
            "referralCode":referralCode,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(User_rec, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus



     # 注册码用户_登录
    def User_Login(self,username:str,password:str) -> RunStatus:
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if username == "":
            resultStatus.info = "用户名不能为空"
            return resultStatus
        if password == "":
            resultStatus.info = "密码不能为空"
            return resultStatus
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "username": username,
            "password":password,
            "loginVersion": self.__versionID,
            "machineCode": self.__machineCode,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(User_login, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            result2 = ParsingData2(result.data)  # 解析返回的数
            if result2.code == 1:
                self.__username = username
                self.__statusCode = result2.data  # 状态码
                self.__loginStatus = True
                self.__loginTime = GetlocalTime()
                self.__expirationTime = result2.time
                resultStatus.status = True
                resultStatus.expirationTime = result2.time  # 到期时间
                resultStatus.statusCode = result2.data  # 状态码
                return resultStatus
            else:  # 如果解析失败就返回全部信息
                resultStatus.info = result2.msg

        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 合法性检测  - 此函数不联网 必须在登录以后使用建议周期调用
    def LegitimacyTesting(self):
        if self.__loginStatus == False:
            os.kill(pid, 0)  # 发送0信号来检查进程是否存在
            return
        time = self.__expirationTime * 60 - (GetlocalTime() - self.__loginTime / 1000)
        if time < 1:
            os.kill(pid, 0)  # 发送0信号来检查进程是否存在
            return


    # 获取到期时间
    def GetExpireTime(self, username: str, statusCode: str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if username == "":
            resultStatus.info = "用户名不能为空"
            return resultStatus
        if statusCode == "":
            resultStatus.info = "状态码不能为空"
            return resultStatus
        if self.__loginStatus == False:
            resultStatus.info = "请先登录"
            return resultStatus
        statusCode = statusCode.replace(" ", "")
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "username": username,
            "statusCode": statusCode,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(User_expire, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 获取到期时间_分钟
    def GetExpireTime_minute(self, username: str, statusCode: str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if username == "":
            resultStatus.info = "用户名不能为空"
            return resultStatus
        if statusCode == "":
            resultStatus.info = "状态码不能为空"
            return resultStatus
        if self.__loginStatus == False:
            resultStatus.info = "请先登录"
            return resultStatus
        statusCode = statusCode.replace(" ", "")
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "username": username,
            "statusCode": statusCode,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(User_expires, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 解绑机器码
    def UnbindMachineCode(self, username: str,password:str, NewMachineCode: str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if username == "":
            resultStatus.info = "用户名不能为空"
            return resultStatus
        if password == "":
            resultStatus.info = "密码不能为空"
            return resultStatus
        if NewMachineCode == "":
            resultStatus.info = "新机器码不能为空"
            return resultStatus
        NewMachineCode = NewMachineCode.replace(" ", "")
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "username": username,
            "password": password,
            "machineCode": NewMachineCode,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(User_updatacode, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            result2 = ParsingData2(result.data)  # 解析返回的数
            if result2.code == 1:
                resultStatus.status = True
                resultStatus.info = result2.data  # 状态码
                resultStatus.deduct = result2.sign  # 扣除的时间
                return resultStatus
            else:  # 如果解析失败就返回全部信息
                resultStatus.info = result2.msg
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 解绑IP
    def UnbindIP(self, username: str,password:str, NewIP: str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if username == "":
            resultStatus.info = "用户名不能为空"
            return resultStatus
        if password == "":
            resultStatus.info = "密码不能为空"
            return resultStatus
        if NewIP == "":
            resultStatus.info = "新机器码不能为空"
            return resultStatus
        NewIP = NewIP.replace(" ", "")
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "username": username,
            "password":password,
            "ip": NewIP,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(User_updataip, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            result2 = ParsingData2(result.data)  # 解析返回的数
            if result2.code == 1:
                resultStatus.status = True
                resultStatus.info = result2.data  # 状态码
                resultStatus.deduct = result2.sign  # 扣除的时间
                return resultStatus
            else:  # 如果解析失败就返回全部信息
                resultStatus.info = result2.msg
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 获取远程变量数据
    def GetRemoteVariables(self, username: str, statusCode: str, varNumber: str, varName: str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if username == "":
            resultStatus.info = "用户名不能为空"
            return resultStatus
        if statusCode == "":
            resultStatus.info = "状态码不能为空"
            return resultStatus
        if self.__loginStatus == False:
            resultStatus.info = "请先登录"
            return resultStatus
        if varNumber == "":
            resultStatus.info = "变量编号不能为空"
            return resultStatus
        if varName == "":
            resultStatus.info = "变量名不能为空"
            return resultStatus
        statusCode = statusCode.replace(" ", "")
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "username": username,
            "statusCode": statusCode,
            "varName": varName,
            "varNumber": varNumber,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(User_var, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 设置用户数据
    def SetUserdata(self, username: str, statusCode: str, userdata: str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if username == "":
            resultStatus.info = "用户名不能为空"
            return resultStatus
        if statusCode == "":
            resultStatus.info = "状态码不能为空"
            return resultStatus
        if self.__loginStatus == False:
            resultStatus.info = "请先登录"
            return resultStatus
        if len(userdata) > 2000:
            resultStatus.info = "用户数据过长"
            return resultStatus
        statusCode = statusCode.replace(" ", "")
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "username": username,
            "statusCode": statusCode,
            "userData": userdata,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(User_setdata, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 获取用户数据
    def GetUserdata(self, username: str, statusCode: str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if username == "":
            resultStatus.info = "用户名不能为空"
            return resultStatus
        if statusCode == "":
            resultStatus.info = "状态码不能为空"
            return resultStatus
        if self.__loginStatus == False:
            resultStatus.info = "请先登录"
            return resultStatus
        statusCode = statusCode.replace(" ", "")
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "username": username,
            "statusCode": statusCode,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(User_getdata, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 获取更新地址
    def GetUpdateAddress(self, username: str):
            resultStatus = RunStatus()
            if self.__init == False:
                return resultStatus
            sing = get_random_text()
            send_info = {
                "sname": self.__sname,
                "uuid": self.__uuid,
                "username": username,
                "remarks": sing,
                "timestamp": str(GetlocalTime())
            }
            send_data = to_sendJson(send_info, self.__uuid, self.__key)
            result = SendHttp(User_Update, send_data, sing)
            if result.sign != sing:
                resultStatus.status = False
                resultStatus.info = "非法数据"
                return resultStatus
            Valid = GetlocalTime() - int(result.time)
            if Valid < Mix_Valid or Valid > Max_Valid:
                resultStatus.status = False
                resultStatus.info = "数据包过期"
                return resultStatus
            if result.code == 1:
                resultStatus.status = True
                resultStatus.info = result.data
                return resultStatus
            resultStatus.status = False
            resultStatus.info = result.msg
            return resultStatus



    # 获取用户状态
    def GetUserStatus(self, username: str, statusCode: str):
            resultStatus = RunStatus()
            if self.__init == False:
                return resultStatus
            if username == "":
                resultStatus.info = "卡密不能为空"
                return resultStatus
            if statusCode == "":
                resultStatus.info = "状态码不能为空"
                return resultStatus
            if self.__loginStatus == False:
                resultStatus.info = "请先登录"
                return resultStatus
            statusCode = statusCode.replace(" ", "")
            sing = get_random_text()
            send_info = {
                "sname": self.__sname,
                "uuid": self.__uuid,
                "username": username,
                "statusCode": statusCode,
                "machineCode": self.__machineCode,
                "loginVersion": self.__versionID,
                "remarks": sing,
                "timestamp": str(GetlocalTime())
            }
            send_data = to_sendJson(send_info, self.__uuid, self.__key)
            result = SendHttp(User_status, send_data, sing)
            if result.sign != sing:
                resultStatus.status = False
                resultStatus.info = "非法数据"
                return resultStatus
            Valid = GetlocalTime() - int(result.time)
            if Valid < Mix_Valid or Valid > Max_Valid:
                resultStatus.status = False
                resultStatus.info = "数据包过期"
                return resultStatus
            if result.code == 1:
                resultStatus.status = True
                resultStatus.info = result.data
                return resultStatus
            resultStatus.status = False
            resultStatus.info = result.msg
            return resultStatus

    # 调用远程JS算法
    def RunJScode(self, jsName: str, params: str):
            resultStatus = RunStatus()
            if self.__init == False:
                return resultStatus
            if jsName == "":
                resultStatus.info = "JS函数名不能为空"
                return resultStatus
            if len(jsName) > 20:
                resultStatus.info = "JS函数名过长"
                return resultStatus
            if self.__loginStatus == False:
                resultStatus.info = "请先登录"
                return resultStatus
            params = params.replace("，", ",")
            sing = get_random_text()


            statusCode = self.__statusCode.replace(" ", "")
            send_info = {
                "sname": self.__sname,
                "uuid": self.__uuid,
                "username": self.__username,
                "statusCode":statusCode,
                "machineCode": self.__machineCode,
                "javascript": jsName,
                "params": params,
                "remarks": sing,
                "timestamp": str(GetlocalTime())
            }
            send_data = to_sendJson(send_info, self.__uuid, self.__key)
            result = SendHttp(JavaScript_user, send_data, sing)
            if result.sign != sing:
                resultStatus.status = False
                resultStatus.info = "非法数据"
                return resultStatus
            Valid = GetlocalTime() - int(result.time)
            if Valid < Mix_Valid or Valid > Max_Valid:
                resultStatus.status = False
                resultStatus.info = "数据包过期"
                return resultStatus
            if result.code == 1:
                resultStatus.status = True
                resultStatus.info = result.data
                return resultStatus
            resultStatus.status = False
            resultStatus.info = result.msg
            return resultStatus

    # 获取云下发标识   成功返回 文件标志  5分钟内有效且只能使用一次   私有
    def __GetCloudFileflag(self, username: str):
            resultStatus = RunStatus()
            if self.__init == False:
                return resultStatus
            sing = get_random_text()
            send_info = {
                "sname": self.__sname,
                "uuid": self.__uuid,
                "username": username,
                "remarks": sing,
                "timestamp": str(GetlocalTime())
            }
            send_data = to_sendJson(send_info, self.__uuid, self.__key)
            result = SendHttp(User_CloudFlag, send_data, sing)
            if result.sign != sing:
                resultStatus.status = False
                resultStatus.info = "非法数据"
                return resultStatus
            Valid = GetlocalTime() - int(result.time)
            if Valid < Mix_Valid or Valid > Max_Valid:
                resultStatus.status = False
                resultStatus.info = "数据包过期"
                return resultStatus
            if result.code == 1:
                resultStatus.status = True
                resultStatus.info = result.data
                return resultStatus
            resultStatus.status = False
            resultStatus.info = result.msg
            return resultStatus

    # 添加黑名单 IP会自动添加到黑名单
    def AddBlacklist(self, remarks: str):
            resultStatus = RunStatus()
            if self.__init == False:
                return resultStatus
            sing = get_random_text()
            send_info = {
                "sname": self.__sname,
                "uuid": self.__uuid,
                "username": self.__username,
                "machineCode": self.__machineCode,
                "remarks": remarks,
                "ipAnalysis": sing,
                "timestamp": str(GetlocalTime())
            }
            send_data = to_sendJson(send_info, self.__uuid, self.__key)
            result = SendHttp(Blacklist, send_data, sing)
            if result.sign != sing:
                resultStatus.status = False
                resultStatus.info = "非法数据"
                return resultStatus
            Valid = GetlocalTime() - int(result.time)
            if Valid < Mix_Valid or Valid > Max_Valid:
                resultStatus.status = False
                resultStatus.info = "数据包过期"
                return resultStatus
            if result.code == 1:
                resultStatus.status = True
                resultStatus.info = result.data
                return resultStatus
            resultStatus.status = False
            resultStatus.info = result.msg
            return resultStatus

    # 下载更新文件
    def DownloadedUpdatafile(self, url: str, path: str):
        resultStatus = RunStatus()
        r = requests.get(url=url)
        with open(path, "wb") as code:
            code.write(r.content)
        resultStatus.status = True
        resultStatus.info = "下载完成"
        return resultStatus

    # 下载云下发文件
    def DownloadCloudFile(self, username: str, url: str, path: str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        resultStatus = self.__GetCloudFileflag(username)
        if resultStatus.status == False:
            print("获取云下发标识:失败", ReturntoDefinition_(resultStatus.info))
            return
        newUrl = url + "&uuid" + resultStatus.info
        DownloadedUpdatafile(newUrl, path)
        return


    # 获取邮箱验证码     返回 邮箱UUID  注意：每次调用需要 间隔时间120秒 否则返回错误
    def GetMailcode(self, username: str, mail: str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if username == "":
            resultStatus.info = "用户名不能为空"
            return resultStatus
        if mail == "":
            resultStatus.info = "邮箱不能为空"
            return resultStatus
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "username": username,
            "mail": mail,
            "userData": userdata,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(User_MailCode, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus

    # 更新密码
    def UpdataPassword(self, username: str,newPassword:str, mail: str, mailuuid: str,mailCode:str):
        resultStatus = RunStatus()
        if self.__init == False:
            return resultStatus
        if username == "":
            resultStatus.info = "用户名不能为空"
            return resultStatus
        if newPassword == "":
            resultStatus.info = "新密码不能为空"
            return resultStatus
        if mail == "":
            resultStatus.info = "邮箱不能为空"
            return resultStatus
        if mailuuid == "":
            resultStatus.info = "邮箱UUID不能为空"
            return resultStatus
        if mailCode == "":
            resultStatus.info = "邮箱验证码不能为空"
            return resultStatus
        sing = get_random_text()
        send_info = {
            "sname": self.__sname,
            "uuid": self.__uuid,
            "username": username,
            "repassword":repassword,
            "mail": mail,
            "mailuuid": mailuuid,
            "mailCode":mailCode,
            "remarks": sing,
            "timestamp": str(GetlocalTime())
        }
        send_data = to_sendJson(send_info, self.__uuid, self.__key)
        result = SendHttp(User_password, send_data, sing)
        if result.sign != sing:
            resultStatus.status = False
            resultStatus.info = "非法数据"
            return resultStatus
        Valid = GetlocalTime() - int(result.time)
        if Valid < Mix_Valid or Valid > Max_Valid:
            resultStatus.status = False
            resultStatus.info = "数据包过期"
            return resultStatus
        if result.code == 1:
            resultStatus.status = True
            resultStatus.info = result.data
            return resultStatus
        resultStatus.status = False
        resultStatus.info = result.msg
        return resultStatus





     # 解析返回释义
    def ReturntoDefinition_(self,nunmer:int) ->str:
        return ReturntoDefinition(nunmer)