import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Category, Household, Item, Recipe, RecipeItem
from ..schemas import (
    RecipeCreate, RecipeUpdate, RecipeResponse, RecipeItemBase,
    RecipeExportDocument, RecipeExportRecipe, RecipeExportIngredient,
    ParseIngredientsRequest, ParsedIngredient, ImportUrlRequest, ImportUrlResponse,
)
from ..auth import get_current_household
from .. import recipe_url
from ..ingredients import parse_ingredients, suggest_category_id
from ..utils import image_extension, sort_key

router = APIRouter(prefix="/api/recipes", tags=["recipes"])

_uploads_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "uploads"


@router.post("/upload-image")
async def upload_image(
    file: UploadFile,
    household: Household = Depends(get_current_household),
):
    ext = image_extension(file.content_type)
    if ext is None:
        raise HTTPException(status_code=400, detail="File must be a JPEG, PNG, GIF or WebP image")

    filename = f"{uuid.uuid4().hex}{ext}"
    dest = _uploads_dir / filename
    content = await file.read()
    dest.write_bytes(content)
    return {"image_url": f"/api/uploads/{filename}"}


@router.get("", response_model=list[RecipeResponse])
def list_recipes(
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    return sorted(
        db.query(Recipe).filter(Recipe.household_id == household.id).all(),
        key=lambda p: sort_key(p.name)
    )


def _export_recipe(recipe: Recipe, request: Request) -> RecipeExportRecipe:
    image_url = recipe.image_url
    if image_url and image_url.startswith("/"):
        # Make locally hosted images resolvable from another instance
        image_url = str(request.base_url).rstrip("/") + image_url
    return RecipeExportRecipe(
        name=recipe.name,
        description=recipe.description,
        image_url=image_url,
        categories=recipe.categories or [],
        ingredients=[
            RecipeExportIngredient(
                name=ri.item.name,
                quantity=ri.quantity,
                unit=ri.unit or "x",
                category=ri.item.category.name if ri.item.category else None,
            )
            for ri in recipe.recipe_items
        ],
    )


@router.get("/export", response_model=RecipeExportDocument)
def export_recipes(
    request: Request,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household),
):
    recipes = sorted(
        db.query(Recipe).filter(Recipe.household_id == household.id).all(),
        key=lambda r: sort_key(r.name),
    )
    return RecipeExportDocument(recipes=[_export_recipe(r, request) for r in recipes])


@router.get("/{recipe_id}/export", response_model=RecipeExportDocument)
def export_recipe(
    recipe_id: int,
    request: Request,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household),
):
    recipe = db.query(Recipe).filter(
        Recipe.id == recipe_id, Recipe.household_id == household.id
    ).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return RecipeExportDocument(recipes=[_export_recipe(recipe, request)])


@router.post("/parse-ingredients", response_model=list[ParsedIngredient])
def parse_ingredient_text(
    req: ParseIngredientsRequest,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household),
):
    """Turn pasted text (one ingredient per line) into quantity/unit/name rows."""
    existing = {
        i.name.strip().lower(): i.id
        for i in db.query(Item).filter(Item.household_id == household.id).all()
    }
    return [
        ParsedIngredient(**p, item_id=existing.get(p["name"].lower()))
        for p in parse_ingredients(req.text)
    ]


@router.post("/import-url", response_model=ImportUrlResponse)
async def import_recipe_from_url(
    req: ImportUrlRequest,
    household: Household = Depends(get_current_household),
):
    """Read a recipe from a web page's structured data (schema.org JSON-LD)."""
    url = req.url.strip()
    try:
        body, _ = await recipe_url.safe_get(url, recipe_url.MAX_PAGE_BYTES)
    except recipe_url.FetchError as e:
        raise HTTPException(status_code=400, detail=str(e))
    recipe = recipe_url.extract_recipe(body.decode("utf-8", errors="replace"), url)
    if recipe is None:
        raise HTTPException(status_code=422, detail="No recipe found on this page")
    if recipe["image_url"]:
        recipe["image_url"] = await recipe_url.download_image(recipe["image_url"])
    return recipe


@router.post("/import-json", response_model=list[RecipeResponse])
def import_recipes_json(
    doc: RecipeExportDocument,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household),
):
    """Create recipes from the portable format, matching/creating items by name."""
    if doc.format != "nakupak-recipes":
        raise HTTPException(status_code=400, detail="Unsupported format")
    if doc.version != 1:
        raise HTTPException(status_code=400, detail="Unsupported version")

    items = {
        i.name.strip().lower(): i
        for i in db.query(Item).filter(Item.household_id == household.id).all()
    }
    categories = {
        c.name.strip().lower(): c
        for c in db.query(Category).filter(Category.household_id == household.id).all()
    }

    def get_category(name: str | None) -> Category | None:
        name = (name or "").strip()
        if not name:
            return None
        key = name.lower()
        if key not in categories:
            cat = Category(name=name, household_id=household.id, sort_order=len(categories))
            db.add(cat)
            db.flush()
            categories[key] = cat
        return categories[key]

    created = []
    for r in doc.recipes:
        db_recipe = Recipe(
            name=r.name, description=r.description,
            image_url=r.image_url or None, categories=r.categories,
            household_id=household.id,
        )
        db.add(db_recipe)
        db.flush()
        seen = set()
        for ing in r.ingredients:
            key = ing.name.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            item = items.get(key)
            if item is None:
                cat = get_category(ing.category)
                suggested = None if cat else suggest_category_id(ing.name, items.values())
                item = Item(name=ing.name.strip(), household_id=household.id,
                            category_id=cat.id if cat else suggested)
                db.add(item)
                db.flush()
                items[key] = item
            db.add(RecipeItem(recipe_id=db_recipe.id, item_id=item.id,
                              quantity=ing.quantity, unit=ing.unit))
        created.append(db_recipe)

    db.commit()
    for r in created:
        db.refresh(r)
    return created


@router.post("", response_model=RecipeResponse)
def create_recipe(
    recipe: RecipeCreate,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    db_recipe = Recipe(name=recipe.name, description=recipe.description, image_url=recipe.image_url,
                       categories=recipe.categories, household_id=household.id)
    db.add(db_recipe)
    db.commit()
    db.refresh(db_recipe)

    for item in recipe.items:
        recipe_item = RecipeItem(
            recipe_id=db_recipe.id,
            item_id=item.item_id,
            quantity=item.quantity,
            unit=item.unit,
        )
        db.add(recipe_item)

    db.commit()
    db.refresh(db_recipe)
    return db_recipe


@router.put("/{recipe_id}", response_model=RecipeResponse)
def update_recipe(
    recipe_id: int,
    recipe: RecipeUpdate,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    db_recipe = db.query(Recipe).filter(
        Recipe.id == recipe_id,
        Recipe.household_id == household.id
    ).first()
    if not db_recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    if recipe.name is not None:
        db_recipe.name = recipe.name
    if recipe.description is not None:
        db_recipe.description = recipe.description
    if recipe.image_url is not None:
        db_recipe.image_url = recipe.image_url or None
    if recipe.categories is not None:
        db_recipe.categories = recipe.categories

    if recipe.items is not None:
        db.query(RecipeItem).filter(RecipeItem.recipe_id == recipe_id).delete()
        for item in recipe.items:
            recipe_item = RecipeItem(
                recipe_id=recipe_id,
                item_id=item.item_id,
                quantity=item.quantity,
                unit=item.unit,
            )
            db.add(recipe_item)

    db.commit()
    db.refresh(db_recipe)
    return db_recipe


@router.delete("/{recipe_id}")
def delete_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    household: Household = Depends(get_current_household)
):
    db_recipe = db.query(Recipe).filter(
        Recipe.id == recipe_id,
        Recipe.household_id == household.id
    ).first()
    if not db_recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    db.delete(db_recipe)
    db.commit()
    return {"ok": True}
