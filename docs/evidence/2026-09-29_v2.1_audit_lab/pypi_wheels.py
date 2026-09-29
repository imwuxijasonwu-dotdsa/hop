"""Which platforms have prebuilt cp312 wheels for the solver packages (PyPI metadata, latest release)."""
import json, urllib.request
for pkg in ["ecos", "clarabel", "osqp", "scs", "cvxpy"]:
    d = json.load(urllib.request.urlopen(f"https://pypi.org/pypi/{pkg}/json", timeout=30))
    files = [f["filename"] for f in d["urls"]]
    cp312 = [f for f in files if "cp312" in f or "abi3" in f or "py3-none" in f]
    mac_arm = [f for f in cp312 if "macosx" in f and ("arm64" in f or "universal2" in f)]
    mac_x86 = [f for f in cp312 if "macosx" in f and "x86_64" in f]
    lin_x86 = [f for f in cp312 if "manylinux" in f and "x86_64" in f]
    sdist = [f for f in files if f.endswith(".tar.gz")]
    print(f"{pkg} {d['info']['version']}: macOS-arm64={bool(mac_arm)} macOS-x86_64={bool(mac_x86)} "
          f"linux-x86_64={bool(lin_x86)} sdist={bool(sdist)}")
    if pkg == "ecos":
        print("  ecos macOS files:", [f for f in files if "macosx" in f])
