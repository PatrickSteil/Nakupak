from pydantic import BaseModel, BeforeValidator, StringConstraints
from datetime import datetime
from typing import Annotated, Optional


def _clean_categories(value):
    """Trim, drop blanks and case-insensitive duplicates, keep the first spelling."""
    seen, out = set(), []
    for v in value or []:
        name = " ".join(str(v).split())[:40]
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append(name)
    return out


RecipeCategories = Annotated[list[str], BeforeValidator(_clean_categories)]


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    household_id: int | None = None


class HouseholdCredentials(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    password: str


class HouseholdUpdate(BaseModel):
    name: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


class HouseholdResponse(BaseModel):
    name: str
    created_at: datetime

    class Config:
        from_attributes = True


class CategoryBase(BaseModel):
    name: str
    sort_order: int = 0
    color: str = "#6b7280"


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = None
    sort_order: int | None = None
    color: str | None = None


class CategoryResponse(CategoryBase):
    id: int

    class Config:
        from_attributes = True


class ItemBase(BaseModel):
    name: str
    category_id: int | None = None


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    name: str | None = None
    category_id: int | None = None


class ItemResponse(ItemBase):
    id: int
    created_at: datetime
    category: CategoryResponse | None = None

    class Config:
        from_attributes = True


class ShoppingListItemBase(BaseModel):
    item_id: int
    quantity: float = 1
    unit: str = "x"


class ShoppingListItemCreate(BaseModel):
    item_id: int
    quantity: float = 1
    unit: str = "x"


class ShoppingListItemUpdate(BaseModel):
    quantity: float
    unit: str | None = None


class ShoppingListItemResponse(BaseModel):
    id: int
    item_id: int
    quantity: float
    unit: str = "x"
    checked: bool = False
    added_at: datetime
    from_recipe_id: int | None
    item: ItemResponse

    class Config:
        from_attributes = True


class RecipeItemBase(BaseModel):
    item_id: int
    quantity: float = 1
    unit: str = "x"


class RecipeBase(BaseModel):
    name: str
    description: str | None = None
    image_url: str | None = None
    categories: RecipeCategories = []


class RecipeCreate(RecipeBase):
    items: list[RecipeItemBase] = []


class RecipeExportIngredient(BaseModel):
    name: str
    quantity: float = 1
    unit: str = "x"
    category: str | None = None


class RecipeExportRecipe(BaseModel):
    name: str
    description: str | None = None
    image_url: str | None = None
    categories: RecipeCategories = []
    ingredients: list[RecipeExportIngredient] = []


class RecipeExportDocument(BaseModel):
    """Portable, database-independent recipe format (ingredients by name)."""
    format: str = "nakupak-recipes"
    version: int = 1
    recipes: list[RecipeExportRecipe]


class ParseIngredientsRequest(BaseModel):
    text: str


class ParsedIngredient(BaseModel):
    name: str
    quantity: float = 1
    unit: str = "x"
    item_id: int | None = None  # existing item matched by name, if any


class ImportUrlRequest(BaseModel):
    url: str


class ImportUrlResponse(BaseModel):
    name: str
    description: str
    image_url: str | None = None
    ingredients_text: str


class RecipeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    image_url: str | None = None
    categories: RecipeCategories | None = None
    items: list[RecipeItemBase] | None = None


class RecipeItemResponse(BaseModel):
    item_id: int
    quantity: float
    unit: str = "x"
    item: ItemResponse

    class Config:
        from_attributes = True


class RecipeResponse(RecipeBase):
    id: int
    created_at: datetime
    recipe_items: list[RecipeItemResponse] = []

    class Config:
        from_attributes = True


class SessionItemBase(BaseModel):
    item_id: int | None = None
    item_name: str
    quantity: float = 1
    unit: str = "x"


class SessionItemResponse(SessionItemBase):
    id: int
    item: ItemResponse | None = None

    class Config:
        from_attributes = True


class ShoppingSessionResponse(BaseModel):
    id: int
    started_at: datetime
    completed_at: datetime | None
    session_items: list[SessionItemResponse] = []

    class Config:
        from_attributes = True


class PoolItemResponse(BaseModel):
    item: ItemResponse
    score: float
    frequency: int
    last_added: datetime | None

    class Config:
        from_attributes = True


class AddItemsRequest(BaseModel):
    items: list[ShoppingListItemCreate]


class MergeItemsRequest(BaseModel):
    source_ids: list[int]


class BulkIdsRequest(BaseModel):
    ids: list[int]


class BulkSetCategoryRequest(BaseModel):
    item_ids: list[int]
    category_id: int | None = None


class WSMessage(BaseModel):
    type: str
    data: dict
