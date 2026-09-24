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


# --------------------------------------------- collinear-ray audit batch
ASH_BATCH_COORDS = {
    "Z1": (2, 0, 0), "Z2": (0, 3, 0), "Z3": (-4, -4, 0),
    "A1": (1, 0, 0), "A2": (0, 1, 0), "B2": (0, 2, 0),
    "A3": (-1, -1, 0), "B3": (-2, -2, 0), "C3": (-3, -3, 0),
}
ASH_ORDER = ["Z1", "Z2", "Z3", "A1", "A2", "B2", "A3", "B3", "C3"]
ASH_RAY_X = {"Z1", "A1"}
ASH_RAY_Y = {"Z2", "A2", "B2"}
ASH_RAY_D = {"Z3", "A3", "B3", "C3"}


def _ash_audit(order=ASH_ORDER):
    return audit(
        [em(i, ASH_BATCH_COORDS[i]) for i in order],
        (Fraction(0), Fraction(0), Fraction(0)),
    )


def test_ash_batch_canonical_solution():
    res = _ash_audit()
    assert res.feasible
    assert res.solution.ids == ("A1", "A2", "A3")
    assert res.solution.weights == (Fraction(1, 3), Fraction(1, 3), Fraction(1, 3))
    assert res.solution.cost == 3


def test_ash_batch_has_24_distinct_tied_explanations():
    res = _ash_audit()
    assert len(res.tied) == 24
    assert len({s.ids for s in res.tied}) == 24
    # one endmember per co-directional ray in every explanation
    for sol in res.tied:
        assert len(sol.ids) == 3
        assert sum(i in ASH_RAY_X for i in sol.ids) == 1
        assert sum(i in ASH_RAY_Y for i in sol.ids) == 1
        assert sum(i in ASH_RAY_D for i in sol.ids) == 1
        assert sol.cost == 3


def test_ash_batch_every_tied_solution_is_exact_and_positive():
    res = _ash_audit()
    for sol in res.tied:
        assert len(sol.weights) == 3
        assert all(w > 0 for w in sol.weights)
        assert sum(sol.weights) == 1
        for r in range(3):
            assert sum(w * ASH_BATCH_COORDS[i][r]
                       for i, w in zip(sol.ids, sol.weights)) == 0


def test_ash_batch_all_endmembers_partial():
    res = _ash_audit()
    assert res.classification == {i: "partial" for i in ASH_BATCH_COORDS}


def test_ash_batch_invariant_to_entry_order():
    shuffled = ["C3", "B3", "A3", "B2", "A2", "A1", "Z3", "Z2", "Z1"]
    res = _ash_audit(shuffled)
    assert res.solution.ids == ("A1", "A2", "A3")
    assert res.solution.weights == (Fraction(1, 3),) * 3
    assert len(res.tied) == 24
    assert len({s.ids for s in res.tied}) == 24
    assert res.classification == {i: "partial" for i in ASH_BATCH_COORDS}


def test_ash_batch_distances_give_expected_weights():
    # the farthest members Z1/Z2/Z3 reproduce the 6/13, 4/13, 3/13 balance
    res = _ash_audit()
    z = next(s for s in res.tied if set(s.ids) == {"Z1", "Z2", "Z3"})
    by_id = dict(zip(z.ids, z.weights))
    assert by_id == {"Z1": Fraction(6, 13), "Z2": Fraction(4, 13),
                     "Z3": Fraction(3, 13)}


def test_collinear_ray_alternatives_combine_as_cartesian_product():
    # two members on +x, two on -x around the origin: 2 x 2 = 4 ties
    res = audit(
        [em("A1", (1, 0, 0)), em("Z1", (2, 0, 0)),
         em("A2", (-1, 0, 0)), em("Z2", (-2, 0, 0)),
         em("E", (9, 9, 9))],
        (Fraction(0), Fraction(0), Fraction(0)),
    )
    assert [s.ids for s in res.tied] == [
        ("A1", "A2"), ("A1", "Z2"), ("A2", "Z1"), ("Z1", "Z2"),
    ]
    assert res.classification["E"] == "never"
    coords = {"A1": (1, 0, 0), "Z1": (2, 0, 0),
              "A2": (-1, 0, 0), "Z2": (-2, 0, 0)}
    expected_weights = {
        ("A1", "A2"): (Fraction(1, 2), Fraction(1, 2)),
        ("A1", "Z2"): (Fraction(2, 3), Fraction(1, 3)),
        ("A2", "Z1"): (Fraction(2, 3), Fraction(1, 3)),
        ("Z1", "Z2"): (Fraction(1, 2), Fraction(1, 2)),
    }
    for sol in res.tied:
        assert sol.weights == expected_weights[sol.ids]
        assert all(w > 0 for w in sol.weights)
        assert sum(sol.weights) == 1
        for r in range(3):
            assert sum(w * coords[i][r]
                       for i, w in zip(sol.ids, sol.weights)) == 0
