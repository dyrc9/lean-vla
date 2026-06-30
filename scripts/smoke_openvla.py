from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

from experiments.libero_vla_plugin import OpenVLAConfig, OpenVLAPolicy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load OpenVLA/OpenVLA-OFT and emit one action chunk.")
    parser.add_argument(
        "--observation",
        default="external/openvla-oft/experiments/robot/libero/sample_libero_spatial_observation.pkl",
    )
    parser.add_argument("--instruction", default=None)
    parser.add_argument("--backend", default="openvla_oft")
    parser.add_argument("--model-id", default="moojink/openvla-7b-oft-finetuned-libero-spatial")
    parser.add_argument("--unnorm-key", default="libero_spatial_no_noops")
    parser.add_argument("--cache-dir", default="/data0/ldx/huggingface")
    parser.add_argument("--hf-endpoint", default="https://hf-mirror.com")
    parser.add_argument("--openvla-oft-root", default="external/openvla-oft")
    parser.add_argument("--load-in-8bit", action="store_true")
    parser.add_argument("--load-in-4bit", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with Path(args.observation).open("rb") as handle:
        observation = pickle.load(handle)
    instruction = args.instruction or observation.get("task_description") or "pick up the object"
    policy = OpenVLAPolicy(
        OpenVLAConfig(
            backend=args.backend,
            model_id=args.model_id,
            unnorm_key=args.unnorm_key,
            cache_dir=args.cache_dir,
            hf_endpoint=args.hf_endpoint,
            openvla_oft_root=args.openvla_oft_root,
            load_in_8bit=args.load_in_8bit,
            load_in_4bit=args.load_in_4bit,
        )
    )
    actions = policy.predict_actions(instruction, observation)
    print(
        json.dumps(
            {
                "model_id": args.model_id,
                "unnorm_key": args.unnorm_key,
                "instruction": instruction,
                "num_actions": len(actions),
                "first_action": actions[0] if actions else None,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
