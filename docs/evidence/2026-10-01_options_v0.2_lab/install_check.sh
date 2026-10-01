#!/usr/bin/env bash
# S4: can the proposed v1 dependency set be locked and installed reproducibly?
# Official ibapi comes from IBKR's download URL (not PyPI). Step A tries a direct URL dependency;
# step B is the fallback recipe: download -> verify sha256 -> extract -> build local wheel -> lock by hash.
# Usage: bash install_check.sh <scratch-dir>
set -u
W=${1:-/tmp/opt-install-check}; rm -rf "$W" && mkdir -p "$W" && cd "$W"
ZIP_URL="https://interactivebrokers.github.io/downloads/twsapi_macunix.1050.02.zip"
echo "== A direct URL dependency"
printf 'ibapi @ %s#subdirectory=IBJts/source/pythonclient\n' "$ZIP_URL" > direct.in
uv pip compile direct.in --python-version 3.12 -q -o direct.txt 2>direct.err && echo "A: ok" || { echo "A: FAILED"; grep -E 'Bad compressed size|Failed to extract' direct.err | head -2 | sed 's/^[ │╰─▶├]*/  /'; }
echo "== B download, verify, extract, build wheel, lock by hash"
curl -sSL -o tws.zip "$ZIP_URL"
echo "archive sha256: $(sha256sum tws.zip | cut -d' ' -f1)"
python3 - <<'PY'
import zipfile
z = zipfile.ZipFile("tws.zip")
bad = z.testzip()
members = [m for m in z.namelist() if m.startswith("IBJts/source/pythonclient/")]
z.extractall("src", members=members)
print("python zipfile: extracted", len(members), "members; testzip first bad member:", bad)
PY
uv build --wheel src/IBJts/source/pythonclient -o wheels -q 2>build.err && ls wheels | sed 's/^/built: /' || { echo "build FAILED"; tail -3 build.err; }
printf 'ibapi==10.50.2\nQuantLib==1.43\nnumpy\nscipy\n' > requirements.in
uv pip compile requirements.in --python-version 3.12 --find-links wheels --generate-hashes -q -o requirements.txt && echo "compile: ok"
echo "locked packages: $(grep -cE '^[a-zA-Z]' requirements.txt)"
grep -iE '^(ibapi|protobuf|quantlib|numpy|scipy)==' requirements.txt | sed 's/ \\$//'
uv venv .venv --python 3.12 -q
uv pip sync --python .venv/bin/python --find-links wheels --require-hashes -q requirements.txt && echo "sync --require-hashes: ok"
uv pip check --python .venv/bin/python
.venv/bin/python - <<'PY'
import importlib.metadata as md
import ibapi, QuantLib as ql, numpy, scipy
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.sync_wrapper import TWSSyncWrapper
print("ibapi", ibapi.__version__, "| protobuf", md.version("protobuf"), "| QuantLib", ql.__version__,
      "| numpy", numpy.__version__, "| scipy", scipy.__version__)
print("ibapi license metadata:", md.metadata("ibapi").get("License"))
print("TWSSyncWrapper has order methods:", hasattr(TWSSyncWrapper, "place_order_sync"), hasattr(TWSSyncWrapper, "cancel_order_sync"))
PY
