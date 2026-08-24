"""FastAPI application entrypoint."""

from fastapi import FastAPI

app = FastAPI(title="Kiba API", version="0.1.0")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Report whether the API process is healthy."""
    return {"status": "ok"}
