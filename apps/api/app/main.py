from fastapi import FastAPI

app = FastAPI(title="Telugu Global API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
