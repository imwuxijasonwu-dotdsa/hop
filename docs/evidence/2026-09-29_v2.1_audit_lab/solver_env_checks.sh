#!/usr/bin/env bash
# E8: CVXPY solver discovery and solve evidence; E9: physical cost of a second same-lock runtime with a warm uv cache.
# Usage: bash solver_env_checks.sh <python-with-pyqlib-0.9.7> <constraints.txt> <scratch-dir>
set -u
PY=$1; CONS=$2; W=$3
echo "== E8 CVXPY"
"$PY" - <<'PY' 2>/dev/null
import cvxpy as cp, numpy as np
print("cvxpy", cp.__version__, "installed_solvers:", cp.installed_solvers())
x = cp.Variable(3)
p = cp.Problem(cp.Minimize(cp.sum_squares(x - np.array([0.5, 0.3, 0.2]))), [cp.sum(x) == 1, x >= 0])
p.solve()
s = p.solver_stats
print("default solve: status=%s solver=%s num_iters=%s solve_time_recorded=%s" % (p.status, s.solver_name, s.num_iters, s.solve_time is not None))
try:
    p.solve(solver=cp.ECOS)
except Exception as e:
    print("explicit ECOS:", type(e).__name__, "-", e)
PY
echo "== E9 second same-lock runtime (uv cache warm, same filesystem)"
rm -rf "$W" && mkdir -p "$W"
for n in A B; do
  s=$(date +%s.%N)
  uv venv "$W/env$n" --python 3.12 -q && uv pip install --python "$W/env$n/bin/python" -q "pyqlib==0.9.7" -c "$CONS"
  e=$(date +%s.%N); echo "env$n build seconds: $(python3 -c "print(round($e-$s,1))")"
done
echo "logical size envB alone: $(du -sh "$W/envB" | cut -f1)"
echo "physical size of envB after counting cache+envA first (du counts hardlinks once):"
du -sh "${UV_CACHE_DIR}" "$W/envA" "$W/envB" | sed 's/^/  /'
echo "numpy core .so link count in envB: $(stat -c %h "$(find "$W/envB" -name '_multiarray_umath*.so' | head -1)")"
echo "filesystem: $(df -T "$W" | tail -1 | awk '{print $2}')"
