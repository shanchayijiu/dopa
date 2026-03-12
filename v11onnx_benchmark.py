import argparse
import json
from dataclasses import asdict, dataclass
from typing import Dict, Tuple


@dataclass
class BenchmarkMetrics:
    precision: float
    latency_ms: float
    throughput_fps: float
    cpu_percent: float
    memory_mb: float
    gpu_percent: float = 0.0


def compare_metrics(
    baseline: BenchmarkMetrics, candidate: BenchmarkMetrics
) -> Dict[str, float]:
    metrics = {}
    for key in asdict(baseline).keys():
        baseline_value = float(getattr(baseline, key))
        candidate_value = float(getattr(candidate, key))
        if baseline_value == 0:
            metrics[key] = 0.0 if candidate_value == 0 else 100.0
        else:
            metrics[key] = abs(candidate_value - baseline_value) / abs(baseline_value) * 100.0
    return metrics


def is_within_threshold(diff_map: Dict[str, float], threshold_pct: float = 2.0) -> Tuple[bool, Dict[str, float]]:
    failed = {name: diff for name, diff in diff_map.items() if diff > threshold_pct}
    return len(failed) == 0, failed


def render_markdown_report(
    baseline: BenchmarkMetrics,
    candidate: BenchmarkMetrics,
    diff_map: Dict[str, float],
    threshold_pct: float = 2.0,
) -> str:
    lines = []
    lines.append("| 指标 | 基线模型 | v11onnx | 差异(%) |")
    lines.append("|---|---:|---:|---:|")
    for key in asdict(baseline).keys():
        lines.append(
            f"| {key} | {getattr(baseline, key):.4f} | {getattr(candidate, key):.4f} | {diff_map[key]:.4f} |"
        )
    passed, failed = is_within_threshold(diff_map, threshold_pct=threshold_pct)
    if passed:
        lines.append("")
        lines.append(f"结论: 所有指标差异均 <= {threshold_pct:.2f}%。")
    else:
        lines.append("")
        lines.append(f"结论: 存在指标差异 > {threshold_pct:.2f}%: {', '.join(sorted(failed.keys()))}")
    return "\n".join(lines)


def _load_metrics(path: str) -> BenchmarkMetrics:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return BenchmarkMetrics(**payload)


def _save_report(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main() -> int:
    parser = argparse.ArgumentParser(description="v11onnx benchmark comparator")
    parser.add_argument("--baseline", required=True, help="baseline metrics json")
    parser.add_argument("--candidate", required=True, help="v11onnx metrics json")
    parser.add_argument("--threshold", type=float, default=2.0, help="max allowed diff pct")
    parser.add_argument("--out", default="v11onnx_benchmark_report.md", help="markdown output path")
    args = parser.parse_args()

    baseline = _load_metrics(args.baseline)
    candidate = _load_metrics(args.candidate)
    diff_map = compare_metrics(baseline, candidate)
    report = render_markdown_report(
        baseline=baseline,
        candidate=candidate,
        diff_map=diff_map,
        threshold_pct=args.threshold,
    )
    _save_report(args.out, report)
    passed, _ = is_within_threshold(diff_map, threshold_pct=args.threshold)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
