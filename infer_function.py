import cv2
import numpy as np

# 1.0 / 255 —— 像素归一化因子
NORMALIZE_FACTOR = 1.0 / 255  # 0.00392156862745098

# NMS 空结果常量，避免每次早返时分配新数组
_EMPTY_NMS_RESULT = (
    np.empty((0, 4), dtype=np.float32),
    np.empty((0,), dtype=np.float32),
    np.empty((0,), dtype=np.int32),
)

try:
    import numba as nb
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
if NUMBA_AVAILABLE:

    @nb.njit(parallel=True, fastmath=True)
    def numba_convert_new_array(src):
        """Numba优化转换,返回新数组"""
        dst = np.empty_like(src, dtype=np.float32)
        for i in nb.prange(src.shape[0]):
            for j in nb.prange(src.shape[1]):
                for k in range(src.shape[2]):
                    dst[i, j, k] = src[i, j, k] * 0.00392156862745098
        return dst

    @nb.njit(parallel=True, fastmath=True)
    def numba_resize_and_normalize(src, target_h, target_w):
        """Numba优化的resize和归一化"""
        dst = np.empty((target_h, target_w, 3), dtype=np.float32)
        scale_h = src.shape[0] / target_h
        scale_w = src.shape[1] / target_w
        for i in nb.prange(target_h):
            for j in nb.prange(target_w):
                src_i = int(i * scale_h)
                src_j = int(j * scale_w)
                if src_i >= src.shape[0]:
                    src_i = src.shape[0] - 1
                if src_j >= src.shape[1]:
                    src_j = src.shape[1] - 1
                dst[i, j, 0] = src[src_i, src_j, 2] * 0.00392156862745098
                dst[i, j, 1] = src[src_i, src_j, 1] * 0.00392156862745098
                dst[i, j, 2] = src[src_i, src_j, 0] * 0.00392156862745098
        return dst

def draw_boxes(image, boxes, scores, classes):
    for box, score, classe in zip(boxes, scores, classes):
        box = box[:4]
        class_id = np.argmax(classe)
        c_x, c_y, w, h = box.astype(np.int32)
        x_min, y_min, x_max, y_max = convert_box_coordinates(c_x, c_y, w, h)
        color = get_color(class_id)
        thickness = 2
        cv2.rectangle(image, (x_min, y_min), (x_max, y_max), color, thickness)
        text = f'{class_id} {score:.2f}'
        cv2.putText(image, text, (x_min, y_min - 5), cv2.FONT_HERSHEY_PLAIN, 1, color, thickness)
    return image

def draw_boxes_v8(image, boxes, scores, classes, class_names=None):
    """
    在图像上绘制检测框
    Args:
        image: 原始图像
        boxes: 边界框坐标 [x1, y1, x2, y2]
        scores: 置信度分数
        classes: 类别ID
        class_names: 类别名称列表(可选)
    Returns:
        image: 绘制了检测框的图像
    """
    image = image.copy()
    height, width = image.shape[:2]
    for box, score, class_id in zip(boxes, scores, classes):
        class_id = int(class_id)
        box = np.asarray(box[:4], dtype=np.float32)
        if box.shape[0] < 4:
            continue
        if not np.all(np.isfinite(box)):
            continue
        if float(box[2]) <= 0.0 or float(box[3]) <= 0.0:
            continue
        c_x, c_y, w, h = np.rint(box).astype(np.int32)
        x1, y1, x2, y2 = convert_box_coordinates(c_x, c_y, w, h)
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(width, x2)
        y2 = min(height, y2)
        if x2 <= x1 or y2 <= y1:
            continue
        color = get_color(class_id)
        thickness = 2
        cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness)
        text = f'{class_id} {score:.2f}'
        cv2.putText(image, text, (x1, y1 - 5), cv2.FONT_HERSHEY_PLAIN, 1, color, thickness)
    return image

def get_color(class_id):
    """
    为每个类别生成唯一且易于区分的颜色
    """
    predefined_colors = [(0, 255, 0), (255, 0, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255), (128, 0, 255), (255, 128, 0), (0, 255, 128), (255, 0, 128)]
    if class_id < len(predefined_colors):
        return predefined_colors[class_id]
    np.random.seed(class_id)
    color = tuple(map(int, np.random.randint(0, 255, size=3)))
    return color

def draw_fps(image, fps):
    text = f'FPS: {fps:.2f}'
    cv2.putText(image, text, (10, 30), cv2.FONT_HERSHEY_PLAIN, 1, (0, 255, 0), 1)
    return image

def convert_box_coordinates(center_x, center_y, width, height):
    x_min = int(center_x - width / 2)
    y_min = int(center_y - height / 2)
    x_max = int(center_x + width / 2)
    y_max = int(center_y + height / 2)
    return (x_min, y_min, x_max, y_max)

def convert_box_coordinates_float(center_x, center_y, width, height):
    x_min = center_x - width / 2
    y_min = center_y - height / 2
    x_max = center_x + width / 2
    y_max = center_y + height / 2
    return (x_min, y_min, x_max, y_max)

def nms_v8(pred, conf_thres, iou_thres, adaptive_nms=True):
    """
    处理YOLO预测输出，执行置信度过滤和NMS，返回最终的检测结果。
    优化版本：使用 cv2.dnn.NMSBoxes 提升性能并解决闪烁问题。

    Args:
        pred: 模型输出的特征图 (1, 84, 8400) 或 (1, N, 4+C)。
        conf_thres: 置信度阈值。
        iou_thres: IoU阈值。
        adaptive_nms: 是否启用自适应NMS（在cv2版本中暂通过调整阈值模拟或忽略）。

    Returns:
        boxes: 最终保留的边界框坐标 (x1, y1, x2, y2)。
        scores: 置信度分数。
        classes: 类别标签。
    """
    pred = np.asarray(pred)
    pred = np.squeeze(pred)
    
    # 维度检查与转置处理
    if pred.ndim != 2:
        return _EMPTY_NMS_RESULT

    # 兼容 [C,N] / [N,C] 两种布局
    # YOLOv8/v11 默认输出通常是 [C, N] (例如 [84, 8400])，需要转置为 [N, C]
    r, c = pred.shape
    if r < c and r <= 256: 
        pred = pred.T
        
    if pred.shape[1] < 5:
        return _EMPTY_NMS_RESULT

    # 解析 Box, Score, Class
    # 假设前4列是 cx, cy, w, h
    attr_count = pred.shape[1]
    
    if attr_count == 5:
        # 单类模型: [cx, cy, w, h, conf]
        scores = pred[:, 4]
        class_ids = np.zeros_like(scores, dtype=np.int32)
    else:
        # 多类模型: [cx, cy, w, h, class1, class2, ...]
        # 这种情况下，我们需要找出每个框的最大类别概率
        # 为了性能，先过滤掉低置信度的
        class_scores = pred[:, 4:]
        class_ids = np.argmax(class_scores, axis=1).astype(np.int32)
        scores = np.max(class_scores, axis=1)

    # 初步置信度过滤
    valid_mask = scores > conf_thres
    if not np.any(valid_mask):
        return _EMPTY_NMS_RESULT

    pred_boxes = pred[valid_mask, :4].astype(np.float32)
    scores = scores[valid_mask]
    class_ids = class_ids[valid_mask]

    # 1. 统一坐标格式为 cx, cy, w, h
    # 自动检测是否为 xyxy 格式 (x1, y1, x2, y2)
    if pred_boxes.shape[0] > 0:
        # 采样检测，避免全量计算
        sample_size = min(100, pred_boxes.shape[0])
        sample = pred_boxes[:sample_size]
        # xyxy 特征: x2 > x1 且 y2 > y1
        # cxcywh 特征: w > 0, h > 0, 但 w > cx 不一定成立
        xyxy_check = (sample[:, 2] > sample[:, 0]) & (sample[:, 3] > sample[:, 1])
        
        # 如果绝大多数样本满足 x2 > x1 且 y2 > y1，则判定为 xyxy
        if xyxy_check.sum() > sample_size * 0.9:
            x1 = pred_boxes[:, 0]
            y1 = pred_boxes[:, 1]
            x2 = pred_boxes[:, 2]
            y2 = pred_boxes[:, 3]
            
            w = x2 - x1
            h = y2 - y1
            cx = x1 + w / 2
            cy = y1 + h / 2
            
            # 更新为 cx, cy, w, h
            pred_boxes = np.stack([cx, cy, w, h], axis=1)

    # 2. 准备 OpenCV NMS 输入: [x, y, w, h] (左上角坐标)
    cx = pred_boxes[:, 0]
    cy = pred_boxes[:, 1]
    w = pred_boxes[:, 2]
    h = pred_boxes[:, 3]
    
    # 确保宽高非负
    w = np.maximum(w, 0.0)
    h = np.maximum(h, 0.0)
    
    x = cx - w / 2
    y = cy - h / 2
    
    nms_boxes = np.stack([x, y, w, h], axis=1).astype(np.float32)
    nms_scores = scores.astype(np.float32)
    
    # 3. 执行 NMS
    indices = cv2.dnn.NMSBoxes(nms_boxes, nms_scores, conf_thres, iou_thres)

    if len(indices) == 0:
        return _EMPTY_NMS_RESULT

    indices = np.array(indices).flatten()
    
    # 4. 返回结果 (保持 cx, cy, w, h 格式，与原版 nms_v8 一致)
    final_boxes = pred_boxes[indices]
    final_scores = scores[indices]
    final_classes = class_ids[indices]
    
    return final_boxes, final_scores, final_classes

def nms_v5(pred, confidence_threshold, iou_threshold, class_num):
    pred = np.array(pred)
    if len(pred) == 0:
        return ([], [], [])
    pred = pred.reshape(-1, 5 + class_num)
    boxes = pred[:, :4]
    scores = pred[:, 4]
    class_probs = pred[:, 5:]
    mask = scores > confidence_threshold
    if not np.any(mask):
        return ([], [], [])
    boxes = boxes[mask]
    scores = scores[mask]
    class_probs = class_probs[mask]
    start_x = boxes[:, 0] - boxes[:, 2] / 2
    start_y = boxes[:, 1] - boxes[:, 3] / 2
    end_x = boxes[:, 0] + boxes[:, 2] / 2
    end_y = boxes[:, 1] + boxes[:, 3] / 2
    boxes = np.stack([start_x, start_y, end_x, end_y], axis=1)
    areas = (end_x - start_x) * (end_y - start_y)
    results_boxes, results_scores, results_classes = ([], [], [])
    for cls_idx in range(class_num):
        cls_scores = class_probs[:, cls_idx]
        mask = cls_scores > 0
        if not np.any(mask):
            continue
        cls_boxes = boxes[mask]
        cls_scores = scores[mask] * cls_scores[mask]
        order = np.argsort(cls_scores)[::-1]
        keep = []
        while len(order) > 0:
            i = order[0]
            keep.append(i)
            xx1 = np.maximum(cls_boxes[i, 0], cls_boxes[order[1:], 0])
            yy1 = np.maximum(cls_boxes[i, 1], cls_boxes[order[1:], 1])
            xx2 = np.minimum(cls_boxes[i, 2], cls_boxes[order[1:], 2])
            yy2 = np.minimum(cls_boxes[i, 3], cls_boxes[order[1:], 3])
            inter_w = np.maximum(0, xx2 - xx1)
            inter_h = np.maximum(0, yy2 - yy1)
            intersection = inter_w * inter_h
            iou = intersection / (areas[i] + areas[order[1:]] - intersection)
            order = order[1:][iou <= iou_threshold]
        results_boxes.append(cls_boxes[keep])
        results_scores.append(cls_scores[keep])
        results_classes.extend([cls_idx] * len(keep))
    if results_boxes:
        results_boxes = np.vstack(results_boxes)
        results_scores = np.hstack(results_scores)
    else:
        results_boxes, results_scores = (np.array([]), np.array([]))
    return (results_boxes, results_scores, np.array(results_classes))

def nms(pred, confidence_threshold, iou_threshold, class_num):
    pred = np.array(pred)
    if len(pred) == 0:
        return ([], [], [])
    pred = pred.reshape(-1, 5 + class_num)
    boxes = pred[:, :4]
    scores = pred[:, 4]
    classes = pred[:, 5:]
    indexs = np.where(scores > confidence_threshold)
    boxes, scores, classes = (boxes[indexs], scores[indexs], classes[indexs])
    start_x = boxes[:, 0] - boxes[:, 2] / 2
    start_y = boxes[:, 1] - boxes[:, 3] / 2
    end_x = boxes[:, 0] + boxes[:, 2] / 2
    end_y = boxes[:, 1] + boxes[:, 3] / 2
    areas = (end_x - start_x + 1) * (end_y - start_y + 1)
    order = np.argsort(scores)
    keep = []
    while order.size > 0:
        index = order[-1]
        keep.append(index)
        x1 = np.maximum(start_x[index], start_x[order[:-1]])
        x2 = np.minimum(end_x[index], end_x[order[:-1]])
        y1 = np.maximum(start_y[index], start_y[order[:-1]])
        y2 = np.minimum(end_y[index], end_y[order[:-1]])
        w = np.maximum(0.0, x2 - x1 + 1)
        h = np.maximum(0.0, y2 - y1 + 1)
        intersection = w * h
        ratio = intersection / (areas[index] + areas[order[:-1]] - intersection)
        left = np.where(ratio <= iou_threshold)
        order = order[left]
    if not keep:
        return ([], [], [])
    keep = np.array(keep)
    boxes = boxes[keep]
    scores = scores[keep]
    classes = classes[keep]
    return (boxes, scores, classes)

def read_img(img_data, size=(320, 320)):
    target_w, target_h = size
    if NUMBA_AVAILABLE and target_w == 640 and (target_h == 640):
        try:
            resized_img = cv2.resize(img_data, (target_w, target_h))
            normalized_img = numba_convert_new_array(resized_img)
            processed_img = normalized_img[:, :, [2, 1, 0]]
            blob = np.transpose(processed_img, (2, 0, 1))
            blob = np.expand_dims(blob, axis=0)
            return blob
        except Exception as e:
            print(f'numba预处理回退: {e}')
    blob = cv2.dnn.blobFromImage(image=img_data, scalefactor=NORMALIZE_FACTOR, size=(target_w, target_h), mean=(0.0, 0.0, 0.0), swapRB=True, crop=False)
    return blob
