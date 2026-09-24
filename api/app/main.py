"""FastAPI application for the volcanic-ash endmember audit."""

from __future__ import annotations

from fractions import Fraction

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .models import (
    AuditRequest,
    AuditResponse,
    SolutionOut,
    WeightOut,
)
from .solver import AuditResult, Solution, audit
from .validation import validate_request

app = FastAPI(title="Volcanic Ash Endmember Audit", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
def _on_schema_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for err in exc.errors():
        if err.get("type", "").startswith("json_"):
            errors.append({"field": "body", "message": "请求体不是合法 JSON"})
            continue
        parts: list[str] = []
        for p in err.get("loc", []):
            if isinstance(p, int):
                # array position -> "[i]", appended directly to previous name
                if parts:
                    parts[-1] = f"{parts[-1]}[{p}]"
                else:
                    parts.append(f"[{p}]")
            elif isinstance(p, str) and p not in ("body", ""):
                parts.append(p)
        field = ".".join(parts) if parts else "body"
        errors.append({"field": field, "message": err.get("msg", "输入格式有误")})
    return JSONResponse(
        status_code=200,
        content={"feasible": False, "solution": None, "tied": [], "tie_count": 0,
                 "classification": {}, "errors": errors},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _weight_out(endmember_id: str, w: Fraction) -> WeightOut:
    # canonical reduced fraction: Fraction is always in lowest terms
    text = str(w.numerator) if w.denominator == 1 else f"{w.numerator}/{w.denominator}"
    return WeightOut(
        id=endmember_id,
        fraction=text,
        numerator=w.numerator,
        denominator=w.denominator,
        decimal=float(w),
    )


def _solution_out(sol: Solution) -> SolutionOut:
    return SolutionOut(
        ids=list(sol.ids),
        weights=[_weight_out(i, w) for i, w in zip(sol.ids, sol.weights)],
        cost=sol.cost,
    )


def _serialize(result: AuditResult) -> AuditResponse:
    return AuditResponse(
        feasible=result.feasible,
        solution=_solution_out(result.solution) if result.solution else None,
        tied=[_solution_out(s) for s in result.tied],
        tie_count=len(result.tied),
        classification=result.classification,
        errors=[],
    )


@app.post("/api/audit", response_model=AuditResponse)
def run_audit(req: AuditRequest) -> AuditResponse:
    endmembers, target, errors = validate_request(req.endmembers, list(req.target))
    if errors:
        return AuditResponse(feasible=False, errors=errors)
    return _serialize(audit(endmembers, target))
