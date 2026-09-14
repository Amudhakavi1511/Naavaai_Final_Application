"""
Naavaai API — Maritime procurement decision support backend.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.orchestration import ConfigMissingError, run_decision_engine
from app.api.reference_data import load_demo_reference_data
from app.api.schemas import DecisionEngineResponse, OptimizationRunRequest
from app.api.whatif import WhatIfValidationError, run_what_if
from app.api.whatif_schemas import WhatIfRequest, WhatIfResponse


app = FastAPI(
    title="Naavaai API",
    description="Maritime procurement decision support API.",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

# Local development:
#   FRONTEND_URL=http://localhost:5173
#
# Production:
#   FRONTEND_URL=https://your-naavaai.vercel.app
#
# Only the configured frontend origin is allowed to call the API.

FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:5173",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

# Currently loaded at process startup.
# This remains the application's existing reference-data mechanism.
_reference_data = load_demo_reference_data()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Optimization
# ---------------------------------------------------------------------------

@app.post(
    "/optimization/run",
    response_model=DecisionEngineResponse,
)
def optimization_run(
    request: OptimizationRunRequest,
) -> DecisionEngineResponse:

    try:
        return run_decision_engine(
            request,
            _reference_data,
        )

    except ConfigMissingError as e:
        raise HTTPException(
            status_code=500,
            detail=f"CONFIG_MISSING: {e}",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=f"REFERENCE_DATA_INCOMPLETE: {e}",
        )


# ---------------------------------------------------------------------------
# What-if analysis
# ---------------------------------------------------------------------------

@app.post(
    "/optimization/what-if",
    response_model=WhatIfResponse,
)
def optimization_what_if(
    request: WhatIfRequest,
) -> WhatIfResponse:

    try:
        return run_what_if(
            request,
            _reference_data,
        )

    except WhatIfValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=f"INVALID_WHATIF_CHANGES: {e}",
        )

    except ConfigMissingError as e:
        raise HTTPException(
            status_code=500,
            detail=f"CONFIG_MISSING: {e}",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=f"REFERENCE_DATA_INCOMPLETE: {e}",
        )
