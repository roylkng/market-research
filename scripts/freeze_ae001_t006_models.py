from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_history import load_canonical_gzip_json
from marketlab.alpha_t006 import freeze_t006_models, validate_frozen_t006_models


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze AE001 T006 CORE27/FULL37 ridge models"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--feature-panel", type=Path, required=True)
    parser.add_argument("--action-ledger", type=Path, required=True)
    parser.add_argument("--trial-ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market = load_canonical_gzip_json(args.market_panel.read_bytes())
    features = load_canonical_gzip_json(args.feature_panel.read_bytes())
    actions = load_canonical_gzip_json(args.action_ledger.read_bytes())
    trials = _load_json(args.trial_ledger)

    artifact = freeze_t006_models(
        feature_panel=features,
        market_panel=market,
        action_ledger=actions,
        trial_ledger=trials,
    )
    validate_frozen_t006_models(artifact)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            artifact,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "artifact_sha256": artifact["artifact_sha256"],
                "base_model_sha256": artifact["base_model"]["model_sha256"],
                "augmented_model_sha256": artifact["augmented_model"][
                    "model_sha256"
                ],
                "training_example_count": artifact["training_example_count"],
                "training_first_feature_session": artifact[
                    "training_first_feature_session"
                ],
                "training_last_feature_session": artifact[
                    "training_last_feature_session"
                ],
                "training_last_exit_session": artifact[
                    "training_last_exit_session"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
