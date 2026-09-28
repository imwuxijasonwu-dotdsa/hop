#!/usr/bin/env bash
# E1: venv relocation; E5b: EnhancedIndexingOptimizer with ECOS installed.
# Usage: bash relocate.sh <workdir>   (needs uv; downloads pyqlib 0.9.7 wheels)
set -u
W=${1:-/tmp/lab-reloc}; HERE=$(cd "$(dirname "$0")" && pwd)
rm -rf "$W" && mkdir -p "$W" && cd "$W"
echo "== E1a plain venv: build at temporary path, rename (old path removed)"
uv venv .building --python 3.12 -q && uv pip install --python .building/bin/python -q "pyqlib==0.9.7" -c "$HERE/constraints.txt"
mv .building final
echo "shebang: $(head -1 final/bin/qrun)"
final/bin/python -c "import sys, qlib; print('python -m style: ok, sys.prefix =', sys.prefix)"
final/bin/qrun --help >/dev/null 2>err.txt; echo "console script qrun: exit=$? $(head -c 100 err.txt)"
echo "== E1b uv venv --relocatable: build at temporary path, rename"
uv venv .building-rel --python 3.12 --relocatable -q && uv pip install --python .building-rel/bin/python -q "pyqlib==0.9.7" -c "$HERE/constraints.txt"
mv .building-rel final-rel
final-rel/bin/qrun --help >/dev/null 2>err2.txt; echo "console script qrun: exit=$?"
echo "== E5b EnhancedIndexingOptimizer after explicitly installing ecos"
uv pip install --python final-rel/bin/python -q ecos
final-rel/bin/python - <<'PY' 2>/dev/null
import numpy as np, importlib.metadata as md
from qlib.contrib.strategy.optimizer import EnhancedIndexingOptimizer
n = 4
w = EnhancedIndexingOptimizer(delta=0.2)(r=np.array([0.02, 0.01, 0.0, -0.01]), F=np.ones((n, 1)),
    cov_b=np.array([[0.0004]]), var_u=np.full(n, 1e-4), w0=np.zeros(n), wb=np.full(n, 0.25))
print("ecos", md.version("ecos"), "-> weights", np.round(w, 4).tolist())
PY
