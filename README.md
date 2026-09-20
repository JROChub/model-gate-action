# MFENX model-gate action

Verify a signed release receipt, its exact model artifact and an independently
approved evaluation-contract digest. All checks run on your runner. The action
does not upload model files, create an account, issue receipts or replay inference.

Verification is free, including commercial use. The action requires the
separately installed **MFENX Gate 1.0.0** CLI and Bash.

## Release verification

The example below runs from a protected release workflow. Put the candidate
model and signed receipt at `release/model.onnx` and
`release/release-receipt.json`, or change those two paths.

Configure a protected `model-release` environment that permits only your trusted
release branch. Store these environment variables through your release authority:

| Variable | Value |
| --- | --- |
| `MODEL_RELEASE_TRUST_SPKI_BASE64` | Base64-encoded P-256 SPKI DER public key |
| `MODEL_RELEASE_CONTRACT_SHA256` | Approved digest, in `sha256:` plus 64 lowercase hexadecimal characters |

Neither value may be supplied by the candidate change or copied from its receipt.
Restrict who can change the workflow, environment and approval configuration.
Use the action's reviewed full commit SHA in production; the version tag below
identifies the release family.

```yaml
name: Verify model release
on:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  verify:
    runs-on: ubuntu-24.04
    environment: model-release
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          ref: ${{ github.event.repository.default_branch }}
          persist-credentials: false

      - name: Install the checksum-pinned verifier
        shell: bash
        run: |
          set -euo pipefail
          python3 -c 'import sys; assert sys.version_info >= (3, 11)'
          wheel="$RUNNER_TEMP/mfenx_gate-1.0.0-py3-none-any.whl"
          curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
            https://mfenx.com/gate/downloads/mfenx_gate-1.0.0-py3-none-any.whl \
            --output "$wheel"
          printf '%s  %s\n' 'aac76f6f516f93d5aeb58f373ec747b34acc790fafabcbb3643f26b1f9365b4d' "$wheel" | sha256sum --check --strict
          python3 -m venv "$RUNNER_TEMP/mfenx-gate"
          "$RUNNER_TEMP/mfenx-gate/bin/python" -m pip install --disable-pip-version-check "$wheel"
          printf '%s\n' "$RUNNER_TEMP/mfenx-gate/bin" >> "$GITHUB_PATH"

      - name: Materialize the independently trusted public key
        shell: bash
        env:
          MFENX_TRUST_SPKI: ${{ vars.MODEL_RELEASE_TRUST_SPKI_BASE64 }}
        run: |
          set -euo pipefail
          test -n "$MFENX_TRUST_SPKI"
          printf '%s' "$MFENX_TRUST_SPKI" | base64 --decode > "$RUNNER_TEMP/mfenx-issuer.der"

      - uses: JROChub/model-gate-action@v1
        with:
          receipt: release/release-receipt.json
          model: release/model.onnx
          trusted-public-key: ${{ runner.temp }}/mfenx-issuer.der
          approved-contract-sha256: ${{ vars.MODEL_RELEASE_CONTRACT_SHA256 }}
```

The pinned wheel is checked before installation. Its dependencies follow the
versions declared in that release. Preinstall the same verified package in your
runner image when network access is unavailable.

## Acceptance

The job succeeds only when the receipt's structure, trusted-key signature,
validity, artifact binding and expected contract digest verify. The CLI reports
`ATTESTATION_VERIFIED`, `artifactStatus: MATCH` and `contractStatus: MATCH`.

`replayStatus` remains `NOT_PERFORMED`. A signature authenticates an issuer's
finite-evaluation statement; this action does not independently establish that
the evaluation ran or that a model is safe. Use the local CKODMK workflow when
your release policy requires behavioral replay.

Keep the verified artifact immutable between this check and deployment. This
action validates the supplied file; it does not supervise later model loading.
An invalid receipt, wrong key, changed model, expired statement or policy mismatch
fails the job. Input values are passed through environment variables and a
positional-argument delimiter, not interpolated into shell commands.

## Local tests

With Gate 1.0.0 on `PATH`, supply the public demonstration fixture directory:

```sh
python3 tests/test_action.py --fixtures /path/to/verify/example
```

The fixture must contain `release-receipt.json`, `issuer-public.der` and
`model.onnx`. The test fixture's key and contract are test data, not production
trust configuration. Tests exercise the actual composite-action shell block,
including wrong-policy and leading-option rejection.

[Local verifier](https://mfenx.com/verify/) · [Documentation](https://mfenx.com/docs/)

## Rights

The [wrapper permission](LICENSE) covers this repository only. The Gate SDK and
other dependencies retain their own terms and notices; no broader MFENX product
rights are granted by this wrapper.
