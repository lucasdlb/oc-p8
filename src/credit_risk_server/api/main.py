"""FastAPI app factory, middleware, exception handlers."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from credit_risk_server.core.config import api_settings
from credit_risk_server.core.exceptions import InvalidInputError, ModelLoadError, PredictionError
from credit_risk_server.models.loader import load_model


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model = load_model(api_settings.model_path)
    yield
    app.state.model = None


app = FastAPI(lifespan=lifespan)


@app.exception_handler(InvalidInputError)
async def invalid_input_handler(request, exc):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(ModelLoadError)
async def model_load_handler(request, exc):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(PredictionError)
async def prediction_error_handler(request, exc):
    return JSONResponse(status_code=500, content={"detail": str(exc)})
