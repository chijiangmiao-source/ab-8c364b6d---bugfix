from fractions import Fraction

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _post(payload):
    return client.post("/api/audit", json=payload)


SQUARE = [
    {"id": "A", "t0": "0", "t1": "0", "t2": "0", "cost": "1"},
    {"id": "B", "t0": "2", "t1": "2", "t2": "0", "cost": "1"},
    {"id": "C", "t0": "0", "t1": "2", "t2": "0", "cost": "1"},
    {"id": "D", "t0": "2", "t1": "0", "t2": "0", "cost": "1"},
]


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_feasible_returns_canonical_fractions():
    r = _post({"endmembers": SQUARE, "target": ["1", "1", "0"]})
    body = r.json()
    assert body["feasible"] is True
    assert body["solution"]["ids"] == ["A", "B"]
    weights = {w["id"]: w for w in body["solution"]["weights"]}
    assert weights["A"]["fraction"] == "1/2"
    assert weights["A"]["numerator"] == 1
    assert weights["A"]["denominator"] == 2
    assert body["tie_count"] == 2


def test_infeasible_outside_hull():
    r = _post({"endmembers": SQUARE, "target": ["1", "1", "9"]})
    body = r.json()
    assert body["feasible"] is False
    assert body["solution"] is None
    assert body["errors"] == []


def test_invalid_integer_is_field_localised():
    ems = [dict(e) for e in SQUARE]
    ems[1]["t1"] = "2.5"
    r = _post({"endmembers": ems, "target": ["1", "1", "0"]})
    body = r.json()
    assert body["feasible"] is False
    fields = {e["field"] for e in body["errors"]}
    assert "endmembers[1].t1" in fields


def test_tracer_boundary_and_cost_rules():
    ems = [dict(e) for e in SQUARE]
    ems[0]["t0"] = "1000001"
    ems[2]["cost"] = "0"
    r = _post({"endmembers": ems, "target": ["1", "1", "0"]})
    fields = {e["field"] for e in r.json()["errors"]}
    assert "endmembers[0].t0" in fields
    assert "endmembers[2].cost" in fields


def test_target_too_many_decimals_rejected():
    r = _post({"endmembers": SQUARE, "target": ["1.12345", "1", "0"]})
    fields = {e["field"] for e in r.json()["errors"]}
    assert "target[0]" in fields


def test_duplicate_and_non_ascii_ids_rejected():
    ems = [dict(e) for e in SQUARE]
    ems[3]["id"] = "B"
    ems[0]["id"] = "火山A"
    r = _post({"endmembers": ems, "target": ["1", "1", "0"]})
    fields = {e["field"] for e in r.json()["errors"]}
    assert "endmembers[0].id" in fields
    assert "endmembers[3].id" in fields


def test_batch_size_limits():
    r = _post({"endmembers": SQUARE[:2], "target": ["1", "1", "0"]})
    assert any(e["field"] == "endmembers" for e in r.json()["errors"])


def test_malformed_json_body_still_200_with_field_error():
    r = client.post("/api/audit", json={"endmembers": "nope"})
    assert r.status_code == 200
    body = r.json()
    assert body["feasible"] is False and body["errors"]


def test_classification_payload():
    ems = [dict(e) for e in SQUARE]
    ems.append({"id": "E", "t0": "40", "t1": "40", "t2": "40", "cost": "1"})
    r = _post({"endmembers": ems, "target": ["1", "1", "0"]})
    cls = r.json()["classification"]
    assert cls["A"] == "partial" and cls["E"] == "never"


# ------------------------------------------- collinear-ray acceptance batch
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
ASH_IDS = [e["id"] for e in ASH_BATCH]
ASH_RAY_X = {"Z1", "A1"}
ASH_RAY_Y = {"Z2", "A2", "B2"}
ASH_RAY_D = {"Z3", "A3", "B3", "C3"}
ASH_COORDS = {e["id"]: (int(e["t0"]), int(e["t1"]), int(e["t2"]))
              for e in ASH_BATCH}


def _fraction(weight):
    return Fraction(weight["numerator"], weight["denominator"])


def _check_tied_solution(sol):
    ids = sol["ids"]
    assert sorted(ids) == ids  # ids and weights are aligned in id order
    weights = {w["id"]: w for w in sol["weights"]}
    assert set(weights) == set(ids)
    fracs = {i: _fraction(weights[i]) for i in ids}
    # fraction string must match the exact numerator/denominator pair
    for i in ids:
        w = weights[i]
        assert w["fraction"] == (
            str(w["numerator"]) if w["denominator"] == 1
            else f"{w['numerator']}/{w['denominator']}"
        )
        assert Fraction(w["fraction"]) == fracs[i]
    # strictly positive and sum exactly to 1
    assert all(weights[i]["numerator"] > 0 for i in ids)
    assert sum(fracs.values()) == 1
    assert weights[ids[0]]["denominator"] > 0
    # recompute every tracer from the exact response fractions
    for r in range(3):
        tracer = sum(fracs[i] * ASH_COORDS[i][r] for i in ids)
        assert tracer == 0
    # one member from each co-directional ray
    assert sum(i in ASH_RAY_X for i in ids) == 1
    assert sum(i in ASH_RAY_Y for i in ids) == 1
    assert sum(i in ASH_RAY_D for i in ids) == 1
    assert sol["cost"] == 3


def test_ash_batch_endpoint_24_explanations():
    r = _post({"endmembers": ASH_BATCH, "target": ["0", "0", "0"]})
    assert r.status_code == 200
    body = r.json()
    assert body["feasible"] is True
    assert body["errors"] == []
    assert body["tie_count"] == 24
    tied = body["tied"]
    assert len(tied) == 24
    keys = [tuple(s["ids"]) for s in tied]
    assert len(set(keys)) == 24
    for sol in tied:
        _check_tied_solution(sol)
    # canonical solution: A1, A2, A3 with exact thirds
    canonical = body["solution"]
    assert canonical["ids"] == ["A1", "A2", "A3"]
    assert [(w["id"], w["fraction"], w["numerator"], w["denominator"])
            for w in canonical["weights"]] == [
        ("A1", "1/3", 1, 3), ("A2", "1/3", 1, 3), ("A3", "1/3", 1, 3),
    ]
    assert tied[0]["ids"] == ["A1", "A2", "A3"]


def test_ash_batch_endpoint_all_partial():
    r = _post({"endmembers": ASH_BATCH, "target": ["0", "0", "0"]})
    cls = r.json()["classification"]
    assert set(cls) == set(ASH_IDS)
    assert all(v == "partial" for v in cls.values())


def test_ash_batch_endpoint_invariant_to_order():
    shuffled = [
        next(e for e in ASH_BATCH if e["id"] == i)
        for i in ["C3", "B3", "A3", "B2", "A2", "A1", "Z3", "Z2", "Z1"]
    ]
    r = _post({"endmembers": shuffled, "target": ["0", "0", "0"]})
    body = r.json()
    assert body["tie_count"] == 24
    assert body["solution"]["ids"] == ["A1", "A2", "A3"]
    assert all(w["fraction"] == "1/3" for w in body["solution"]["weights"])
    assert all(v == "partial" for v in body["classification"].values())
