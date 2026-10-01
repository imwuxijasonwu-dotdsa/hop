#!/usr/bin/env bash
# S1-S3: static facts about the two candidate IBKR Python clients (downloads public artifacts; no IBKR connection).
set -u
W=${1:-/tmp/ibclient-facts}; rm -rf "$W" && mkdir -p "$W" && cd "$W"
echo "== S1 official TWS API (Mac/Unix stable zip from interactivebrokers.github.io)"
curl -sSL -o tws.zip "https://interactivebrokers.github.io/downloads/twsapi_macunix.1050.02.zip" -w "download http=%{http_code} bytes=%{size_download}\n"
unzip -q tws.zip -d tws
PC=tws/IBJts/source/pythonclient
echo "version: $(grep -o '"major": [0-9]*, "minor": [0-9]*, "micro": [0-9]*' $PC/ibapi/__init__.py)"
echo "license (setup.py): $(grep -o 'license="[^"]*"' $PC/setup.py)"
echo "LICENSE file first line: $(head -1 tws/IBJts/LICENSE | sed 's/^ *//')"
echo "install_requires: $(grep -o 'install_requires=\[[^]]*\]' $PC/setup.py)"
echo "MAX_CLIENT_VER -> $(grep -E '^MAX_CLIENT_VER' $PC/ibapi/server_versions.py) ($(grep -E '^UNIFIED_VERSION_COND_ORDER_WITH_OVERNIGHT_PARAM' $PC/ibapi/server_versions.py))"
echo "settlementMethod parsed: $(grep -c 'settlementMethod' $PC/ibapi/decoder_utils.py) occurrence(s) in decoder_utils.py"
echo "reader thread: $(grep -c 'class EReader(Thread)' $PC/ibapi/reader.py)"
echo "volumes-in-shares server version: $(grep -E '^MIN_SERVER_VER_MARKET_DATA_VOLUMES_IN_SHARES' $PC/ibapi/server_versions.py)"
echo "== S2 PyPI package named ibapi"
curl -sS https://pypi.org/pypi/ibapi/json | python3 -c "import json,sys; d=json.load(sys.stdin); print('latest', d['info']['version'], '| releases', sorted(d['releases']))"
echo "== S3 ib_async"
curl -sS https://pypi.org/pypi/ib_async/json | python3 -c "import json,sys; d=json.load(sys.stdin); i=d['info']; print('latest', i['version'], '| license', i.get('license'), '| last upload', max(f['upload_time'][:10] for f in d['urls']))"
python3 -m pip download -q --no-deps ib_async==2.1.0 -d . >/dev/null 2>&1
python3 - <<'PY'
import glob, re, zipfile
z = zipfile.ZipFile(glob.glob("ib_async-2.1.0*.whl")[0])
cl = z.read("ib_async/client.py").decode()
ct = z.read("ib_async/contract.py").decode()
print("MaxClientVersion:", re.findall(r"MaxClientVersion\s*=\s*(\d+)", cl))
print("settlementMethod in contract.py/decoder.py:", "settlementMethod" in ct, "settlementMethod" in z.read("ib_async/decoder.py").decode())
print("protobuf referenced:", any("protobuf" in z.read(n).decode(errors="ignore") for n in z.namelist() if n.endswith(".py")))
PY
curl -sS "https://api.github.com/repos/ib-api-reloaded/ib_async/commits?per_page=1" | python3 -c "import json,sys; c=json.load(sys.stdin)[0]; print('latest commit on default branch:', c['commit']['committer']['date'][:10])"
