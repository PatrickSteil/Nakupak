def test_list_recipes_empty(authed_client):
    resp = authed_client.get("/api/recipes")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_recipe_without_items(authed_client):
    resp = authed_client.post("/api/recipes", json={"name": "Pancakes"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Pancakes"
    assert data["recipe_items"] == []


def test_create_recipe_with_items(authed_client):
    item = authed_client.post("/api/items", json={"name": "Flour"}).json()
    resp = authed_client.post("/api/recipes", json={
        "name": "Pancakes",
        "items": [{"item_id": item["id"], "quantity": 2}]
    })
    assert resp.status_code == 200
    assert len(resp.json()["recipe_items"]) == 1
    assert resp.json()["recipe_items"][0]["quantity"] == 2


def test_update_recipe_name(authed_client):
    recipe = authed_client.post("/api/recipes", json={"name": "Pancakes"}).json()
    resp = authed_client.put(f"/api/recipes/{recipe['id']}", json={"name": "Waffles"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Waffles"


def test_update_recipe_replaces_items(authed_client):
    item_a = authed_client.post("/api/items", json={"name": "A"}).json()
    item_b = authed_client.post("/api/items", json={"name": "B"}).json()
    recipe = authed_client.post("/api/recipes", json={
        "name": "R1",
        "items": [{"item_id": item_a["id"], "quantity": 1}]
    }).json()
    resp = authed_client.put(f"/api/recipes/{recipe['id']}", json={
        "items": [{"item_id": item_b["id"], "quantity": 3}]
    })
    assert resp.status_code == 200
    ri = resp.json()["recipe_items"]
    assert len(ri) == 1
    assert ri[0]["item_id"] == item_b["id"]
    assert ri[0]["quantity"] == 3


def test_update_recipe_items_none_preserves(authed_client):
    item = authed_client.post("/api/items", json={"name": "A"}).json()
    recipe = authed_client.post("/api/recipes", json={
        "name": "R1",
        "items": [{"item_id": item["id"], "quantity": 1}]
    }).json()
    resp = authed_client.put(f"/api/recipes/{recipe['id']}", json={"name": "R1 Updated"})
    assert len(resp.json()["recipe_items"]) == 1


def test_delete_recipe(authed_client):
    recipe = authed_client.post("/api/recipes", json={"name": "R1"}).json()
    resp = authed_client.delete(f"/api/recipes/{recipe['id']}")
    assert resp.status_code == 200
    assert authed_client.get("/api/recipes").json() == []


def test_recipes_sorted_by_name(authed_client):
    authed_client.post("/api/recipes", json={"name": "Zebra"})
    authed_client.post("/api/recipes", json={"name": "Apple"})
    authed_client.post("/api/recipes", json={"name": "Mango"})
    names = [r["name"] for r in authed_client.get("/api/recipes").json()]
    assert names == ["Apple", "Mango", "Zebra"]


def test_delete_nonexistent_recipe(authed_client):
    resp = authed_client.delete("/api/recipes/9999")
    assert resp.status_code == 404


def test_update_nonexistent_recipe(authed_client):
    resp = authed_client.put("/api/recipes/9999", json={"name": "Nope"})
    assert resp.status_code == 404


def test_recipe_household_isolation(client, household, second_household, auth_headers, second_auth_headers):
    client.post("/api/recipes", json={"name": "H1 Recipe"}, headers=auth_headers)
    assert len(client.get("/api/recipes", headers=auth_headers).json()) == 1
    assert len(client.get("/api/recipes", headers=second_auth_headers).json()) == 0


def test_upload_image_uses_extension_from_content_type(authed_client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.routers.recipes._uploads_dir", tmp_path)
    resp = authed_client.post(
        "/api/recipes/upload-image",
        files={"file": ("evil.html", b"<script>alert(1)</script>", "image/png")},
    )
    assert resp.status_code == 200
    assert resp.json()["image_url"].endswith(".png")
    assert [p.suffix for p in tmp_path.iterdir()] == [".png"]


def test_upload_image_rejects_svg(authed_client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.routers.recipes._uploads_dir", tmp_path)
    resp = authed_client.post(
        "/api/recipes/upload-image",
        files={"file": ("x.svg", b"<svg onload='alert(1)'/>", "image/svg+xml")},
    )
    assert resp.status_code == 400
    assert list(tmp_path.iterdir()) == []


def _make_recipe(c):
    cat = c.post("/api/categories", json={"name": "Dairy"}).json()
    milk = c.post("/api/items", json={"name": "Milk", "category_id": cat["id"]}).json()
    flour = c.post("/api/items", json={"name": "Flour"}).json()
    return c.post("/api/recipes", json={
        "name": "Pancakes", "description": "Tasty",
        "items": [
            {"item_id": milk["id"], "quantity": 2, "unit": "l"},
            {"item_id": flour["id"], "quantity": 300, "unit": "g"},
        ],
    }).json()


def test_export_all_and_single(authed_client):
    recipe = _make_recipe(authed_client)
    doc = authed_client.get("/api/recipes/export").json()
    assert doc["format"] == "nakupak-recipes" and doc["version"] == 1
    assert len(doc["recipes"]) == 1
    ings = {i["name"]: i for i in doc["recipes"][0]["ingredients"]}
    assert ings["Milk"] == {"name": "Milk", "quantity": 2, "unit": "l", "category": "Dairy"}
    assert ings["Flour"]["category"] is None
    single = authed_client.get(f"/api/recipes/{recipe['id']}/export").json()
    assert single["recipes"] == doc["recipes"]
    assert authed_client.get("/api/recipes/9999/export").status_code == 404


def test_import_json_roundtrip_creates_items_and_categories(authed_client):
    _make_recipe(authed_client)
    doc = authed_client.get("/api/recipes/export").json()
    # simulate another database: import into fresh state by deleting everything
    for r in authed_client.get("/api/recipes").json():
        authed_client.delete(f"/api/recipes/{r['id']}")
    for i in authed_client.get("/api/items").json():
        authed_client.delete(f"/api/items/{i['id']}")
    for c in authed_client.get("/api/categories").json():
        authed_client.delete(f"/api/categories/{c['id']}")

    resp = authed_client.post("/api/recipes/import-json", json=doc)
    assert resp.status_code == 200
    created = resp.json()
    assert len(created) == 1 and created[0]["name"] == "Pancakes"
    by_name = {ri["item"]["name"]: ri for ri in created[0]["recipe_items"]}
    assert by_name["Milk"]["quantity"] == 2 and by_name["Milk"]["unit"] == "l"
    assert by_name["Milk"]["item"]["category"]["name"] == "Dairy"
    assert len(authed_client.get("/api/categories").json()) == 1


def test_import_json_reuses_existing_items(authed_client):
    _make_recipe(authed_client)
    doc = authed_client.get("/api/recipes/export").json()
    doc["recipes"][0]["ingredients"][0]["name"] = doc["recipes"][0]["ingredients"][0]["name"].upper()
    authed_client.post("/api/recipes/import-json", json=doc)
    assert len(authed_client.get("/api/items").json()) == 2
    assert len(authed_client.get("/api/recipes").json()) == 2


def test_import_json_rejects_wrong_format(authed_client):
    resp = authed_client.post("/api/recipes/import-json", json={"format": "other", "recipes": []})
    assert resp.status_code == 400
