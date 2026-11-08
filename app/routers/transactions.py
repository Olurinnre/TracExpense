import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy import func, select

from .. import models, schemas
from ..database import get_db
from ..security import get_current_user

router = APIRouter(prefix="/transactions", tags=["transactions"])


def get_owned_transaction(tx_id: int, db: Session, user: models.User) -> models.Transaction:
    tx = db.scalar(
        select(models.Transaction).where(
            models.Transaction.id == tx_id,
            models.Transaction.user_id == user.id,
        )
    )
    if tx is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
    return tx


@router.post("", response_model=schemas.TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(
    data: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    tx = models.Transaction(**data.model_dump(), user_id=user.id)
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


@router.get("", response_model=list[schemas.TransactionOut])
def list_transactions(
    type: str | None = None,
    category: str | None = None,
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    T = models.Transaction
    query = select(T).where(T.user_id == user.id)
    if type:
        query = query.where(T.type == type)
    if category:
        query = query.where(T.category == category)
    if date_from:
        query = query.where(T.date >= date_from)
    if date_to:
        query = query.where(T.date <= date_to)
    query = query.order_by(T.date.desc(), T.id.desc()).offset(skip).limit(limit)
    return db.scalars(query).all()

@router.get("/summary/overview")
def summary(
    year: int | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    T = models.Transaction
    filters = [T.user_id == user.id]
    if year:
        filters.append(func.strftime("%Y", T.date) == str(year))

    # 1. Totals by type (income / expense)
    totals = dict(
        db.execute(
            select(T.type, func.sum(T.amount)).where(*filters).group_by(T.type)
        ).all()
    )
    income = totals.get("income") or 0
    expense = totals.get("expense") or 0

    # 2. Expenses by category, biggest first
    by_category = db.execute(
        select(T.category, func.sum(T.amount))
        .where(*filters, T.type == "expense")
        .group_by(T.category)
        .order_by(func.sum(T.amount).desc())
    ).all()

    # 3. Income and expense per month
    month = func.strftime("%Y-%m", T.date)
    by_month_rows = db.execute(
        select(month, T.type, func.sum(T.amount))
        .where(*filters)
        .group_by(month, T.type)
        .order_by(month)
    ).all()

    months: dict[str, dict] = {}
    for m, tx_type, total in by_month_rows:
        entry = months.setdefault(m, {"month": m, "income": 0.0, "expense": 0.0})
        entry[tx_type] = float(total)

    return {
        "total_income": float(income),
        "total_expense": float(expense),
        "balance": float(income - expense),
        "expense_by_category": [
            {"category": c, "total": float(s)} for c, s in by_category
        ],
        "by_month": list(months.values()),
    }

@router.get("/{tx_id}", response_model=schemas.TransactionOut)
def get_transaction(
    tx_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return get_owned_transaction(tx_id, db, user)


@router.patch("/{tx_id}", response_model=schemas.TransactionOut)
def update_transaction(
    tx_id: int,
    data: schemas.TransactionUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    tx = get_owned_transaction(tx_id, db, user)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(tx, field, value)
    db.commit()
    db.refresh(tx)
    return tx


@router.delete("/{tx_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    tx_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    tx = get_owned_transaction(tx_id, db, user)
    db.delete(tx)
    db.commit()
    