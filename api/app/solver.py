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
vanishes), hence the participating *rays* determine the combination
shape and the set of minimum-support solutions is finite.

Same-ray endmembers (collinear with the target on one directed line) are
interchangeable at the ray level: if a ray participates with direction
weight ``delta`` using a representative at ray distance ``d_rep``, any
other member at distance ``d`` on that ray participates with weight
``delta * d_rep / d``.  Alternatives therefore combine as a Cartesian
product across rays, e.g. lane widths 2 x 3 x 4 yield 24 tied solutions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from itertools import combinations, product
from typing import Iterable

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
    """All cheapest endmembers lying on one directed ray from the target.

    ``members`` are interchangeable alternatives (same minimum cost);
    ``rep`` / ``rep_distance`` are the representative used to solve the
    ray-level balance and its distance along the normalised ray.
    """

    direction: tuple[Fraction, Fraction, Fraction]
    members: tuple[Endmember, ...]
    rep: Endmember
    rep_distance: Fraction


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


def _ray_delta(
    point: tuple[int, int, int],
    target: tuple[Fraction, Fraction, Fraction],
) -> tuple[Fraction, Fraction, Fraction]:
    return tuple(Fraction(point[i]) - target[i] for i in range(3))


def _ray_distance(delta: Iterable[Fraction]) -> Fraction:
    """Distance of a point along its ray.

    Rays are normalised by the absolute value of their first non-zero
    component, so this is exactly the scale used in :func:`_direction_key`.
    A point at the target has distance 0.
    """
    pivot = next((value for value in delta if value != 0), None)
    return abs(pivot) if pivot is not None else Fraction(0)


def _direction_key(
    point: tuple[int, int, int],
    target: tuple[Fraction, Fraction, Fraction],
) -> tuple[Fraction, Fraction, Fraction]:
    delta = _ray_delta(point, target)
    pivot = next((value for value in delta if value != 0), None)
    if pivot is None:
        return (Fraction(0), Fraction(0), Fraction(0))
    scale = abs(pivot)
    return tuple(value / scale for value in delta)


def _direction_classes(
    endmembers: list[Endmember],
    target: tuple[Fraction, Fraction, Fraction],
) -> list[DirectionClass]:
    """Group endmembers by directed ray, keeping cheapest alternatives.

    Within a ray only the minimum-cost members can occur in a cost-optimal
    solution; every retained member is an interchangeable alternative.
    """
    grouped: dict[
        tuple[Fraction, Fraction, Fraction], list[Endmember]
    ] = {}
    for endmember in endmembers:
        key = _direction_key(endmember.t, target)
        grouped.setdefault(key, []).append(endmember)

    classes: list[DirectionClass] = []
    for direction, members in grouped.items():
        min_cost = min(member.cost for member in members)
        cheapest = tuple(member for member in members if member.cost == min_cost)
        rep = cheapest[0]
        rep_distance = _ray_distance(_ray_delta(rep.t, target))
        classes.append(
            DirectionClass(
                direction=direction,
                members=cheapest,
                rep=rep,
                rep_distance=rep_distance,
            )
        )
    return classes


def _member_distance(
    member: Endmember, target: tuple[Fraction, Fraction, Fraction]
) -> Fraction:
    return _ray_distance(_ray_delta(member.t, target))


def _expand_ray_solution(
    groups: tuple[DirectionClass, ...],
    direction_weights: tuple[Fraction, ...],
    target: tuple[Fraction, Fraction, Fraction],
) -> list[Solution]:
    """Expand one ray-level balance into every member-level solution.

    A member at distance ``d`` pulling as hard as its ray's representative
    needs weight proportional to ``delta * d_rep / d`` (same contribution
    vector ``w * d * u``).  Swapping members at different distances keeps
    the homogeneous balance but changes the total mass, so each selection
    is renormalised to sum to one -- the positive balance cone of an
    affinely independent ray set is one-dimensional, hence this common
    scale is the only freedom.
    """
    lanes: list[list[tuple[Endmember, Fraction]]] = []
    for group, direction_weight in zip(groups, direction_weights):
        if group.rep_distance == 0:
            # A ray of length zero means the member coincides with the
            # target; a size-1 solution carries weight 1.
            lane = [(member, Fraction(1)) for member in group.members]
        else:
            lane = []
            for member in group.members:
                distance = _member_distance(member, target)
                lane.append(
                    (member, direction_weight * group.rep_distance / distance)
                )
        lanes.append(lane)

    solutions: list[Solution] = []
    for chosen in product(*lanes):
        scale = Fraction(1) / sum(weight for _, weight in chosen)
        weighted = [(member, weight * scale) for member, weight in chosen]
        ordered = sorted(weighted, key=lambda item: item[0].id)
        solutions.append(
            Solution(
                ids=tuple(member.id for member, _ in ordered),
                weights=tuple(weight for _, weight in ordered),
                cost=sum(member.cost for member, _ in weighted),
            )
        )
    return solutions


def _classify(
    endmembers: list[Endmember], solutions: list[Solution]
) -> dict[str, str]:
    """always / partial / never from participation across all tied optima."""
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

    # At the first feasible support size, positive balance depends only on
    # ray directions (not member distances), and every balancing ray set is
    # affinely independent for all member choices -- otherwise a smaller
    # subset would already balance, contradicting minimality of the size.
    # One representative per ray therefore suffices for this feasibility
    # test; per-member weights are derived afterwards.
    best: list[Solution] = []
    for size in range(1, MAX_SUPPORT + 1):
        candidates: list[Solution] = []
        for combo in combinations(direction_classes, size):
            representatives = [group.rep for group in combo]
            direction_weights = solve_weights(
                [member.t for member in representatives], target
            )
            if direction_weights is None:
                continue
            candidates.extend(
                _expand_ray_solution(combo, direction_weights, target)
            )
        if candidates:
            min_cost = min(s.cost for s in candidates)
            best = sorted(
                (s for s in candidates if s.cost == min_cost),
                key=lambda s: tuple(s.ids),
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
