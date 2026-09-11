"""生成 320x320 的 YOLOv8n ONNX（零训练，仅对现成 640 权重做图改造）。

现成的 COCO yolov8n.onnx 是固定 640 输入，本项目靶场用 320 更省算力。
YOLOv8 的检测头把锚点网格以常量形式烘进图里，直接改输入尺寸会维度不匹配；
本脚本把输入尺寸改为 320，并同步重建三处被烘死的常量：
  - 锚点网格 (1,2,N) 与步长张量 (1,N)
  - DFL reshape 的 N（8400 -> 2100）
之后清空过期的 value_info，导出可直接被 onnxruntime/DML 加载的 320 模型。
用法:
  python -m sim.make_320_model [--src URL] [--out models/yolov8n_320.onnx] [--size 320]
"""
from __future__ import annotations

import argparse
import os
import urllib.request

import numpy as np
import onnx
from onnx import numpy_helper

DEFAULT_SRC = "https://hf-mirror.com/Kalray/yolov8/resolve/main/yolov8n.onnx"
STRIDES = (8, 16, 32)


def _download(url: str, dst: str):
    if os.path.isfile(dst) and os.path.getsize(dst) > 1_000_000:
        print(f"已存在，跳过下载: {dst}")
        return dst
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    print(f"下载 {url}")
    urllib.request.urlretrieve(url, dst)
    print(f"已保存: {dst} ({os.path.getsize(dst)} bytes)")
    return dst


def _make_anchors(size: int, strides=STRIDES):
    xs, ys, ss = [], [], []
    for s in strides:
        n = size // s
        gy, gx = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
        xs.append(gx.reshape(-1).astype(np.float32) + 0.5)
        ys.append(gy.reshape(-1).astype(np.float32) + 0.5)
        ss.append(np.full(n * n, float(s), dtype=np.float32))
    anchors = np.stack([np.concatenate(xs), np.concatenate(ys)], axis=0).reshape(1, 2, -1)
    return anchors, np.concatenate(ss).reshape(1, -1)


def convert(src: str, dst: str, size: int = 320) -> str:
    m = onnx.load(src)
    n_old = 8400
    n_new = sum((size // s) ** 2 for s in STRIDES)
    anchors, strides = _make_anchors(size)

    for i in m.graph.input:
        if i.name == "images":
            i.type.tensor_type.shape.dim[2].dim_value = size
            i.type.tensor_type.shape.dim[3].dim_value = size
    for o in m.graph.output:
        if len(o.type.tensor_type.shape.dim) >= 3:
            o.type.tensor_type.shape.dim[2].dim_value = n_new

    replace = {
        "/model.22/Constant_9_output_0": anchors,
        "/model.22/Constant_10_output_0": anchors,
        "/model.22/Constant_12_output_0": strides,
    }
    patched = 0
    for init in list(m.graph.initializer):
        if init.name in replace:
            init.CopyFrom(numpy_helper.from_array(replace[init.name].astype(np.float32), init.name))
            patched += 1
        else:
            a = numpy_helper.to_array(init)
            if a.size <= 8 and a.dtype.kind == "i" and n_old in a.reshape(-1).tolist():
                v = a.reshape(-1)
                init.CopyFrom(
                    numpy_helper.from_array(
                        np.where(v == n_old, n_new, v).astype(a.dtype).reshape(a.shape), init.name
                    )
                )
                patched += 1

    del m.graph.value_info[:]
    onnx.save(m, dst)
    print(f"改造完成: 输入 {size}x{size}, 锚点 {n_new}, 补丁 {patched} 处 -> {dst}")
    return dst


def verify(path: str, size: int = 320):
    import onnxruntime as ort

    sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    shape = sess.get_inputs()[0].shape
    out = sess.run(None, {sess.get_inputs()[0].name: np.zeros((1, 3, size, size), dtype=np.float32)})
    print(f"校验: input={shape} output={out[0].shape}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default=DEFAULT_SRC)
    parser.add_argument("--out", default=os.path.join("models", "yolov8n_320.onnx"))
    parser.add_argument("--size", type=int, default=320)
    parser.add_argument("--cache", default=os.path.join("models", "_yolov8n_640_src.onnx"))
    parser.add_argument("--no-verify", action="store_true")
    args = parser.parse_args()
    src = _download(args.src, args.cache)
    convert(src, args.out, args.size)
    if not args.no_verify:
        verify(args.out, args.size)


if __name__ == "__main__":
    main()
