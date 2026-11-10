from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Household, Category, Item, ShoppingListItem, RecipeItem, SessionItem, ShoppingSession
from ..schemas import (
    CategoryCreate, CategoryUpdate, CategoryResponse,
    ItemCreate, ItemUpdate, ItemResponse, MergeItemsRequest,
    BulkIdsRequest, BulkSetCategoryRequest
)
from ..auth import get_current_household
from ..ingredients import suggest_category_id
from ..utils import sort_key
from ..websocket import broadcast_update

router = APIRouter(prefix="/api", tags=["items"])


@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    return sorted(
        db.query(Category).filter(Category.household_id == household.id).all(),
        key=lambda c: (c.sort_order or 0, sort_key(c.name))
    )


@router.post("/categories/reorder", response_model=list[CategoryResponse])
def reorder_categories(
    req: BulkIdsRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    """Set the store-walk order: position in `ids` becomes the sort_order."""
    cats = {
        c.id: c for c in db.query(Category).filter(Category.household_id == household.id).all()
    }
    if len(set(req.ids)) != len(req.ids) or set(req.ids) != set(cats):
        raise HTTPException(status_code=400, detail="ids must list every category exactly once")
    for position, cat_id in enumerate(req.ids):
        cats[cat_id].sort_order = position
    db.commit()
    background_tasks.add_task(broadcast_update, household.id, "categories_updated", {})
    return [cats[i] for i in req.ids]


@router.post("/categories", response_model=CategoryResponse)
def create_category(
    category: CategoryCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    data = category.model_dump()
    if "sort_order" not in category.model_fields_set:
        # New categories go to the end of the store route
        last = db.query(func.max(Category.sort_order)).filter(
            Category.household_id == household.id
        ).scalar()
        data["sort_order"] = 0 if last is None else last + 1
    db_category = Category(**data, household_id=household.id)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    background_tasks.add_task(broadcast_update, household.id, "categories_updated", {})
    return db_category


@router.put("/categories/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    category: CategoryUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    db_category = db.query(Category).filter(
        Category.id == category_id,
        Category.household_id == household.id
    ).first()
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")

    update_data = category.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_category, key, value)

    db.commit()
    db.refresh(db_category)
    background_tasks.add_task(broadcast_update, household.id, "categories_updated", {})
    return db_category


@router.delete("/categories/{category_id}")
def delete_category(
    category_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    db_category = db.query(Category).filter(
        Category.id == category_id,
        Category.household_id == household.id
    ).first()
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")

    db.delete(db_category)
    db.commit()
    background_tasks.add_task(broadcast_update, household.id, "categories_updated", {})
    return {"ok": True}


@router.get("/items", response_model=list[ItemResponse])
def list_items(
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    return sorted(
        db.query(Item).filter(Item.household_id == household.id).all(),
        key=lambda i: sort_key(i.name)
    )


@router.post("/items", response_model=ItemResponse)
def create_item(
    item: ItemCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    data = item.model_dump()
    if data.get("category_id") is None:
        # Suggest a category from similar existing items ("Vollmilch" -> same as "Milch")
        data["category_id"] = suggest_category_id(
            item.name, db.query(Item).filter(Item.household_id == household.id).all()
        )
    db_item = Item(**data, household_id=household.id)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)

    # Re-link orphaned session items with matching name to the new item
    db.query(SessionItem).filter(
        SessionItem.item_id == None,
        SessionItem.item_name == db_item.name,
        SessionItem.session_id.in_(
            db.query(ShoppingSession.id).filter(
                ShoppingSession.household_id == household.id
            )
        )
    ).update({"item_id": db_item.id}, synchronize_session=False)
    db.commit()

    background_tasks.add_task(broadcast_update, household.id, "items_updated", {})
    return db_item


@router.put("/items/{item_id}", response_model=ItemResponse)
def update_item(
    item_id: int,
    item: ItemUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    db_item = db.query(Item).filter(
        Item.id == item_id,
        Item.household_id == household.id
    ).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")

    update_data = item.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)

    db.commit()
    db.refresh(db_item)
    background_tasks.add_task(broadcast_update, household.id, "items_updated", {})
    return db_item


@router.delete("/items/{item_id}")
def delete_item(
    item_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    db_item = db.query(Item).filter(
        Item.id == item_id,
        Item.household_id == household.id
    ).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")

    db.delete(db_item)
    db.commit()
    background_tasks.add_task(broadcast_update, household.id, "items_updated", {})
    background_tasks.add_task(broadcast_update, household.id, "list_updated", {})
    return {"ok": True}


@router.post("/items/set-category")
def bulk_set_category(
    request: BulkSetCategoryRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    if request.category_id is not None:
        category = db.query(Category).filter(
            Category.id == request.category_id,
            Category.household_id == household.id
        ).first()
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")

    updated = db.query(Item).filter(
        Item.id.in_(request.item_ids),
        Item.household_id == household.id
    ).update({"category_id": request.category_id}, synchronize_session=False)
    db.commit()
    background_tasks.add_task(broadcast_update, household.id, "items_updated", {})
    return {"ok": True, "updated": updated}


@router.post("/items/delete")
def bulk_delete_items(
    request: BulkIdsRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    # Delete associated shopping list items and recipe items first to avoid orphans
    db.query(ShoppingListItem).filter(ShoppingListItem.item_id.in_(request.ids)).delete(synchronize_session=False)
    db.query(RecipeItem).filter(RecipeItem.item_id.in_(request.ids)).delete(synchronize_session=False)
    db.query(SessionItem).filter(SessionItem.item_id.in_(request.ids)).delete(synchronize_session=False)

    deleted = db.query(Item).filter(
        Item.id.in_(request.ids),
        Item.household_id == household.id
    ).delete(synchronize_session=False)
    db.commit()
    background_tasks.add_task(broadcast_update, household.id, "items_updated", {})
    background_tasks.add_task(broadcast_update, household.id, "list_updated", {})
    return {"ok": True, "deleted": deleted}


@router.post("/items/{target_id}/merge", response_model=ItemResponse)
def merge_items(
    target_id: int,
    request: MergeItemsRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    target_item = db.query(Item).filter(
        Item.id == target_id,
        Item.household_id == household.id
    ).first()
    if not target_item:
        raise HTTPException(status_code=404, detail="Target item not found")

    source_ids = [sid for sid in request.source_ids if sid != target_id]
    if not source_ids:
        return target_item

    db.query(ShoppingListItem).filter(ShoppingListItem.item_id.in_(source_ids)).update(
        {"item_id": target_id}, synchronize_session=False
    )
    db.query(RecipeItem).filter(RecipeItem.item_id.in_(source_ids)).update(
        {"item_id": target_id}, synchronize_session=False
    )
    db.query(SessionItem).filter(SessionItem.item_id.in_(source_ids)).update(
        {"item_id": target_id}, synchronize_session=False
    )

    db.query(Item).filter(Item.id.in_(source_ids)).delete(synchronize_session=False)

    db.commit()
    db.refresh(target_item)
    background_tasks.add_task(broadcast_update, household.id, "items_updated", {})
    background_tasks.add_task(broadcast_update, household.id, "list_updated", {})
    return target_item
