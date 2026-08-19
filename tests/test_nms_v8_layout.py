import unittest

import numpy as np

from inference.infer_function import nms_v8


def _build_single_class_pred(layout: str = "c_n", count: int = 16):
    # box: cx, cy, w, h, conf
    pred_nc = np.zeros((count, 5), dtype=np.float32)
    for i in range(count):
        pred_nc[i, 0] = 80 + i
        pred_nc[i, 1] = 80 + i
        pred_nc[i, 2] = 20
        pred_nc[i, 3] = 20
        pred_nc[i, 4] = 0.9 if i % 2 == 0 else 0.2

    if layout == "c_n":
        return pred_nc.T[np.newaxis, :, :]  # [1, 5, N]
    if layout == "n_c":
        return pred_nc[np.newaxis, :, :]  # [1, N, 5]
    raise ValueError(layout)


class NmsV8LayoutTests(unittest.TestCase):
    def test_supports_c_n_layout(self):
        pred = _build_single_class_pred("c_n")
        boxes, scores, classes = nms_v8(pred, conf_thres=0.5, iou_thres=0.45, adaptive_nms=False)
        self.assertGreater(len(boxes), 0)
        self.assertEqual(len(boxes), len(scores))
        self.assertEqual(len(boxes), len(classes))
        self.assertTrue(np.all(classes == 0))

    def test_supports_n_c_layout(self):
        pred = _build_single_class_pred("n_c")
        boxes, scores, classes = nms_v8(pred, conf_thres=0.5, iou_thres=0.45, adaptive_nms=False)
        self.assertGreater(len(boxes), 0)
        self.assertEqual(len(boxes), len(scores))
        self.assertEqual(len(boxes), len(classes))
        self.assertTrue(np.all(classes == 0))

    def test_normalized_boxes_not_over_suppressed(self):
        # 两个距离很远的归一化框，NMS 后应都保留。
        pred_nc = np.zeros((8, 5), dtype=np.float32)
        pred_nc[0] = [0.2, 0.2, 0.1, 0.1, 0.95]
        pred_nc[1] = [0.8, 0.8, 0.1, 0.1, 0.93]
        pred = pred_nc.T[np.newaxis, :, :]  # [1, 5, N]
        boxes, scores, classes = nms_v8(pred, conf_thres=0.5, iou_thres=0.45, adaptive_nms=False)
        _ = scores
        _ = classes
        self.assertGreaterEqual(len(boxes), 2)


if __name__ == "__main__":
    unittest.main()
