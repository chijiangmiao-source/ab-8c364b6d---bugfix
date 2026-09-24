"""Endmember audit solver.

Finds a minimum-support non-negative exact rational convex combination of
endmembers that reproduces a target tracer vector, breaking ties by total
review cost and then by the lexicographically smallest id sequence.  Each
endmember is also classified by how often it participates in the
cost-tied optimal solutions (always / partial / never).

All arithmetic is exact: tracers are integers, targets are rationals with
up to four decimal places, and weights are :class:`fractions.Fraction`.

Geometry fact: with three tracers the points live in R^3, so by
Caratheodory a convex combination, when one exists, uses at most four
endmembers.  Every minimum-support combination uses affinely independent
points (dependent positive weights could be perturbed until one weight
vanishes), hence each endmember subset determines at most one weight
vector and the set of minimum-support solutions is finite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from itertools import combinations, product

# Three tracers -> ambient space R^3; at most 4 endmembers are ever needed.
MAX_SUPPORT = 4


@dataclass(frozen=True)
class Endmember:
    id: str
    t: tuple[int, int, int]
    cost: int


@dataclass(frozen=True)
class Solution:
    """One minimum-support, cost-minimal feasible convex combination."""

    ids: tuple[str, ...]
    weights: tuple[Fraction, ...]
    cost: int


@dataclass(frozen=True)
class DirectionClass:
    """Endmembers lying on one ray from the target.

    ``cheapest`` holds the members attaining the class minimum ``cost``
    (sorted by id); only they can participate in a cost-tied optimum: a
    solution using a pricier member of the same ray could swap in a
    cheaper one (rescaling its weight) and keep support size while
    lowering cost.
    """

    direction: tuple[Fraction, Fraction, Fraction]
    cost: int
    cheapest: tuple[Endmember, ...]


@dataclass
class AuditResult:
    feasible: bool
    # lexicographically first among the cost-tied minimum-support solutions
    solution: Solution | None = None
    # every minimum-support, cost-minimal solution, in canonical order
    tied: list[Solution] = field(default_factory=list)
    classification: dict[str, str] = field(default_factory=dict)


def solve_weights(
    points: list[tuple[int, int, int]],
    target: tuple[Fraction, Fraction, Fraction],
) -> tuple[Fraction, ...] | None:
    """Exact strictly-positive barycentric weights for one endmember subset.

    Solves the 4 x k homogeneous system

        x_i columns tracer rows, last row all ones; rhs = target + [1]

    requiring full column rank (affinely independent points), exact
    consistency and strictly positive weights.  Returns ``None`` otherwise,
    including subsets whose target representation has a zero weight -- such
    targets belong to a smaller subset, enumerated elsewhere.
    """
    k = len(points)
    # Augmented matrix rows: tracer 0..2, then the sum-to-one row.
    mat: list[list[Fraction]] = [
        [Fraction(points[c][r]) for c in range(k)] for r in range(3)
    ]
    mat.append([Fraction(1) for _ in range(k)])
    rhs = [Fraction(target[0]), Fraction(target[1]), Fraction(target[2]), Fraction(1)]

    return _solve_full_column_rank(mat, rhs)


def _solve_full_column_rank(
    mat: list[list[Fraction]], rhs: list[Fraction]
) -> tuple[Fraction, ...] | None:
    """Exact solve via reduced row echelon form.

    Returns the unique solution when ``mat`` has full column rank, all rows
    are consistent with ``rhs`` and every component is strictly positive.
    """
    m = len(mat)
    k = len(mat[0])
    a = [mat[r][:] + [rhs[r]] for r in range(m)]

    pivot_row = 0
    for col in range(k):
        p = next((r for r in range(pivot_row, m) if a[r][col] != 0), None)
        if p is None:
            return None  # rank deficient -> affinely dependent subset
        a[pivot_row], a[p] = a[p], a[pivot_row]
        piv = a[pivot_row][col]
        a[pivot_row] = [v / piv for v in a[pivot_row]]
        for r in range(m):
            if r != pivot_row and a[r][col] != 0:
                factor = a[r][col]
                a[r] = [a[r][j] - factor * a[pivot_row][j] for j in range(k + 1)]
        pivot_row += 1

    # Remaining (non-pivot) rows must be 0 = rhs, i.e. exactly consistent.
    for r in range(pivot_row, m):
        if a[r][k] != 0 or any(a[r][c] != 0 for c in range(k)):
            return None

    # With k pivots found in column order, pivot row `col` is 1 at `col` and
    # zero at every other variable column.
    w = tuple(a[col][k] for col in range(k))
    if any(x <= 0 for x in w):
        return None
    return w


def _direction_key(
    point: tuple[int, int, int],
    target: tuple[Fraction, Fraction, Fraction],
) -> tuple[Fraction, Fraction, Fraction]:
    delta = tuple(Fraction(point[i]) - target[i] for i in range(3))
    pivot = next((value for value in delta if value != 0), None)
    if pivot is None:
        return (Fraction(0), Fraction(0), Fraction(0))
    scale = abs(pivot)
    return tuple(value / scale for value in delta)


def _direction_classes(
    endmembers: list[Endmember],
    target: tuple[Fraction, Fraction, Fraction],
) -> list[DirectionClass]:
    grouped: dict[
        tuple[Fraction, Fraction, Fraction], list[Endmember]
    ] = {}
    for endmember in endmembers:
        key = _direction_key(endmember.t, target)
        grouped.setdefault(key, []).append(endmember)

    classes: list[DirectionClass] = []
    for direction, members in grouped.items():
        ordered = tuple(sorted(members, key=lambda member: member.id))
        min_cost = min(member.cost for member in ordered)
        cheapest = tuple(m for m in ordered if m.cost == min_cost)
        classes.append(
            DirectionClass(
                direction=direction,
                cost=min_cost,
                cheapest=cheapest,
            )
        )
    # Stable, input-independent order; candidates are deduped and sorted
    # lexicographically by id before they leave the solver.
    classes.sort(key=lambda c: c.direction)
    return classes


def _enumerate_support_solutions(
    groups: tuple[DirectionClass, ...],
    target: tuple[Fraction, Fraction, Fraction],
) -> list[Solution]:
    """Every strictly-positive combination over distinct target-rays.

    For each selection of distinct direction classes, each class may
    contribute any of its cheapest members (members at different
    distances along the same ray carry *different* weights, so weights
    are re-solved exactly for every choice).  Duplicate affine
    representations (e.g. collinear members making two selections
    coincide) are collapsed by their id tuple.
    """
    found: dict[tuple[str, ...], Solution] = {}
    member_lanes = [group.cheapest for group in groups]
    for chosen in product(*member_lanes):
        w = solve_weights([member.t for member in chosen], target)
        if w is None:
            continue
        ordered = sorted(zip(chosen, w), key=lambda item: item[0].id)
        ids = tuple(member.id for member, _ in ordered)
        cost = sum(member.cost for member in chosen)
        found[ids] = Solution(
            ids=ids,
            weights=tuple(weight for _, weight in ordered),
            cost=cost,
        )
    return list(found.values())


def _classify(
    endmembers: list[Endmember], solutions: list[Solution]
) -> dict[str, str]:
    """always / partial / never across all (min-support, min-cost) ties."""
    counts: dict[str, int] = {}
    for solution in solutions:
        for endmember_id in solution.ids:
            counts[endmember_id] = counts.get(endmember_id, 0) + 1

    solution_count = len(solutions)
    return {
        endmember.id: (
            "always"
            if counts.get(endmember.id, 0) == solution_count
            else "partial"
            if counts.get(endmember.id, 0) > 0
            else "never"
        )
        for endmember in endmembers
    }


def audit(
    endmembers: list[Endmember], target: tuple[Fraction, Fraction, Fraction]
) -> AuditResult:
    direction_classes = _direction_classes(endmembers, target)

    best: list[Solution] = []
    for size in range(1, MAX_SUPPORT + 1):
        candidates: list[Solution] = []
        for combo in combinations(direction_classes, size):
            candidates.extend(_enumerate_support_solutions(combo, target))
        if candidates:
            min_cost = min(s.cost for s in candidates)
            best = sorted(
                (s for s in candidates if s.cost == min_cost),
                key=lambda s: s.ids,
            )
            break

    if not best:
        return AuditResult(feasible=False)

    return AuditResult(
        feasible=True,
        solution=best[0],
        tied=best,
        classification=_classify(endmembers, best),
    )
