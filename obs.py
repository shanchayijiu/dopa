import time
import cv2
import queue
from concurrent.futures import ThreadPoolExecutor

class OBSVideoStream:

    def __init__(self, ip='0.0.0.0', port=4455, fps=240):
        self.ip = ip
        self.port = port
        self.buffer_size = 0
        self.fps = fps
        self.udp_url = f'udp://{self.ip}:{self.port}'
        self.executor = None
        self.frame_queue = queue.Queue(maxsize=1)
        self.screenshot_queue = queue.Queue(maxsize=1)
        self.cap = None
        self.running = False
        self.latency_stats = {'frames_received': 0, 'frames_dropped': 0, 'decode_times': []}

    def print_latency_report(self):
        """打印延迟统计报告"""
        try:
            total_frames = self.latency_stats['frames_received']
            dropped_frames = self.latency_stats['frames_dropped']
            decode_times = self.latency_stats['decode_times']
            if total_frames == 0:
                print('OBS延迟报告: 未接收到任何帧')
                return
            drop_rate = dropped_frames / total_frames * 100 if total_frames > 0 else 0
            if decode_times:
                avg_decode = sum(decode_times) / len(decode_times)
                min_decode = min(decode_times)
                max_decode = max(decode_times)
                print(f'解码延迟: 平均{avg_decode:.2f}ms, 最小{min_decode:.2f}ms, 最大{max_decode:.2f}ms')
            print('========================\n')
        except Exception as e:
            print(f'打印延迟报告失败: {e}')

    def _read_frame(self):
        """读取视频帧并将其放入队列 - 延迟优化版本"""
        consecutive_failures = 0
        max_failures = 10
        while self.running:
            try:
                if self.cap is None or not self.cap.isOpened():
                    print('OBS视频流已关闭，退出读取线程')
                    break
                start_time = time.perf_counter()
                ret, frame = self.cap.read()
                if not ret:
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        print(f'连续失败 {max_failures} 次，停止OBS读取')
                        break
                    print('无法读取视频帧，正在重试...')
                    time.sleep(0.1)
                    continue
                consecutive_failures = 0
                decode_time = time.perf_counter() - start_time
                self.latency_stats['decode_times'].append(decode_time * 1000)
                if len(self.latency_stats['decode_times']) > 100:
                    self.latency_stats['decode_times'].pop(0)
                self.latency_stats['frames_received'] += 1
                if self.frame_queue.full():
                    try:
                        self.frame_queue.get_nowait()
                        self.latency_stats['frames_dropped'] += 1
                    except queue.Empty:
                        pass
                try:
                    self.frame_queue.put_nowait(frame)
                except queue.Full:
                    self.latency_stats['frames_dropped'] += 1
            except Exception as e:
                if self.cap is None:
                    print('OBS读取线程: 视频流已关闭')
                    break
                error_str = str(e)
                if 'Unknown C++ exception from OpenCV code' in error_str or 'NoneType' in error_str:
                    print('OBS读取线程: 检测到OpenCV流关闭异常，退出线程')
                    break
                print(f'OBS读取帧异常: {e}')
                time.sleep(0.01)
        print('OBS读取线程已退出')

    def start(self):
        """启动视频流读取和显示"""
        self.cap = cv2.VideoCapture(self.udp_url)
        low_latency_configs = [(cv2.CAP_PROP_BUFFERSIZE, 1), (cv2.CAP_PROP_FPS, self.fps)]
        for prop, value in low_latency_configs:
            try:
                self.cap.set(prop, value)
            except Exception as e:
                print(f'OBS配置 {prop}={value} 失败: {e}')
        width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
        buffer_size = self.cap.get(cv2.CAP_PROP_BUFFERSIZE)
        if not self.cap.isOpened():
            print('无法打开OBS UDP流')
            return False
        self.running = True
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.executor.submit(self._read_frame)
        return True

    def close(self):
        """关闭视频流并释放资源"""
        print('正在关闭OBS视频流...')
        self.running = False
        if self.executor:
            try:
                self.executor.shutdown(wait=True)
                print('OBS线程池已安全关闭')
            except Exception as e:
                print(f'关闭OBS线程池异常: {e}')
            self.executor = None
        try:
            if self.latency_stats['frames_received'] > 0:
                self.print_latency_report()
        except Exception as e:
            print(f'打印OBS延迟报告失败: {e}')
        if self.cap:
            try:
                self.cap.release()
                print('OBS视频流已关闭')
            except Exception as e:
                print(f'关闭视频流异常: {e}')
            finally:
                self.cap = None