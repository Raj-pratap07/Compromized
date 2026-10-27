from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.errors import ConfigurationError, ProviderError, RecordNotFoundError, RecoveryError

app = FastAPI(title="Firefly", debug=False)
app.include_router(router)


@app.exception_handler(RecordNotFoundError)
def handle_not_found(_request: Request, _exc: RecordNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Record not found"})


@app.exception_handler(RecoveryError)
def handle_recovery_error(_request: Request, _exc: RecoveryError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "Secret recovery is unavailable"})


@app.exception_handler(ProviderError)
def handle_provider_error(_request: Request, _exc: ProviderError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "A required service is unavailable"})


@app.exception_handler(ConfigurationError)
def handle_configuration_error(_request: Request, _exc: ConfigurationError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "Firefly is not correctly configured"})