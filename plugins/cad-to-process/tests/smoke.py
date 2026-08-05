#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = PLUGIN_ROOT / "tests" / "fixtures"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=PLUGIN_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def main() -> int:
    run("scripts/validate_manifest.py", str(FIXTURES / "step-manifest.json"))
    run("scripts/validate_manifest.py", str(FIXTURES / "dxf-manifest.json"))
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        features = temp / "features.json"
        fused = temp / "fused.json"
        run(
            "skills/machining-feature-recognizer/scripts/recognize_features.py",
            str(FIXTURES / "step-manifest.json"),
            "-o",
            str(features),
        )
        feature_payload = json.loads(features.read_text(encoding="utf-8"))
        assert len(feature_payload["feature_candidates"]) == 1
        assert feature_payload["feature_candidates"][0]["supporting_faces"] == [
            "#o1.f1",
            "#o1.f2",
        ]
        run(
            "skills/manufacturing-intent-fusion/scripts/fuse_manifests.py",
            str(features),
            str(FIXTURES / "dxf-manifest.json"),
            "-o",
            str(fused),
        )
        fused_payload = json.loads(fused.read_text(encoding="utf-8"))
        assert fused_payload["release"]["decision"] == "needs_review"
        assert "feature_candidates_unpromoted" in fused_payload["release"]["blockers"]
        assert len(fused_payload["requirements"]) == 1
    print("smoke-ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
