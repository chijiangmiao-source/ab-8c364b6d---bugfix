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
