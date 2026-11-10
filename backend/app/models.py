from sqlalchemy import Column, Integer, Float, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class Household(Base):
    __tablename__ = "households"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False, server_default="")
    created_at = Column(DateTime, server_default=func.now())

    categories = relationship("Category", back_populates="household")
    items = relationship("Item", back_populates="household")
    shopping_list_items = relationship("ShoppingListItem", back_populates="household")
    recipes = relationship("Recipe", back_populates="household")
    shopping_sessions = relationship("ShoppingSession", back_populates="household")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    sort_order = Column(Integer, default=0)
    color = Column(String, default="#6b7280")
    household_id = Column(Integer, ForeignKey("households.id"), nullable=False)

    household = relationship("Household", back_populates="categories")
    items = relationship("Item", back_populates="category")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    household_id = Column(Integer, ForeignKey("households.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    household = relationship("Household", back_populates="items")
    category = relationship("Category", back_populates="items")
    shopping_list_items = relationship("ShoppingListItem", back_populates="item", cascade="all, delete-orphan")
    recipe_items = relationship("RecipeItem", back_populates="item", cascade="all, delete-orphan")
    session_items = relationship("SessionItem", back_populates="item")


class ShoppingListItem(Base):
    __tablename__ = "shopping_list_items"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    quantity = Column(Float, default=1)
    unit = Column(String, default="x")
    added_at = Column(DateTime, server_default=func.now())
    checked = Column(Boolean, default=False)
    from_recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=True)
    household_id = Column(Integer, ForeignKey("households.id"), nullable=False)

    household = relationship("Household", back_populates="shopping_list_items")
    item = relationship("Item", back_populates="shopping_list_items")
    from_recipe = relationship("Recipe")


class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    categories = Column(JSON, nullable=False, default=list, server_default="[]")
    household_id = Column(Integer, ForeignKey("households.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    household = relationship("Household", back_populates="recipes")
    recipe_items = relationship("RecipeItem", back_populates="recipe", cascade="all, delete-orphan")


class RecipeItem(Base):
    __tablename__ = "recipe_items"

    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    quantity = Column(Float, default=1)
    unit = Column(String, default="x")

    recipe = relationship("Recipe", back_populates="recipe_items")
    item = relationship("Item", back_populates="recipe_items")


class ShoppingSession(Base):
    __tablename__ = "shopping_sessions"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
    household_id = Column(Integer, ForeignKey("households.id"), nullable=False)

    household = relationship("Household", back_populates="shopping_sessions")
    session_items = relationship("SessionItem", back_populates="session", cascade="all, delete-orphan")


class SessionItem(Base):
    __tablename__ = "session_items"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("shopping_sessions.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="SET NULL"), nullable=True)
    item_name = Column(String, nullable=False)
    quantity = Column(Float, default=1)
    unit = Column(String, default="x")
    checked = Column(Boolean, default=False)
    checked_at = Column(DateTime, nullable=True)

    session = relationship("ShoppingSession", back_populates="session_items")
    item = relationship("Item", back_populates="session_items")
