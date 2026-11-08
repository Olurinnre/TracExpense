from fastapi import FastAPI

from . import models  # noqa: F401  (registers the tables)
from .database import Base, engine
from .routers import auth, transactions

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Expense Tracker API")

app.include_router(auth.router)
app.include_router(transactions.router)


@app.get("/")
def health():
    return {"status": "ok"}