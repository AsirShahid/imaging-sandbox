from fastapi import FastAPI

from .routers import deid, jobs, metadata, metrics, recon

app = FastAPI(
    title="Imaging Sandbox API",
    version="0.1.0",
    description=(
        "Demo-only imaging utilities: DICOM metadata, de-identification checks, "
        "image-quality metrics, and CT reconstruction. Public datasets only — "
        "no clinical data."
    ),
    # Public prefix: nginx serves the API under /api/ and strips it. root_path
    # makes /docs and /openapi.json resolve correctly behind that prefix.
    root_path="/api",
)

app.include_router(metadata.router)
app.include_router(deid.router)
app.include_router(metrics.router)
app.include_router(recon.router)
app.include_router(jobs.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}
