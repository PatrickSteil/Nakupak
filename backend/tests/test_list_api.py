import pytest

def test_get_empty_list(authed_client):
    resp = authed_client.get("/api/list")
    assert resp.status_code == 200
    assert resp.json() == []


def test_add_item_to_list(authed_client):
    item = authed_client.post("/api/items", json={"name": "Milk"}).json()
    resp = authed_client.post("/api/list/add", json={"items": [{"item_id": item["id"], "quantity": 1}]})
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["item_id"] == item["id"]


def test_update_list_item_quantity(authed_client):
    item = authed_client.post("/api/items", json={"name": "Milk"}).json()
    added = authed_client.post("/api/list/add", json={"items": [{"item_id": item["id"], "quantity": 1}]}).json()
    resp = authed_client.put(f"/api/list/{added[0]['id']}", json={"quantity": 5})
    assert resp.status_code == 200
    assert resp.json()["quantity"] == 5


def test_remove_from_list(authed_client):
    item = authed_client.post("/api/items", json={"name": "Milk"}).json()
    added = authed_client.post("/api/list/add", json={"items": [{"item_id": item["id"], "quantity": 1}]}).json()
    resp = authed_client.delete(f"/api/list/{added[0]['id']}")
    assert resp.status_code == 200
    assert authed_client.get("/api/list").json() == []


def test_bulk_add(authed_client):
    a = authed_client.post("/api/items", json={"name": "A"}).json()
    b = authed_client.post("/api/items", json={"name": "B"}).json()
    resp = authed_client.post("/api/list/add", json={
        "items": [
            {"item_id": a["id"], "quantity": 1},
            {"item_id": b["id"], "quantity": 2},
        ]
    })
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_duplicate_quantity_aggregation(authed_client):
    item = authed_client.post("/api/items", json={"name": "Milk"}).json()
    authed_client.post("/api/list/add", json={"items": [{"item_id": item["id"], "quantity": 2}]})
    authed_client.post("/api/list/add", json={"items": [{"item_id": item["id"], "quantity": 3}]})
    list_items = authed_client.get("/api/list").json()
    assert len(list_items) == 1
    assert list_items[0]["quantity"] == 5


def test_add_recipe_to_list(authed_client):
    item = authed_client.post("/api/items", json={"name": "Flour"}).json()
    recipe = authed_client.post("/api/recipes", json={
        "name": "Pancakes",
        "items": [{"item_id": item["id"], "quantity": 2}]
    }).json()
    resp = authed_client.post(f"/api/list/add-recipe/{recipe['id']}")
    assert resp.status_code == 200
    list_items = authed_client.get("/api/list").json()
    assert len(list_items) == 1
    assert list_items[0]["quantity"] == 2
    assert list_items[0]["from_recipe_id"] == recipe["id"]


def test_add_recipe_quantity_aggregation(authed_client):
    item = authed_client.post("/api/items", json={"name": "Flour"}).json()
    authed_client.post("/api/list/add", json={"items": [{"item_id": item["id"], "quantity": 1}]})
    recipe = authed_client.post("/api/recipes", json={
        "name": "Pancakes",
        "items": [{"item_id": item["id"], "quantity": 2}]
    }).json()
    authed_client.post(f"/api/list/add-recipe/{recipe['id']}")
    list_items = authed_client.get("/api/list").json()
    assert len(list_items) == 1
    assert list_items[0]["quantity"] == 3


def test_add_recipe_404(authed_client):
    resp = authed_client.post("/api/list/add-recipe/9999")
    assert resp.status_code == 404


def test_update_nonexistent_list_item(authed_client):
    resp = authed_client.put("/api/list/9999", json={"quantity": 1})
    assert resp.status_code == 404


def test_bulk_remove_from_list(authed_client):
    a = authed_client.post("/api/items", json={"name": "A"}).json()
    b = authed_client.post("/api/items", json={"name": "B"}).json()
    c = authed_client.post("/api/items", json={"name": "C"}).json()
    added = authed_client.post("/api/list/add", json={
        "items": [
            {"item_id": a["id"], "quantity": 1},
            {"item_id": b["id"], "quantity": 1},
            {"item_id": c["id"], "quantity": 1},
        ]
    }).json()
    ids_to_remove = [added[0]["id"], added[1]["id"]]
    resp = authed_client.post("/api/list/remove", json={"ids": ids_to_remove})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["deleted"] == 2
    remaining = authed_client.get("/api/list").json()
    assert len(remaining) == 1
    assert remaining[0]["item_id"] == c["id"]


def test_bulk_remove_empty_ids(authed_client):
    resp = authed_client.post("/api/list/remove", json={"ids": []})
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 0


def test_clear_list(authed_client):
    a = authed_client.post("/api/items", json={"name": "A"}).json()
    b = authed_client.post("/api/items", json={"name": "B"}).json()
    authed_client.post("/api/list/add", json={
        "items": [
            {"item_id": a["id"], "quantity": 1},
            {"item_id": b["id"], "quantity": 2},
        ]
    })
    resp = authed_client.delete("/api/list")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["deleted"] == 2
    assert authed_client.get("/api/list").json() == []


def test_clear_empty_list(authed_client):
    resp = authed_client.delete("/api/list")
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 0


def test_list_household_isolation(client, household, second_household, auth_headers, second_auth_headers):
    item = client.post("/api/items", json={"name": "Milk"}, headers=auth_headers).json()
    client.post("/api/list/add", json={"items": [{"item_id": item["id"], "quantity": 1}]}, headers=auth_headers)
    resp1 = client.get("/api/list", headers=auth_headers)
    resp2 = client.get("/api/list", headers=second_auth_headers)
    assert len(resp1.json()) == 1
    assert len(resp2.json()) == 0


def test_add_recipe_with_multiplier(authed_client):
    item = authed_client.post("/api/items", json={"name": "Leek"}).json()
    recipe = authed_client.post("/api/recipes", json={
        "name": "Leek soup",
        "items": [{"item_id": item["id"], "quantity": 2}]
    }).json()
    resp = authed_client.post(f"/api/list/add-recipe/{recipe['id']}?multiplier=3")
    assert resp.status_code == 200
    assert authed_client.get("/api/list").json()[0]["quantity"] == 6
    # adding again aggregates onto the existing entry
    authed_client.post(f"/api/list/add-recipe/{recipe['id']}?multiplier=2")
    assert authed_client.get("/api/list").json()[0]["quantity"] == 10


@pytest.mark.parametrize("bad", ["0", "-1", "101", "abc"])
def test_add_recipe_rejects_bad_multiplier(authed_client, bad):
    recipe = authed_client.post("/api/recipes", json={"name": "Soup"}).json()
    resp = authed_client.post(f"/api/list/add-recipe/{recipe['id']}?multiplier={bad}")
    assert resp.status_code == 422
