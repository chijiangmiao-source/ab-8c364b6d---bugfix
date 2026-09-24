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


# --------------------------------- Cartesian ties across three same-ray lanes
THREE_RAYS = [
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
RAY_X = {"Z1", "A1"}
RAY_Y = {"Z2", "A2", "B2"}
RAY_D = {"Z3", "A3", "B3", "C3"}


def test_three_ray_batch_24_ties_canonical_and_classification():
    r = _post({"endmembers": THREE_RAYS, "target": ["0", "0", "0"]})
    body = r.json()
    assert body["feasible"] is True
    assert body["tie_count"] == 24

    sol = body["solution"]
    assert sol["ids"] == ["A1", "A2", "A3"]
    assert [w["fraction"] for w in sol["weights"]] == ["1/3"] * 3
    assert sol["cost"] == 3

    cls = body["classification"]
    assert set(cls) == {e["id"] for e in THREE_RAYS}
    assert all(v == "partial" for v in cls.values())

    # 24 pairwise distinct explanations, one member per ray each
    keyed = {tuple(s["ids"]): s for s in body["tied"]}
    assert len(keyed) == 24
    for ids in keyed:
        assert sum(i in RAY_X for i in ids) == 1
        assert sum(i in RAY_Y for i in ids) == 1
        assert sum(i in RAY_D for i in ids) == 1


def test_three_ray_batch_every_tie_recomputes_target_exactly():
    r = _post({"endmembers": THREE_RAYS, "target": ["0", "0", "0"]})
    body = r.json()
    coords = {e["id"]: (int(e["t0"]), int(e["t1"]), int(e["t2"]))
              for e in THREE_RAYS}

    for s in body["tied"]:
        fracs = [(w["id"], w["numerator"], w["denominator"])
                 for w in s["weights"]]
        # strictly positive fractions that sum to exactly 1
        assert all(n > 0 and d > 0 for _, n, d in fracs)
        assert sum(Fraction(n, d) for _, n, d in fracs) == 1
        for tr in range(3):
            tracer = sum(
                Fraction(n, d) * coords[i][tr] for i, n, d in fracs
            )
            assert tracer == 0, (s["ids"], tr, tracer)


def test_three_ray_batch_order_independent():
    payload_a = {"endmembers": THREE_RAYS, "target": ["0", "0", "0"]}
    reordered = list(reversed(THREE_RAYS))
    payload_b = {"endmembers": reordered, "target": ["0", "0", "0"]}
    a = _post(payload_a).json()
    b = _post(payload_b).json()
    assert a["tie_count"] == b["tie_count"] == 24
    assert a["solution"] == b["solution"]
    assert a["tied"] == b["tied"]
    assert a["classification"] == b["classification"]
