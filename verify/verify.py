#!/usr/bin/env python3
"""One-shot verification service.

Runs every required audit and exits non-zero on the first failed group:

  1. backend code tests (pytest)
  2. canonical rational weights (exact fraction strings)
  3. outside-convex-hull infeasibility
  4. tie classification (always / partial / never)
  5. collinear-ray acceptance batch (24 cartesian-product ties,
     canonical thirds, all partial, exact tracer recomputation)
  6. build artefacts (web container serves the production bundle)
  7. API smoke (direct + through the web proxy)

Usage:  verify.py [api_base] [web_base]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from fractions import Fraction

API = os.environ.get("API_BASE", "http://api:8000")
WEB = os.environ.get("WEB_BASE", "http://web:80")
API_TESTS = os.environ.get("API_TESTS_DIR", "/srv/api")

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" -- {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(name)


def get(url: str, timeout: float = 5.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read().decode()


def post(url: str, payload: dict, timeout: float = 5.0):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode())


def wait_for(url: str, label: str, attempts: int = 30) -> bool:
    for _ in range(attempts):
        try:
            status, _ = get(url)
            if status == 200:
                return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(1)
    print(f"[FAIL] {label} not reachable at {url}")
    return False


# ----------------------------------------------------------------- 1. tests
def run_pytest() -> None:
    print("[....] running backend pytest")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=API_TESTS,
        capture_output=True,
        text=True,
    )
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-1:]
    check("backend code tests (pytest)", proc.returncode == 0, " ".join(tail))


SQUARE = [
    {"id": "A", "t0": "0", "t1": "0", "t2": "0", "cost": "1"},
    {"id": "B", "t0": "2", "t1": "2", "t2": "0", "cost": "1"},
    {"id": "C", "t0": "0", "t1": "2", "t2": "0", "cost": "1"},
    {"id": "D", "t0": "2", "t1": "0", "t2": "0", "cost": "1"},
]

TETRA = [
    {"id": "A", "t0": "0", "t1": "0", "t2": "0", "cost": "1"},
    {"id": "B", "t0": "4", "t1": "0", "t2": "0", "cost": "1"},
    {"id": "C", "t0": "0", "t1": "4", "t2": "0", "cost": "1"},
    {"id": "D", "t0": "0", "t1": "0", "t2": "4", "cost": "1"},
]

# Collinear-ray acceptance batch: two +x, three +y and four (-x,-y)
# endmembers around the zero target, all with review cost 1.
ASH_BATCH = [
    {"id": "Z1", "t0": "2", "t1": "0", "t2": "0", "cost": "1"},
    {"id": "Z2", "t0": "0", "t1": "3", "t2": "0", "cost": "1"},
    {"id": "Z3", "t0": "-4", "t1": "-4", "t2": "0", "cost": "1"},
    {"id": "A1", "t0": "1", "t1": "0", "t2": "0", "cost": "1"},
    {"id": "A2", "t0": "0", "t1": "1", "t2": "0", "cost": "1"},
    {"id": "B2", "t0": "0", "t1": "2", "t2": "0", "cost": "1"},
    {"id": "A3", "t0": "-1", "t1": "-1", "t2": "0", "cost": "1"},
    {"id": "B3", "t0": "-2", "t1": "-2", "t2": "0", "cost": "1"},
    {"id": "C3", "t0": "-3", "t1": "-3", "t2": "0", "cost": "1"},
]
ASH_ORDER = ["Z1", "Z2", "Z3", "A1", "A2", "B2", "A3", "B3", "C3"]
ASH_RAYS = [
    {"Z1", "A1"}, {"Z2", "A2", "B2"}, {"Z3", "A3", "B3", "C3"},
]
ASH_COORDS = {
    e["id"]: (int(e["t0"]), int(e["t1"]), int(e["t2"])) for e in ASH_BATCH
}


# ----------------------------------------------- 2. canonical fraction weights
def check_canonical_weights() -> None:
    _, body = post(f"{API}/api/audit", {"endmembers": TETRA, "target": ["1", "1", "1"]})
    ok = True
    detail = ""
    if not body.get("feasible"):
        ok = False
        detail = "expected feasible tetrahedron interior point"
    else:
        sol = body["solution"]
        if sorted(w["id"] for w in sol["weights"]) != ["A", "B", "C", "D"]:
            ok = False
        for w in sol["weights"]:
            if w["fraction"] != "1/4" or (w["numerator"], w["denominator"]) != (1, 4):
                ok = False
                detail = f"bad fraction for {w['id']}: {w['fraction']}"
        if abs(sum(w["decimal"] for w in sol["weights"]) - 1.0) > 1e-9:
            ok = False
            detail = "weights do not sum to 1"
    check("canonical rational weights 1/4 (tetrahedron interior)", ok, detail)

    # decimal target 0.125 -> 7/8, 1/8 exactly
    ems = [
        {"id": "A", "t0": "0", "t1": "0", "t2": "0", "cost": "1"},
        {"id": "B", "t0": "1", "t1": "0", "t2": "0", "cost": "1"},
        {"id": "C", "t0": "0", "t1": "1", "t2": "0", "cost": "1"},
    ]
    _, body = post(f"{API}/api/audit", {"endmembers": ems, "target": ["0.125", "0", "0"]})
    frac = {w["id"]: w["fraction"] for w in body["solution"]["weights"]}
    check("four-decimal target yields exact 7/8 + 1/8", frac == {"A": "7/8", "B": "1/8"},
          str(frac))


# --------------------------------------------------- 3. outside hull infeasible
def check_outside_hull() -> None:
    _, body = post(f"{API}/api/audit", {"endmembers": SQUARE, "target": ["1", "1", "9"]})
    check(
        "outside convex hull -> feasible=false, no solution",
        body.get("feasible") is False and body.get("solution") is None
        and not body.get("errors"),
        json.dumps(body)[:300],
    )


# ----------------------------------------------------- 4. tie classification
def check_classification() -> None:
    # both diagonals tie -> all four partial
    _, body = post(f"{API}/api/audit", {"endmembers": SQUARE, "target": ["1", "1", "0"]})
    cls = body.get("classification", {})
    ok = (
        body.get("feasible")
        and body.get("tie_count") == 2
        and all(cls.get(i) == "partial" for i in "ABCD")
    )
    check("equal-cost ties -> all endmembers partial", ok, json.dumps(cls))

    # unique midpoint of A-B on the z axis with no competing representation
    ems = [
        {"id": "A", "t0": "0", "t1": "0", "t2": "0", "cost": "1"},
        {"id": "B", "t0": "2", "t1": "0", "t2": "0", "cost": "1"},
        {"id": "C", "t0": "0", "t1": "2", "t2": "0", "cost": "1"},
    ]
    _, body = post(f"{API}/api/audit", {"endmembers": ems, "target": ["1", "0", "0"]})
    cls = body.get("classification", {})
    check(
        "unique solution -> always/never classes",
        cls.get("A") == "always" and cls.get("B") == "always" and cls.get("C") == "never",
        json.dumps(cls),
    )


# ----------------------------- 5. collinear-ray acceptance batch
def _ash_batch_by_order(order):
    by_id = {e["id"]: e for e in ASH_BATCH}
    return [by_id[i] for i in order]


def _validate_ash_body(body: dict) -> tuple[bool, str]:
    """Validate every contract point of the collinear-ray batch."""
    if not body.get("feasible") or body.get("errors"):
        return False, f"unexpected response: {json.dumps(body)[:300]}"
    if body.get("tie_count") != 24 or len(body.get("tied", [])) != 24:
        return False, f"tie_count={body.get('tie_count')}"

    sol = body.get("solution") or {}
    canonical = [(w["id"], w["fraction"]) for w in sol.get("weights", [])]
    if sol.get("ids") != ["A1", "A2", "A3"] or canonical != [
        ("A1", "1/3"), ("A2", "1/3"), ("A3", "1/3")
    ] or sol.get("cost") != 3:
        return False, f"bad canonical solution: {json.dumps(sol)[:300]}"

    keys = set()
    for tied in body["tied"]:
        ids = tied.get("ids", [])
        key = tuple(ids)
        if key in keys:
            return False, f"duplicate explanation {key}"
        keys.add(key)
        if len(ids) != 3 or not all(len(r & set(ids)) == 1 for r in ASH_RAYS):
            return False, f"bad ray composition: {ids}"
        if tied.get("cost") != 3:
            return False, f"bad cost on {ids}"
        weights = {w["id"]: w for w in tied.get("weights", [])}
        if set(weights) != set(ids):
            return False, f"weight/id mismatch on {ids}"
        fracs = {}
        for i in ids:
            w = weights[i]
            if w["numerator"] <= 0 or w["denominator"] <= 0:
                return False, f"non-positive weight on {ids}: {w}"
            frac = Fraction(w["numerator"], w["denominator"])
            # the rendered fraction string must carry the exact same value
            if Fraction(w["fraction"]) != frac:
                return False, f"fraction string mismatch on {ids}: {w}"
            fracs[i] = frac
        if sum(fracs.values()) != 1:
            return False, f"weights do not sum to 1 on {ids}: {fracs}"
        # recompute all three tracers from the response's exact fractions
        for r in range(3):
            tracer = sum(fracs[i] * ASH_COORDS[i][r] for i in ids)
            if tracer != 0:
                return False, f"tracer {r} recomputes to {tracer} on {ids}"

    cls = body.get("classification", {})
    if set(cls) != set(ASH_ORDER) or not all(v == "partial" for v in cls.values()):
        return False, f"bad classification: {json.dumps(cls)[:300]}"
    return True, ""


def check_ash_batch() -> None:
    # entry order must not change canonical solution, tie total or classes
    orders = {
        "specified order": ASH_ORDER,
        "reversed order": list(reversed(ASH_ORDER)),
        "shuffled order": ["A1", "B2", "C3", "Z1", "A2", "B3", "Z2", "A3", "Z3"],
    }
    for label, order in orders.items():
        _, body = post(f"{API}/api/audit",
                       {"endmembers": _ash_batch_by_order(order),
                        "target": ["0", "0", "0"]})
        ok, detail = _validate_ash_body(body)
        check(f"collinear-ray batch: 24 ties / thirds / partial ({label})",
              ok, detail)

    # same batch through the web proxy proves the real HTTP path end-to-end
    try:
        status, body = post(f"{WEB}/api/audit",
                            {"endmembers": _ash_batch_by_order(ASH_ORDER),
                             "target": ["0", "0", "0"]})
        ok, detail = (status == 200, f"http {status}")
        if ok:
            ok, detail = _validate_ash_body(body)
    except Exception as exc:  # noqa: BLE001
        ok, detail = False, str(exc)
    check("collinear-ray batch through web proxy (24 exact ties)", ok, detail)


# ------------------------------------------------------ 6. build artefacts
def check_web_build() -> None:
    try:
        status, html = get(f"{WEB}/")
    except Exception as exc:  # noqa: BLE001
        check("web build served by nginx container", False, str(exc))
        return
    has_root = status == 200 and '<div id="root">' in html
    check("web container serves production index.html", has_root)
    # the bundled JS asset referenced from the built HTML must exist
    try:
        import re

        m = re.search(r'src="(/assets/[^"]+\.js)"', html)
        asset_ok = bool(m)
        if m:
            s, _ = get(f"{WEB}{m.group(1)}")
            asset_ok = s == 200
        check("built JS bundle asset reachable", asset_ok,
              "no asset reference" if not m else "")
    except Exception as exc:  # noqa: BLE001
        check("built JS bundle asset reachable", False, str(exc))


# ---------------------------------------------------------------- 7. smoke
def check_smoke() -> None:
    try:
        s, body = get(f"{API}/health")
        direct = s == 200 and json.loads(body)["status"] == "ok"
    except Exception as exc:  # noqa: BLE001
        direct = False
        print(f"       direct health error: {exc}")
    check("API smoke: GET /health direct", direct)

    try:
        s, body = get(f"{WEB}/health")
        proxied = s == 200 and json.loads(body)["status"] == "ok"
    except Exception as exc:  # noqa: BLE001
        proxied = False
        print(f"       proxied health error: {exc}")
    check("API smoke: GET /health through web proxy", proxied)

    try:
        s, body = post(f"{WEB}/api/audit",
                       {"endmembers": SQUARE, "target": ["1", "1", "0"]})
        roundtrip = s == 200 and body.get("feasible") is True
    except Exception as exc:  # noqa: BLE001
        roundtrip = False
        print(f"       proxied audit error: {exc}")
    check("API smoke: POST /api/audit through web proxy", roundtrip)


def main() -> int:
    api_ok = wait_for(f"{API}/health", "api")
    web_ok = wait_for(f"{WEB}/healthz", "web")
    if not api_ok or not web_ok:
        return 1

    run_pytest()
    check_canonical_weights()
    check_outside_hull()
    check_classification()
    check_ash_batch()
    check_web_build()
    check_smoke()

    print("-" * 60)
    if failures:
        print(f"{len(failures)} CHECK(S) FAILED: {', '.join(failures)}")
        return 1
    print("ALL VERIFICATION CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
