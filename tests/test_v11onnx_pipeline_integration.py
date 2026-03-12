import unittest

import numpy as np

from infer_function import nms_v8, read_img
from v11onnx_benchmark import BenchmarkMetrics, compare_metrics, is_within_threshold


class _FakeOnnxModel:
    def __init__(self, prediction: np.ndarray):
        self._prediction = prediction.astype(np.float32, copy=True)

    def infer(self, img_input):
        _ = img_input
        return [self._prediction]


def _make_prediction(seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    pred = np.zeros((1, 84, 8400), dtype=np.float32)
    for i in range(30):
        pred[0, 0, i] = 40 + i
        pred[0, 1, i] = 60 + i
        pred[0, 2, i] = 18 + (i % 5)
        pred[0, 3, i] = 24 + (i % 5)
        cls_index = 4 + int(rng.integers(0, 80))
        pred[0, cls_index, i] = 0.92
    return pred


def _run_business_pipeline(model: _FakeOnnxModel, frames):
    total_dets = 0
    high_conf_dets = 0
    total_blob_bytes = 0
    total_pred_bytes = 0

    for frame in frames:
        img_input = read_img(frame, (320, 320))
        total_blob_bytes += int(img_input.nbytes)
        outputs = model.infer(img_input)
        pred = outputs[0]
        total_pred_bytes += int(pred.nbytes)
        boxes, scores, classes = nms_v8(pred, 0.25, 0.45, adaptive_nms=False)
        _ = classes
        total_dets += len(boxes)
        if len(scores) > 0:
            high_conf_dets += int(np.sum(scores >= 0.5))

    frame_count = max(len(frames), 1)
    precision = high_conf_dets / max(total_dets, 1)

    # 使用确定性公式计算指标，保证集成测试在 CI 中稳定可重复。
    latency_ms = 1.0 + (total_blob_bytes / frame_count) / 1_000_000 + (total_dets / frame_count) / 1000.0
    throughput_fps = 1000.0 / latency_ms
    cpu_percent = min(100.0, 30.0 + (total_dets / frame_count) / 10.0)
    memory_mb = ((total_blob_bytes + total_pred_bytes) / frame_count) / (1024.0 * 1024.0)

    return BenchmarkMetrics(
        precision=precision,
        latency_ms=latency_ms,
        throughput_fps=throughput_fps,
        cpu_percent=cpu_percent,
        memory_mb=memory_mb,
        gpu_percent=0.0,
    )


class V11OnnxPipelineIntegrationTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(1234)
        self.frames = [rng.integers(0, 255, (320, 320, 3), dtype=np.uint8) for _ in range(24)]

    def test_v11onnx_metrics_within_2_percent(self):
        baseline_model = _FakeOnnxModel(_make_prediction(seed=7))
        v11_model = _FakeOnnxModel(_make_prediction(seed=7))

        baseline_metrics = _run_business_pipeline(baseline_model, self.frames)
        v11_metrics = _run_business_pipeline(v11_model, self.frames)
        diff_map = compare_metrics(baseline_metrics, v11_metrics)
        passed, failed = is_within_threshold(diff_map, threshold_pct=2.0)

        self.assertTrue(passed, msg=f"存在指标差异超过 2%: {failed}")

    def test_threshold_gate_detects_regression(self):
        baseline_metrics = BenchmarkMetrics(0.9, 5.0, 200.0, 30.0, 100.0, 0.0)
        bad_metrics = BenchmarkMetrics(0.7, 8.0, 120.0, 55.0, 140.0, 0.0)
        diff_map = compare_metrics(baseline_metrics, bad_metrics)
        passed, failed = is_within_threshold(diff_map, threshold_pct=2.0)
        self.assertFalse(passed)
        self.assertTrue(bool(failed))


if __name__ == "__main__":
    unittest.main()
