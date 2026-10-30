"""
SleepGPT Backend — Application Entry Point
--------------------------------------------
Initializes the FastAPI application, configures middleware, and registers
all routers for the patient flow, admin flow, chat, and future sensor
integration.
"""

import os
from pathlib import Path

try:  # load backend/.env (UBIDOTS_TOKEN, SOMNNET_*, SLEEPGPT_* ...) before any router reads os.environ
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import admin, assessment, chat, ml, patient, sensors

# -----------------------------------------------------------------------
# Application instance
# -----------------------------------------------------------------------
app = FastAPI(
    title="SleepGPT API",
    description="AI-powered Sleep Apnea Screening & Clinical Decision-Support System",
    version="1.0.0",
)

# -----------------------------------------------------------------------
# CORS Middleware
# -----------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("SLEEPGPT_CORS_ORIGINS", "http://localhost:5173,http://localhost:5174,http://localhost:5175").split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------
# Routers
# -----------------------------------------------------------------------
app.include_router(patient.router, prefix="/api/patient", tags=["Patient"])
app.include_router(assessment.router, prefix="/api/assessment", tags=["Assessment"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(sensors.router, prefix="/api/sensors", tags=["Sensors"])
app.include_router(ml.router, prefix="/api/ml", tags=["ML (SomnNET SpO2)"])


# -----------------------------------------------------------------------
# Root / Health Check
# -----------------------------------------------------------------------
@app.get("/", tags=["System"])
async def root():
    return {"service": "SleepGPT API", "status": "running", "version": "1.0.0"}


@app.get("/health", tags=["System"])
async def health_check():
    """
    Simple health check endpoint.
    Used by load balancers, container orchestrators, and monitoring tools
    to verify that the service is up and responsive.
    """
    return {"status": "running"}


# -----------------------------------------------------------------------
# Local dev entry point
# -----------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
