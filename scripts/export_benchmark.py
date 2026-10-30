"""Run the *deterministic* synthetic benchmark and export reproducible artifacts."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import evaluate

out = ROOT / 'docs' / 'evaluation'
out.mkdir(parents=True, exist_ok=True)
result = evaluate()
metrics = {
    'benchmark_type': 'synthetic_detection_rules',
    'injected_corruptions': result['corruptions_total'],
    'detected_corruptions': result['corruptions_detected'],
    'injected_case_recall': result['recall'],
    'clean_control_snapshots': len(result['clean_cases']),
    'clean_snapshot_flag_rate': result['clean_snapshot_false_positive_rate'],
    'warning': 'Not real-world accuracy and not live LLM evaluation',
}
(out / 'metrics.json').write_text(json.dumps(metrics, indent=2))
result['cases'].to_csv(out / 'injected_cases.csv', index=False)
result['clean_cases'].to_csv(out / 'clean_controls.csv', index=False)
print('Saved benchmark files to', out)
print(json.dumps(metrics, indent=2))
