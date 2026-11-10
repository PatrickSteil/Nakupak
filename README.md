# [Nákupák](https://nakupak.slama.dev/)

A vibecoded web app for managing my family shopping list, since I wanted something that I can
- edit from the **web** from any device,
- support **real-time updates** when multiple people add items to the list, and
- work **offline** when shopping since the store I go to doesn't have internet coverage

It's pure vibe, so proceed with caution.

## Development

### Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Deployment

The `Dockerfile` builds the frontend and serves everything (API + app) from one container on port 8000.

```bash
docker build -t nakupak .
docker run -d --name nakupak -p 8000:8000 \
  -e SECRET_KEY="$(openssl rand -hex 32)" \
  -v nakupak-data:/app/data \
  nakupak
```

- `SECRET_KEY` signs the login tokens — set a long random value and keep it stable.
- `/app/data` holds the SQLite database and uploaded recipe images — mount it as a volume or the data is lost when the container is replaced.
- Put it behind HTTPS (e.g. a reverse proxy such as Caddy or nginx). Browsers only offer "Install app" / "Add to Home Screen" over HTTPS, which is how it becomes a phone app.

## Creating households

There is no public sign-up: households can only be created by whoever runs the server.

```bash
# Docker
docker exec -it nakupak python -m backend.app.cli create-household "Family"
# Development
cd backend && uv run python -m app.cli create-household "Family"
```

The password is prompted for (or pass `--password`, which ends up in your shell history).

## Adding recipes

- **Paste ingredients**: in the recipe form, paste one ingredient per line (`2 l Milch`, `300 g Mehl`, `3 Eier`) and press *Add*. Known items are matched by name, new ones are created and get a category suggested from similar items.
- **From a web page**: paste a recipe URL; title, image, ingredients and steps are read from the page's structured data (works on most recipe sites, no AI involved).
- **JSON**: export/import recipes between instances.

Recipes can have categories (e.g. *Soup*, *Vegetarian*) that are searchable and shown as filter chips. The `+` on a recipe asks how many portions to add; all ingredient quantities are multiplied.
