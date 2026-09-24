"""Strict input validation with field-localised, deterministic errors."""

from __future__ import annotations

import re
from fractions import Fraction

from .models import EndmemberIn, FieldError
from .solver import Endmember

MIN_ENDMEMBERS = 3
MAX_ENDMEMBERS = 30
MAX_TRACER_ABS = 1_000_000
MAX_TARGET_DECIMALS = 4

_INT_RE = re.compile(r"^[+-]?\d+$")
# Optional sign, then either digits with up to four optional decimals, or a
# leading-dot fraction.  Exponents and other notations are rejected.
_TARGET_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d{1,4})?|\.\d{1,4})$")


def parse_int(raw: str) -> int:
    s = raw.strip()
    if not _INT_RE.match(s):
        raise ValueError("必须是整数")
    return int(s)


def parse_target(raw: str) -> Fraction:
    s = raw.strip()
    if not _TARGET_RE.match(s):
        raise ValueError(
            f"必须是至多 {MAX_TARGET_DECIMALS} 位小数的数值（如 1.5 或 -2）"
        )
    return Fraction(s)


def validate_request(
    endmembers: list[EndmemberIn], target_raw: list[str]
) -> tuple[list[Endmember], tuple[Fraction, Fraction, Fraction], list[FieldError]]:
    errors: list[FieldError] = []

    # --- batch-level rules -------------------------------------------------
    if len(endmembers) < MIN_ENDMEMBERS or len(endmembers) > MAX_ENDMEMBERS:
        errors.append(
            FieldError(
                field="endmembers",
                message=(
                    f"每批需含 {MIN_ENDMEMBERS} 至 {MAX_ENDMEMBERS} 个端元，"
                    f"当前为 {len(endmembers)} 个"
                ),
            )
        )

    seen: set[str] = set()
    for i, em in enumerate(endmembers):
        em_id = em.id.strip()
        if not em_id:
            errors.append(FieldError(field=f"endmembers[{i}].id", message="标识不能为空"))
        else:
            try:
                em_id.encode("ascii")
            except UnicodeEncodeError:
                errors.append(
                    FieldError(field=f"endmembers[{i}].id", message="标识必须为 ASCII 字符")
                )
            if em_id in seen:
                errors.append(
                    FieldError(field=f"endmembers[{i}].id", message=f"标识 {em_id!r} 重复")
                )
            seen.add(em_id)

        for j, name in enumerate(("t0", "t1", "t2")):
            try:
                v = parse_int(getattr(em, name))
            except ValueError as exc:
                errors.append(
                    FieldError(field=f"endmembers[{i}].{name}", message=str(exc))
                )
                continue
            if abs(v) > MAX_TRACER_ABS:
                errors.append(
                    FieldError(
                        field=f"endmembers[{i}].{name}",
                        message=f"示踪值绝对值不得超过 {MAX_TRACER_ABS}",
                    )
                )

        try:
            cost = parse_int(em.cost)
        except ValueError as exc:
            errors.append(FieldError(field=f"endmembers[{i}].cost", message=str(exc)))
        else:
            if cost <= 0:
                errors.append(
                    FieldError(
                        field=f"endmembers[{i}].cost", message="复核代价必须为正整数"
                    )
                )

    if len(target_raw) != 3:
        errors.append(
            FieldError(field="target", message="目标必须恰好包含三个示踪值")
        )

    target_values: list[Fraction] = []
    for j, raw in enumerate(target_raw[:3] if len(target_raw) >= 3 else target_raw):
        try:
            target_values.append(parse_target(raw))
        except ValueError as exc:
            errors.append(FieldError(field=f"target[{j}]", message=str(exc)))

    if errors:
        return [], (Fraction(0), Fraction(0), Fraction(0)), errors

    parsed = [
        Endmember(
            id=em.id.strip(),
            t=(int(em.t0), int(em.t1), int(em.t2)),
            cost=int(em.cost),
        )
        for em in endmembers
    ]
    target = (target_values[0], target_values[1], target_values[2])
    return parsed, target, []
