#!/usr/bin/env python3
"""Exercise the actual action block with public, non-production trust fixtures."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, required=True)
    args = parser.parse_args()
    fixtures = args.fixtures.resolve()
    action = (Path(__file__).resolve().parents[1] / "action.yml").read_text()
    marker = "      run: |\n"
    assert action.count(marker) == 1, "Review test extraction if the action structure changes"
    script = "\n".join(line[8:] for line in action.split(marker, 1)[1].splitlines())
    receipt = json.loads((fixtures / "release-receipt.json").read_text())
    approved = receipt["statement"]["contract_sha256"]
    env = {**os.environ,
           "MFENX_RECEIPT": str(fixtures / "release-receipt.json"),
           "MFENX_MODEL": str(fixtures / "model.onnx"),
           "MFENX_TRUST_KEY": str(fixtures / "issuer-public.der"),
           "MFENX_APPROVED_CONTRACT": approved}
    with tempfile.TemporaryDirectory(prefix="mfenx-action-test-") as temporary:
        def run(overrides=None):
            return subprocess.run(["bash", "-c", script], env={**env, **(overrides or {})},
                                  cwd=temporary, capture_output=True, text=True, timeout=30)

        def accepted(result):
            assert result.returncode == 0, result.stderr
            verified = json.loads(result.stdout)
            assert verified["status"] == "ATTESTATION_VERIFIED"
            assert verified["artifactStatus"] == "MATCH"
            assert verified["contractStatus"] == "MATCH"
            assert verified["replayStatus"] == "NOT_PERFORMED"

        accepted(run())
        wrong_policy = "sha256:" + ("1" if approved.endswith("0" * 64) else "0") * 64
        rejected = run({"MFENX_APPROVED_CONTRACT": wrong_policy})
        assert rejected.returncode != 0, "Wrong policy was accepted"
        assert "expected policy" in rejected.stderr, rejected.stderr
        for name in ("MFENX_RECEIPT", "MFENX_MODEL", "MFENX_TRUST_KEY", "MFENX_APPROVED_CONTRACT"):
            rejected = run({name: "--help"})
            assert rejected.returncode != 0, f"Option-like {name} bypassed verification"

        # A real leading-dash filename is a path, not a CLI option.
        dash_receipt = Path(temporary) / "--help"
        dash_receipt.write_bytes((fixtures / "release-receipt.json").read_bytes())
        accepted(run({"MFENX_RECEIPT": "--help"}))
        changed = Path(temporary) / "changed.onnx"
        changed.write_bytes(b"changed artifact")
        assert run({"MFENX_MODEL": str(changed)}).returncode != 0
    print("PASS: valid receipt/artifact/policy; wrong policy; four option-like inputs; real leading-dash filename; changed model")


if __name__ == "__main__":
    main()
