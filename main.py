# -*- coding: utf-8 -*-
import ctypes
from ctypes import *
import time
from queue import Queue
import _ctypes
import _queue
from threading import Thread
import cv2
import bettercam
import win32api
import win32con
import win32gui
from pynput import keyboard, mouse
from function import *
from infer_class import *
import onnxruntime as rt
from infer_function import *
from function import *
import json
import math
import win32gui
from cryptography.fernet import Fernet
import cv2
import numpy as np
import requests
import os
import random
import string
import kmNet
from dearpygui import dearpygui as dpg
import base64
import websocket
from concurrent.futures import ThreadPoolExecutor
import pyclick
from pyclick import HumanCurve
import pydirectinput
import serial
import serial.tools.list_ports
from core import *
import sys
import traceback


def global_exception_hook(exctype, value, tb):
    """
    全局异常钩子，用于捕获所有未处理的异常。
    """
    # 将详细的异常信息写入日志文件
    with open('error_log.txt', 'a', encoding='utf-8') as f:
        f.write(f"[全局异常] {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(''.join(traceback.format_exception(exctype, value, tb)))
        f.write('\n')
    # 向用户显示友好的错误提示
    print('程序发生未捕获异常，详细信息已写入 error_log.txt。请将该文件反馈给开发者。')

# 设置自定义的全局异常处理器
sys.excepthook = global_exception_hook

def handle_tensorrt_error():
    """
    处理与TensorRT相关的导入或初始化错误。
    """
    # 在控制台打印详细的指导信息
    print('\n==================================================')
    print('检测到TensorRT相关错误，但程序会继续使用ONNX推理运行')
    print('如果您想使用TensorRT加速，请安装以下组件：')
    print('1. CUDA Toolkit')
    print('2. cuDNN')
    print('3. TensorRT')
    print('4. 具体配置教程查看:https://www.yuque.com/huiyestudio/dqrld3/rislyof9zegdfira')
    print('==================================================\n')
    
    # 将错误信息记录到文件中
    with open('tensorrt_error.txt', 'a', encoding='utf-8') as f:
        f.write(f"[TensorRT未安装] {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write('程序将使用ONNX推理继续运行\n\n')

# 主程序入口

if __name__ == '__main__':
    valorant_instance = None
    try:
        print('跳过远程配置验证，直接启动程序...')
        # 直接启动主程序，跳过网络验证
        valorant_instance = Valorant()
        valorant_instance.start()
    except ImportError as e:
        # 捕获导入错误，特别是与TensorRT相关的
        error_str = str(e).lower()
        if 'tensorrt' in error_str or 'cuda' in error_str or 'nvinfer' in error_str:
            handle_tensorrt_error()
            valorant_instance = Valorant()
            valorant_instance.start()
        else:
            raise
    except OSError as e:
        # 捕获操作系统错误，也可能是由GPU库缺失引起
        error_str = str(e).lower()
        if 'nvinfer' in error_str or 'cudnn' in error_str or 'cuda' in error_str:
            handle_tensorrt_error()
            valorant_instance = Valorant()
            valorant_instance.start()
        else:
            raise
    except Exception as e:
        # 捕获所有其他启动过程中的异常
        with open('error_log.txt', 'w', encoding='utf-8') as f:
            f.write(traceback.format_exc())
        print('程序发生错误，详细信息已写入 error_log.txt。请将该文件反馈给开发者。')
        input('按回车键退出...')
    finally:
        # 确保程序退出时执行资源清理
        if valorant_instance is not None:
            try:
                print('正在清理程序资源...')
                valorant_instance._secure_cleanup()
                print('程序资源清理完成')
            except Exception as e:
                # 处理清理过程中可能发生的异常
                print(f"清理程序资源时出错: {e}")
                with open('error_log.txt', 'a', encoding='utf-8') as f:
                    f.write(f"[资源清理异常] {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"清理错误: {str(e)}\n")
                    f.write(traceback.format_exc())
                    f.write('\n')