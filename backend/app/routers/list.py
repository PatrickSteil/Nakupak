from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from ..database import get_db
from ..models import Household, Item, ShoppingListItem, Recipe, RecipeItem, SessionItem, ShoppingSession
from ..schemas import (
    ShoppingListItemCreate, ShoppingListItemUpdate, ShoppingListItemResponse,
    AddItemsRequest, BulkIdsRequest, PoolItemResponse, ItemResponse, ShoppingSessionResponse
)
from ..auth import get_current_household
from ..websocket import broadcast_update

router = APIRouter(prefix="/api", tags=["list"])


@router.get("/list", response_model=list[ShoppingListItemResponse])
def get_shopping_list(
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    # Clean up any orphaned shopping list items (item was deleted via bulk operation)
    db.query(ShoppingListItem).filter(
        ShoppingListItem.household_id == household.id,
        ~ShoppingListItem.item_id.in_(
            db.query(Item.id)
        )
    ).delete(synchronize_session=False)
    db.commit()

    return db.query(ShoppingListItem).filter(
        ShoppingListItem.household_id == household.id
    ).all()


@router.post("/list/add", response_model=list[ShoppingListItemResponse])
def add_items_to_list(
    request: AddItemsRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    added_items = []
    for item_data in request.items:
        existing = db.query(ShoppingListItem).filter(
            ShoppingListItem.item_id == item_data.item_id,
            ShoppingListItem.household_id == household.id
        ).first()

        if existing:
            if existing.unit == item_data.unit:
                existing.quantity += item_data.quantity
            else:
                existing.quantity = item_data.quantity
                existing.unit = item_data.unit
            db.commit()
            db.refresh(existing)
            added_items.append(existing)
        else:
            new_item = ShoppingListItem(
                item_id=item_data.item_id,
                quantity=item_data.quantity,
                unit=item_data.unit,
                household_id=household.id
            )
            db.add(new_item)
            db.commit()
            db.refresh(new_item)
            added_items.append(new_item)

    background_tasks.add_task(broadcast_update, household.id, "list_updated", {})
    return added_items


@router.put("/list/{list_item_id}", response_model=ShoppingListItemResponse)
def update_list_item(
    list_item_id: int,
    update: ShoppingListItemUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    item = db.query(ShoppingListItem).filter(
        ShoppingListItem.id == list_item_id,
        ShoppingListItem.household_id == household.id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="List item not found")

    item.quantity = update.quantity
    if update.unit is not None:
        item.unit = update.unit
    db.commit()
    db.refresh(item)
    background_tasks.add_task(broadcast_update, household.id, "list_updated", {})
    return item


@router.delete("/list/{list_item_id}")
def remove_from_list(
    list_item_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    item = db.query(ShoppingListItem).filter(
        ShoppingListItem.id == list_item_id,
        ShoppingListItem.household_id == household.id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="List item not found")

    db.delete(item)
    db.commit()
    background_tasks.add_task(broadcast_update, household.id, "list_updated", {})
    return {"ok": True}


@router.post("/list/remove")
def bulk_remove_from_list(
    request: BulkIdsRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    deleted = db.query(ShoppingListItem).filter(
        ShoppingListItem.id.in_(request.ids),
        ShoppingListItem.household_id == household.id
    ).delete(synchronize_session=False)
    db.commit()
    background_tasks.add_task(broadcast_update, household.id, "list_updated", {})
    return {"ok": True, "deleted": deleted}


@router.delete("/list")
def clear_list(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    deleted = db.query(ShoppingListItem).filter(
        ShoppingListItem.household_id == household.id
    ).delete(synchronize_session=False)
    db.commit()
    background_tasks.add_task(broadcast_update, household.id, "list_updated", {})
    return {"ok": True, "deleted": deleted}


@router.post("/list/add-recipe/{recipe_id}", response_model=list[ShoppingListItemResponse])
def add_recipe_to_list(
    recipe_id: int,
    background_tasks: BackgroundTasks,
    multiplier: float = Query(1, gt=0, le=100),
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    recipe = db.query(Recipe).filter(
        Recipe.id == recipe_id,
        Recipe.household_id == household.id
    ).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    added_items = []
    for recipe_item in recipe.recipe_items:
        if not recipe_item.item:
            continue
        existing = db.query(ShoppingListItem).filter(
            ShoppingListItem.item_id == recipe_item.item_id,
            ShoppingListItem.household_id == household.id
        ).first()

        if existing:
            existing.quantity += round(recipe_item.quantity * multiplier, 4)
            existing.unit = recipe_item.unit
            existing.from_recipe_id = recipe_id
            db.commit()
            db.refresh(existing)
            added_items.append(existing)
        else:
            new_item = ShoppingListItem(
                item_id=recipe_item.item_id,
                quantity=round(recipe_item.quantity * multiplier, 4),
                unit=recipe_item.unit,
                household_id=household.id,
                from_recipe_id=recipe_id
            )
            db.add(new_item)
            db.commit()
            db.refresh(new_item)
            added_items.append(new_item)

    background_tasks.add_task(broadcast_update, household.id, "list_updated", {})
    return added_items


@router.put("/list/{list_item_id}/check")
def toggle_check(
    list_item_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    item = db.query(ShoppingListItem).filter(
        ShoppingListItem.id == list_item_id,
        ShoppingListItem.household_id == household.id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="List item not found")

    item.checked = not item.checked
    db.commit()
    db.refresh(item)
    background_tasks.add_task(broadcast_update, household.id, "list_updated", {})
    return {"checked": item.checked}


@router.post("/list/purchase", response_model=ShoppingSessionResponse)
def purchase_checked(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    checked_items = db.query(ShoppingListItem).filter(
        ShoppingListItem.household_id == household.id,
        ShoppingListItem.checked == True
    ).all()

    if not checked_items:
        raise HTTPException(status_code=400, detail="No checked items")

    now = datetime.utcnow()
    session = ShoppingSession(household_id=household.id, completed_at=now)
    db.add(session)
    db.flush()

    for list_item in checked_items:
        session_item = SessionItem(
            session_id=session.id,
            item_id=list_item.item_id,
            item_name=list_item.item.name,
            quantity=list_item.quantity,
            unit=list_item.unit,
            checked=True,
            checked_at=now,
        )
        db.add(session_item)

    db.query(ShoppingListItem).filter(
        ShoppingListItem.id.in_([i.id for i in checked_items]),
        ShoppingListItem.household_id == household.id
    ).delete(synchronize_session=False)

    db.commit()
    db.refresh(session)
    background_tasks.add_task(broadcast_update, household.id, "list_updated", {})
    return session


@router.get("/pool", response_model=list[PoolItemResponse])
def get_pool(
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)

    items = db.query(Item).filter(Item.household_id == household.id).all()
    pool_items = []

    for item in items:
        frequency = db.query(SessionItem).filter(
            SessionItem.item_id == item.id,
            SessionItem.checked == True
        ).count()

        last_session_item = db.query(SessionItem).filter(
            SessionItem.item_id == item.id,
            SessionItem.checked_at != None
        ).order_by(SessionItem.checked_at.desc()).first()

        last_added = last_session_item.checked_at if last_session_item else None

        recency_score = 0.0
        if last_added and last_added > thirty_days_ago:
            days_ago = (now - last_added).days
            recency_score = max(0, (30 - days_ago) / 30)

        frequency_score = min(frequency / 10, 1.0)
        score = (recency_score * 0.4) + (frequency_score * 0.6)

        if frequency > 0 or last_added:
            pool_items.append(PoolItemResponse(
                item=ItemResponse.model_validate(item),
                score=score,
                frequency=frequency,
                last_added=last_added
            ))

    pool_items.sort(key=lambda x: x.score, reverse=True)
    return pool_items[:50]
