from fractions import Fraction

from app.solver import Endmember, audit, solve_weights


def em(id, t, cost=1):
    return Endmember(id=id, t=t, cost=cost)


# ---------------------------------------------------------------- weights
def test_single_point_match():
    res = audit([em("A", (1, 0, 0)), em("B", (0, 1, 0)), em("C", (0, 0, 1))],
                (Fraction(1), Fraction(0), Fraction(0)))
    assert res.feasible
    assert res.solution.ids == ("A",)
    assert res.solution.weights == (Fraction(1),)


def test_segment_half_exact_fraction():
    res = audit(
        [em("A", (0, 0, 0)), em("B", (2, 4, 6)), em("C", (9, 9, 9))],
        (Fraction(1), Fraction(2), Fraction(3)),
    )
    assert res.solution.ids == ("A", "B")
    assert res.solution.weights == (Fraction(1, 2), Fraction(1, 2))


def test_triangle_barycentric_thirds():
    res = audit(
        [em("A", (0, 0, 0)), em("B", (3, 0, 0)), em("C", (0, 6, 0))],
        (Fraction(1), Fraction(2), Fraction(0)),
    )
    # centroid of (0,0),(3,0),(0,6) with wB=1/3, wC=1/3, wA=1/3
    assert res.solution.ids == ("A", "B", "C")
    assert res.solution.weights == tuple([Fraction(1, 3)] * 3)


def test_tetrahedron_interior_needs_four_endmembers():
    res = audit(
        [em("A", (0, 0, 0)), em("B", (4, 0, 0)),
         em("C", (0, 4, 0)), em("D", (0, 0, 4))],
        (Fraction(1), Fraction(1), Fraction(1)),
    )
    assert res.solution.ids == ("A", "B", "C", "D")
    assert res.solution.weights == tuple([Fraction(1, 4)] * 4)


def test_target_on_face_uses_three_not_four():
    res = audit(
        [em("A", (0, 0, 0)), em("B", (4, 0, 0)),
         em("C", (0, 4, 0)), em("D", (0, 0, 4))],
        (Fraction(1), Fraction(1), Fraction(0)),
    )
    assert res.solution.ids == ("A", "B", "C")


def test_collinear_duplicate_column_rejected_but_smaller_subset_found():
    # B and C identical; midpoint is expressible with A,B and A,C.
    res = audit(
        [em("A", (0, 0, 0), 1), em("B", (2, 0, 0), 5), em("C", (2, 0, 0), 1)],
        (Fraction(1), Fraction(0), Fraction(0)),
    )
    assert res.feasible
    assert set(res.solution.ids) == {"A", "C"}  # cheaper duplicate chosen


# ---------------------------------------------------------- infeasibility
def test_outside_convex_hull_is_infeasible():
    res = audit(
        [em("A", (0, 0, 0)), em("B", (1, 0, 0)), em("C", (0, 1, 0))],
        (Fraction(0), Fraction(0), Fraction(1)),  # off the z=0 plane
    )
    assert not res.feasible
    assert res.solution is None


def test_between_points_but_extrapolated_infeasible():
    res = audit(
        [em("A", (0, 0, 0)), em("B", (2, 0, 0)), em("C", (0, 2, 0))],
        (Fraction(5), Fraction(5), Fraction(0)),
    )
    assert not res.feasible


# ------------------------------------------------------- ties & ordering
def test_cost_tie_break_picks_cheapest_subset():
    # target (1,1) lies on both diagonals A-B and C-D of the unit square.
    res = audit(
        [em("A", (0, 0, 0), 100), em("B", (2, 2, 0), 100),
         em("C", (0, 2, 0), 1), em("D", (2, 0, 0), 1)],
        (Fraction(1), Fraction(1), Fraction(0)),
    )
    assert res.solution.ids == ("C", "D")
    assert res.solution.cost == 2


def test_equal_cost_picks_lexicographically_smallest_ids():
    res = audit(
        [em("A", (0, 0, 0), 1), em("B", (2, 2, 0), 1),
         em("C", (0, 2, 0), 1), em("D", (2, 0, 0), 1)],
        (Fraction(1), Fraction(1), Fraction(0)),
    )
    assert res.solution.ids == ("A", "B")  # ("A","B") < ("C","D")
    tied_ids = [s.ids for s in res.tied]
    assert tied_ids == [("A", "B"), ("C", "D")]
    assert all(s.weights == (Fraction(1, 2), Fraction(1, 2)) for s in res.tied)


def test_classification_always_partial_never():
    # diagonals A-B and C-D both explain the centre; E is irrelevant.
    res = audit(
        [em("A", (0, 0, 0), 1), em("B", (2, 2, 0), 1),
         em("C", (0, 2, 0), 1), em("D", (2, 0, 0), 1),
         em("E", (40, 40, 40), 1)],
        (Fraction(1), Fraction(1), Fraction(0)),
    )
    cls = res.classification
    assert cls["A"] == "partial" and cls["B"] == "partial"
    assert cls["C"] == "partial" and cls["D"] == "partial"
    assert cls["E"] == "never"


def test_classification_always_when_unique_solution():
    res = audit(
        [em("A", (0, 0, 0)), em("B", (2, 0, 0)),
         em("C", (0, 2, 0)), em("D", (9, 9, 9))],
        (Fraction(1), Fraction(0), Fraction(0)),
    )
    assert res.classification["A"] == "always"
    assert res.classification["B"] == "always"
    assert res.classification["C"] == "never"
    assert res.classification["D"] == "never"


def test_cost_higher_tie_excluded_from_classification_scope():
    # A-B cheap diagonal vs C-D expensive diagonal: only A,B counted;
    # C,D must be "never" because ties are within min-support AND min-cost.
    res = audit(
        [em("A", (0, 0, 0), 1), em("B", (2, 2, 0), 1),
         em("C", (0, 2, 0), 100), em("D", (2, 0, 0), 100)],
        (Fraction(1), Fraction(1), Fraction(0)),
    )
    assert res.solution.ids == ("A", "B")
    assert res.classification["A"] == "always"
    assert res.classification["B"] == "always"
    assert res.classification["C"] == "never"
    assert res.classification["D"] == "never"


def test_four_decimal_target_exact():
    # 0.125 along A->B where B=1 -> wA=7/8, wB=1/8, no float drift
    res = audit(
        [em("A", (0, 0, 0)), em("B", (1, 0, 0)), em("C", (0, 1, 0))],
        (Fraction("0.125"), Fraction(0), Fraction(0)),
    )
    assert res.solution.ids == ("A", "B")
    assert dict(zip(res.solution.ids, res.solution.weights)) == {
        "A": Fraction(7, 8), "B": Fraction(1, 8)
    }


def test_negative_tracers_supported():
    res = audit(
        [em("A", (-2, -2, -2)), em("B", (2, 2, 2)), em("C", (5, -5, 0))],
        (Fraction(0), Fraction(0), Fraction(0)),
    )
    assert res.solution.ids == ("A", "B")
    assert res.solution.weights == (Fraction(1, 2), Fraction(1, 2))


def test_weights_sum_to_one_and_reproduce_target():
    pts = [em("A", (1, -3, 7)), em("B", (-4, 2, 9)),
           em("C", (8, 0, -1)), em("E", (0, 5, 3))]
    tgt = (Fraction(1, 2), Fraction(1, 4), Fraction(-2))
    w = solve_weights([p.t for p in pts], tgt)
    if w is not None:
        assert sum(w) == 1
        for r in range(3):
            assert sum(w[i] * pts[i].t[r] for i in range(4)) == tgt[r]


# ------------------------------------- Cartesian ties across same-ray lanes
# Three rays out of the origin with 2 / 3 / 4 co-linear members: the target
# is the origin, so every optimum picks one member per ray (2*3*4 = 24).
RAY_X = {"Z1": (2, 0, 0), "A1": (1, 0, 0)}
RAY_Y = {"Z2": (0, 3, 0), "A2": (0, 1, 0), "B2": (0, 2, 0)}
RAY_D = {"Z3": (-4, -4, 0), "A3": (-1, -1, 0),
         "B3": (-2, -2, 0), "C3": (-3, -3, 0)}
ORIGIN = (Fraction(0), Fraction(0), Fraction(0))


def _three_ray_batch():
    coords = {**RAY_X, **RAY_Y, **RAY_D}
    return [em(k, v) for k, v in coords.items()]


def _assert_recomputes(ems, res):
    by_id = {e.id: e for e in ems}
    for sol in res.tied:
        assert len(sol.ids) == len(set(sol.ids))
        assert all(w > 0 for w in sol.weights)
        assert sum(sol.weights) == 1
        for r in range(3):
            got = sum(w * by_id[i].t[r] for i, w in zip(sol.ids, sol.weights))
            assert got == ORIGIN[r], (sol.ids, r, got)


def test_three_rays_produce_full_cartesian_24_ties():
    ems = _three_ray_batch()
    res = audit(ems, ORIGIN)
    assert res.feasible
    assert res.solution.cost == 3
    assert len(res.tied) == 24

    id_sets = {s.ids for s in res.tied}
    assert len(id_sets) == 24  # 24 distinct explanations
    for ids in id_sets:
        assert sum(i in RAY_X for i in ids) == 1
        assert sum(i in RAY_Y for i in ids) == 1
        assert sum(i in RAY_D for i in ids) == 1

    # canonical explanation: lexicographically smallest, equal thirds
    assert res.solution.ids == ("A1", "A2", "A3")
    assert res.solution.weights == (Fraction(1, 3),) * 3

    # every member of every lane participates in some, never in all ties
    assert set(res.classification) == {e.id for e in ems}
    assert all(v == "partial" for v in res.classification.values())

    _assert_recomputes(ems, res)


def test_cartesian_ties_independent_of_entry_order():
    ems = _three_ray_batch()
    baseline = audit(ems, ORIGIN)
    expected = (
        baseline.solution.ids,
        baseline.solution.weights,
        [(s.ids, s.weights) for s in baseline.tied],
        tuple(sorted(baseline.classification.items())),
    )
    for perm in (
        list(reversed(ems)),
        [ems[i] for i in (0, 3, 6, 1, 4, 7, 2, 5, 8)],
        [ems[i] for i in (8, 0, 7, 1, 6, 2, 5, 3, 4)],
    ):
        res = audit(perm, ORIGIN)
        assert len(res.tied) == 24
        assert (res.solution.ids, res.solution.weights) == expected[:2]
        assert [(s.ids, s.weights) for s in res.tied] == expected[2]
        assert tuple(sorted(res.classification.items())) == expected[3]


def test_same_ray_members_get_their_own_exact_weights():
    # Distances differ per lane member, so weights must be re-solved for
    # every combination rather than copied from a representative.
    ems = [
        em("Z1", (2, 0, 0)), em("A1", (1, 0, 0)),
        em("A2", (0, 1, 0)), em("B2", (0, 2, 0)),
        em("A3", (-1, -1, 0)),
    ]
    res = audit(ems, ORIGIN)
    weights_by_ids = {s.ids: s.weights for s in res.tied}
    assert weights_by_ids[("A1", "A2", "A3")] == (
        Fraction(1, 3), Fraction(1, 3), Fraction(1, 3))
    assert weights_by_ids[("A1", "A3", "B2")] == (
        Fraction(2, 5), Fraction(2, 5), Fraction(1, 5))
    assert weights_by_ids[("A2", "A3", "Z1")] == (
        Fraction(2, 5), Fraction(2, 5), Fraction(1, 5))
    assert weights_by_ids[("A3", "B2", "Z1")] == (
        Fraction(1, 2), Fraction(1, 4), Fraction(1, 4))
    _assert_recomputes(ems, res)


def test_singleton_lane_member_is_always_rest_partial():
    # X and diagonal lanes have one member each; the Y lane has two.
    ems = [
        em("A1", (1, 0, 0)),
        em("A2", (0, 1, 0)), em("B2", (0, 2, 0)),
        em("A3", (-1, -1, 0)),
    ]
    res = audit(ems, ORIGIN)
    assert len(res.tied) == 2
    assert res.classification["A1"] == "always"
    assert res.classification["A3"] == "always"
    assert res.classification["A2"] == "partial"
    assert res.classification["B2"] == "partial"


def test_pricier_same_ray_member_never_appears():
    # Making B2 pricier removes it from the optimum even though the lane
    # still offers Z2/A2 at cost 1: 2*2*4 = 16 cost-3 ties.
    ems = _three_ray_batch()
    ems = [e if e.id != "B2" else em("B2", (0, 2, 0), 2) for e in ems]
    res = audit(ems, ORIGIN)
    assert len(res.tied) == 16
    assert all("B2" not in s.ids for s in res.tied)
    assert all(s.cost == 3 for s in res.tied)
    assert res.classification["B2"] == "never"
    assert res.classification["A2"] == "partial"
    _assert_recomputes(ems, res)
