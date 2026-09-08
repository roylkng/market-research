from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.h003_review_batches import shard_blind_packets


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blind-packets", type=Path, required=True)
    parser.add_argument("--public-manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    manifest = shard_blind_packets(
        blind_packet_path=args.blind_packets,
        public_manifest_path=args.public_manifest,
        output_dir=args.out,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
