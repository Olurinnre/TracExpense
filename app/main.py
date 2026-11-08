from fastapi import FastAPI

from .database import Base, engine
from . import models  # noqa: F401  (import so the tables are registered)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Expense Tracker API")

@app.get("/")
def health():
    return {"status": "ok"}