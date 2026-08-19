# 核心 Pipeline 数据流

## 1. 系统总体 Pipeline

```
用户按下瞄准键
       │
       ▼
┌─────────────────┐
│   屏幕截图捕获    │  devices/screenshot_manager.py
│  (BetterCam /    │  → 多线程分离架构
│   OBS / 采集卡)   │  → 内存池复用
└────────┬────────┘
         │ 图像帧 (numpy array)
         ▼
┌─────────────────┐
│    图像预处理     │  inference/infer_class.py → inference/infer_function.py
│  BGR→RGB         │
│  Resize → 模型尺寸│
│  Normalize /255  │
│  HWC → NCHW     │
└────────┬────────┘
         │ float32 tensor [1, 3, H, W]
         ▼
┌─────────────────┐
│    模型推理       │  inference/infer_class.py / inference/inference_engine.py
│  ONNX Runtime    │  → DML / CUDA / CPU
│    或 TensorRT   │  → CUDA Graph 加速
└────────┬────────┘
         │ 原始预测 [1, 84, 8400] (v8/v11)
         ▼
┌─────────────────┐
│    后处理 (NMS)   │  inference/infer_function.py → nms_v8 / nms_v5
│  置信度过滤       │
│  坐标格式统一     │  → cv2.dnn.NMSBoxes
│  非极大值抑制     │
└────────┬────────┘
         │ boxes [N, 4], scores [N], class_ids [N]
         ▼
┌─────────────────┐
│  投递到 que_aim   │  core/valorant.py → infer()
│  (Queue 大小=1)  │  → 最新帧覆盖旧帧
└────────┬────────┘
         │ dict: {boxes, class_ids, frame_id, ...}
         ▼
┌─────────────────┐
│  aim_bot 定时器   │  core/valorant.py → aim_bot_func() (1ms 周期)
│  消费推理结果     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ByteTrack 跟踪  │  aim/aim_pipeline.py → ByteTracker
│  IoU 匹配        │  → 匈牙利算法关联
│  稳定 track_id   │  → EMA 速度估计
└────────┬────────┘
         │ tracks with stable IDs
         ▼
┌─────────────────┐
│  目标优先级选择    │  aim/aim_pipeline.py → select_target_by_priority
│  距离评分         │
│  大小评分         │  → 粘滞/锁定机制
│  中心距评分       │  → 目标ID强锁定
│  小目标增强       │  → 宽限帧容错
└────────┬────────┘
         │ 最优目标 (screen_x, screen_y)
         ▼
┌─────────────────┐
│  卡尔曼预测       │  aim/aim_pipeline.py → 自维护速度估计
│  速度补偿         │  → 补偿自身鼠标移动
│  前馈偏移         │  → EMA 平滑 lead
└────────┬────────┘
         │ 预测位置 + 前馈偏移
         ▼
┌─────────────────┐
│  PID 控制器       │  aim/pid.py → DualAxisPID
│  误差计算         │  → 比例 + 积分 + 微分
│  误差滤波 (EMA)   │  → 速度滤波 (EMA)
│  平滑处理         │  → 指数平滑 / 时间常数
│  死区判断         │
└────────┬────────┘
         │ (dx, dy) 鼠标移动量
         ▼
┌─────────────────┐
│  亚像素量化       │  aim/aim_pipeline.py → AimMoveQuantizer
│  累积小数部分     │  → 防止截断误差
└────────┬────────┘
         │ (int_dx, int_dy)
         ▼
┌─────────────────┐
│  鼠标移动执行     │  core/valorant.py → execute_move()
│  km_net.move()   │
│  dhz.move()      │  → 根据 move_method 选择
│  catbox.move()   │
│  send_input()    │
└─────────────────┘
```

---

## 2. 推理线程 (infer) 详细流程

```python
def infer():  # 在 core/valorant.py 中
    while self.running:
        # 1. 获取截图
        screenshot = screenshot_manager.get_screenshot(region)
        
        # 2. 预处理
        # - BGR → RGB
        # - Resize 到模型输入尺寸 (如 320×320, 640×640)
        # - 归一化 /255.0
        # - 维度转换 HWC → NCHW
        input_tensor = preprocess(screenshot)
        
        # 3. 模型推理
        output = engine.infer(input_tensor)
        
        # 4. NMS 后处理
        boxes, scores, class_ids = nms_v8(output, conf_thres, iou_thres)
        
        # 5. 可视化(调试模式)
        if infer_debug:
            draw_boxes_v8(screenshot, boxes, scores, class_ids)
            cv2.imshow(...)
        
        # 6. 投递结果
        que_aim.put({boxes, class_ids, frame_id, ...})
        que_trigger.put(trigger_data)
```

---

## 3. 瞄准回调 (aim_bot_func) 详细流程

```python
def aim_bot_func():  # 1ms 定时器回调
    # 1. 判断控制模式
    if aim_key_pressed:
        mode = 'aim'
    elif crosshair_color_lock_enabled:
        mode = 'crosshair'
    else:
        mode = 'idle'
    
    # 2. 模式切换时重置 PID 和 Pipeline
    if mode_changed:
        reset_pid()
        aim_pipeline.reset()
    
    # 3. 瞄准模式
    if mode == 'aim':
        # 消费 que_aim 中的推理结果
        aim_data = que_aim.get_nowait()
        
        # 调用 AimPipeline.step_frame()
        move = aim_pipeline.step_frame(
            frame_payload=aim_data,
            pressed_key_config=current_key_config,
            cfg=global_config,
            center_xy=(screen_center_x, screen_center_y),
            aim_scope=dynamic_scope,
            ...
        )
        
        if move:
            execute_move(move[0], move[1])
        elif crosshair_enabled:
            try_crosshair_pull()
    
    # 4. 准星颜色锁定模式
    elif mode == 'crosshair':
        try_crosshair_pull()
```

---

## 4. AimPipeline 内部流程

```python
def step_frame(frame_payload, config, ...):
    # 1. 数据规范化
    boxes, class_ids = normalize(frame_payload)
    
    # 2. 构建目标元数据 + 屏幕坐标
    det_boxes = compute_screen_boxes(boxes)
    det_meta = compute_aim_points(boxes, class_ids, aim_position)
    
    # 3. ByteTrack 更新
    tracks = tracker.update(det_boxes, scores, class_ids)
    
    # 4. 关联 track → det_meta
    targets = associate_tracks_to_detections(tracks, det_meta)
    
    # 5. 小目标平滑 (可选)
    targets = smooth_small_targets(targets)
    
    # 6. 目标优先级选择
    selected = select_target_by_priority(targets, aim_scope, center)
    #   ├── ID 强锁定检查
    #   ├── 锁定冷却检查  
    #   ├── 距离排序
    #   └── 粘滞保持
    
    # 7. 移动预测 (速度补偿)
    lead_x, lead_y = compute_prediction(selected, prev_output)
    
    # 8. PID 控制
    error_x = target_x - screen_center_x
    error_y = target_y - screen_center_y
    pid_output = pid.compute(error_x, error_y)
    
    # 9. 叠加前馈
    output = pid_output + (lead_x, lead_y)
    
    # 10. 量化
    int_dx, int_dy = quantizer.quantize(output)
    
    return (int_dx, int_dy)
```

---

## 5. 触发器 Pipeline

```python
def trigger():  # 独立线程
    while self.running:
        trigger_data = que_trigger.get()
        
        # 检查是否有目标在触发范围内
        if target_in_trigger_scope(trigger_data):
            # 延迟等待
            sleep(start_delay + random_delay)
            
            # 执行点击
            mouse_left_down()
            sleep(press_delay)
            mouse_left_up()
            
            # 结束延迟
            sleep(end_delay)
```

---

## 6. 准星颜色锁定 Pipeline

```
截图 ROI 区域 (准星周围 200×200)
       │
       ▼
  BGR → HSV 转换
       │
       ▼
  HSV 范围掩码 (inRange)
       │
       ▼
  形态学处理 (开运算 + 闭运算)
       │
       ▼
  轮廓检测 + 面积过滤
       │
       ▼
  计算目标中心偏移
       │
       ▼
  EMA 时间平滑
       │
       ▼
  回拉鼠标 (pull_k * offset)
```

---

## 7. 动态瞄准范围

```
按下瞄准键
    │
    ▼
aim_scope = max_scope (初始值)
    │
    │ 持续按住
    ▼
aim_scope 按时间缩小 → min_scope
    │
    │ (shrink_duration_ms)
    │
松开瞄准键
    │
    ▼
aim_scope 按时间恢复 → max_scope
    │
    │ (recover_duration_ms)
```

---

## 8. 数据格式定义

### 推理结果 (que_aim 中的数据)

```python
{
    'boxes': np.ndarray,       # [N, 4] — cx, cy, w, h
    'class_ids': list[int],    # [N] — 类别ID
    'frame_id': int,           # 帧唯一标识
    'input_w': float,          # 模型输入宽度
    'input_h': float,          # 模型输入高度
}
```

### 目标对象 (Pipeline 内部)

```python
{
    'pos': (float, float),     # 瞄准点屏幕坐标 (x, y)
    'size': float,             # 大小评分 (含 boost)
    'absolute_size': float,    # 检测框面积 (像素²)
    'relative_size': float,    # 相对面积 (/ model_area)
    'class_id': int,           # 类别ID
    'aim_position': float,     # 瞄准高度比例 (0~1)
    'id': int,                 # track_id (ByteTrack)
    'track_id': int,           # 同上
    'velocity': [float, float],# 速度估计 (像素/帧)
    'distance_to_center': float,# 到屏幕中心距离
    'box_w': float,            # 检测框宽度
    'box_h': float,            # 检测框高度
}
```
