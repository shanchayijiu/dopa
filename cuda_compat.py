"""
PyCUDA 兼容层 —— 使用 cuda-python (cuda.bindings.driver) 实现 pycuda.driver 的核心 API。

当平台无法安装 pycuda（缺少 Visual C++ Build Tools 等）时，本模块作为透明替代：

    try:
        import pycuda.driver as cuda
    except ImportError:
        import cuda_compat as cuda

支持的 API:
    init, Device, Stream, get_version,
    pagelocked_empty, mem_alloc, memcpy_htod_async, memcpy_dtoh_async,
    Context.get_current, LogicError
"""

from __future__ import annotations

import ctypes
import numpy as np

from cuda.bindings import driver as _drv

# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------

class LogicError(RuntimeError):
    """对应 pycuda.driver.LogicError"""
    pass


def _check(err):
    """检查 CUDA Driver API 返回值，非 SUCCESS 则抛出 LogicError。"""
    if int(err) != 0:
        raise LogicError(f"CUDA driver error: {err}")


# ---------------------------------------------------------------------------
# 全局初始化
# ---------------------------------------------------------------------------

_initialized = False


def init(flags: int = 0):
    """对应 pycuda.driver.init()"""
    global _initialized
    if _initialized:
        return
    (err,) = _drv.cuInit(flags)
    _check(err)
    _initialized = True


def get_version() -> tuple:
    """返回 (major, minor) 版本元组，与 pycuda.driver.get_version 行为一致。"""
    err, ver = _drv.cuDriverGetVersion()
    _check(err)
    major = ver // 1000
    minor = (ver % 1000) // 10
    return (major, minor)


# ---------------------------------------------------------------------------
# DeviceAllocation —— 模拟 pycuda DeviceAllocation，可 int() 转指针
# ---------------------------------------------------------------------------

class DeviceAllocation:
    """模拟 pycuda.driver.DeviceAllocation"""
    __slots__ = ("_ptr", "_nbytes")

    def __init__(self, ptr, nbytes: int):
        self._ptr = ptr
        self._nbytes = nbytes

    def __int__(self):
        return int(self._ptr)

    def __index__(self):
        return int(self._ptr)

    def __del__(self):
        try:
            _drv.cuMemFree(self._ptr)
        except Exception:
            pass

    def __repr__(self):
        return f"<DeviceAllocation ptr={int(self._ptr):#x} nbytes={self._nbytes}>"


def mem_alloc(nbytes: int) -> DeviceAllocation:
    """对应 pycuda.driver.mem_alloc(nbytes)"""
    err, ptr = _drv.cuMemAlloc(int(nbytes))
    _check(err)
    return DeviceAllocation(ptr, int(nbytes))


# ---------------------------------------------------------------------------
# PagelockedArray —— page-locked 内存 + numpy 视图
# ---------------------------------------------------------------------------

# numpy dtype -> ctypes 映射
_DTYPE_CTYPE = {
    np.float16: ctypes.c_uint16,  # 16-bit
    np.float32: ctypes.c_float,
    np.float64: ctypes.c_double,
    np.int8: ctypes.c_int8,
    np.int16: ctypes.c_int16,
    np.int32: ctypes.c_int32,
    np.int64: ctypes.c_int64,
    np.uint8: ctypes.c_uint8,
    np.uint16: ctypes.c_uint16,
    np.uint32: ctypes.c_uint32,
    np.uint64: ctypes.c_uint64,
    np.bool_: ctypes.c_bool,
}


class _PagelockedArray(np.ndarray):
    """
    numpy ndarray 子类，底层内存由 cuMemAllocHost 分配（page-locked）。
    """
    _host_ptr: int = 0

    def __del__(self):
        ptr = getattr(self, "_host_ptr", 0)
        if ptr:
            try:
                _drv.cuMemFreeHost(ptr)
            except Exception:
                pass

    @property
    def _raw_ptr(self) -> int:
        return self._host_ptr


def pagelocked_empty(size, dtype) -> np.ndarray:
    """
    对应 pycuda.driver.pagelocked_empty(size, dtype)。
    返回一个 page-locked numpy 数组。
    """
    dt = np.dtype(dtype)
    nbytes = int(size) * dt.itemsize
    err, ptr = _drv.cuMemAllocHost(nbytes)
    _check(err)

    ct = _DTYPE_CTYPE.get(dt.type)
    if ct is None:
        ct = ctypes.c_uint8
        shape = (nbytes,)
    else:
        shape = (int(size),)

    arr_type = ct * int(size)
    buf = arr_type.from_address(ptr)
    arr = np.ctypeslib.as_array(buf, shape=shape).view(_PagelockedArray)
    arr._host_ptr = ptr
    return arr


# ---------------------------------------------------------------------------
# Stream
# ---------------------------------------------------------------------------

class Stream:
    """对应 pycuda.driver.Stream"""
    __slots__ = ("_handle",)

    def __init__(self):
        err, h = _drv.cuStreamCreate(0)
        _check(err)
        self._handle = h

    @property
    def handle(self):
        return self._handle

    def synchronize(self):
        (err,) = _drv.cuStreamSynchronize(self._handle)
        _check(err)

    def __del__(self):
        try:
            _drv.cuStreamDestroy(self._handle)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

class _ContextMeta:
    """提供 Context.get_current() 静态方法"""

    @staticmethod
    def get_current():
        err, ctx_handle = _drv.cuCtxGetCurrent()
        _check(err)
        if int(ctx_handle) == 0:
            return None
        return _Context(ctx_handle, owned=False)


Context = _ContextMeta()


class _Context:
    """模拟 pycuda 的 Context 对象"""
    __slots__ = ("_handle", "_owned")

    def __init__(self, handle, owned: bool = True):
        self._handle = handle
        self._owned = owned

    @property
    def handle(self):
        return self._handle

    def push(self):
        (err,) = _drv.cuCtxPushCurrent(self._handle)
        _check(err)

    def pop(self):
        err, _ = _drv.cuCtxPopCurrent()
        _check(err)

    def __del__(self):
        pass  # 不销毁借用的 context


# ---------------------------------------------------------------------------
# Device
# ---------------------------------------------------------------------------

class Device:
    """对应 pycuda.driver.Device(n)"""
    __slots__ = ("_handle", "_ordinal")

    def __init__(self, ordinal: int = 0):
        err, handle = _drv.cuDeviceGet(int(ordinal))
        _check(err)
        self._handle = handle
        self._ordinal = ordinal

    def retain_primary_context(self) -> _Context:
        err, ctx_h = _drv.cuDevicePrimaryCtxRetain(self._handle)
        _check(err)
        return _Context(ctx_h, owned=False)

    def make_context(self) -> _Context:
        err, ctx_h = _drv.cuCtxCreate(0, self._handle)
        _check(err)
        return _Context(ctx_h, owned=True)

    def compute_capability(self) -> tuple:
        err, major = _drv.cuDeviceGetAttribute(
            _drv.CUdevice_attribute.CU_DEVICE_ATTRIBUTE_COMPUTE_CAPABILITY_MAJOR,
            self._handle,
        )
        _check(err)
        err, minor = _drv.cuDeviceGetAttribute(
            _drv.CUdevice_attribute.CU_DEVICE_ATTRIBUTE_COMPUTE_CAPABILITY_MINOR,
            self._handle,
        )
        _check(err)
        return (major, minor)


# ---------------------------------------------------------------------------
# 异步内存拷贝
# ---------------------------------------------------------------------------

def memcpy_htod_async(dest: DeviceAllocation, src: np.ndarray, stream: Stream):
    """
    对应 pycuda.driver.memcpy_htod_async(dest, src, stream)。
    src 应为 pagelocked_empty 返回的数组。
    """
    nbytes = src.nbytes
    src_ptr = getattr(src, "_host_ptr", None) or src.ctypes.data
    (err,) = _drv.cuMemcpyHtoDAsync(int(dest), int(src_ptr), nbytes, stream._handle)
    _check(err)


def memcpy_dtoh_async(dest: np.ndarray, src: DeviceAllocation, stream: Stream):
    """
    对应 pycuda.driver.memcpy_dtoh_async(dest, src, stream)。
    dest 应为 pagelocked_empty 返回的数组。
    """
    nbytes = dest.nbytes
    dest_ptr = getattr(dest, "_host_ptr", None) or dest.ctypes.data
    (err,) = _drv.cuMemcpyDtoHAsync(int(dest_ptr), int(src), nbytes, stream._handle)
    _check(err)
