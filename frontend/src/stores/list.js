import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { shoppingList, items as itemsApi, categories as categoriesApi, recipes as recipesApi, pool as poolApi, sessions as sessionsApi } from '../services/api'
import { nameCompare, categoryCompare } from '../utils/sort'

export const useListStore = defineStore('list', () => {
  const listItems = ref([])
  const items = ref([])
  const categories = ref([])
  const recipes = ref([])
  const poolItems = ref([])
  const sessions = ref([])

  const uncheckedGroupedByCategory = computed(() => {
    const grouped = {}
    const uncategorized = []

    for (const listItem of listItems.value) {
      if (listItem.checked) continue
      const categoryId = listItem.item?.category_id
      if (categoryId) {
        if (!grouped[categoryId]) {
          const category = categories.value.find(c => c.id === categoryId)
          grouped[categoryId] = {
            category,
            items: []
          }
        }
        grouped[categoryId].items.push(listItem)
      } else {
        uncategorized.push(listItem)
      }
    }

    const sorted = Object.values(grouped).sort((a, b) =>
      categoryCompare(a.category, b.category)
    )

    for (const group of sorted) {
      group.items.sort((a, b) => nameCompare(a.item?.name || '', b.item?.name || ''))
    }

    if (uncategorized.length > 0) {
      uncategorized.sort((a, b) => nameCompare(a.item?.name || '', b.item?.name || ''))
      sorted.push({ category: null, items: uncategorized })
    }

    return sorted
  })

  const checkedItems = computed(() => {
    return listItems.value
      .filter(li => li.checked)
      .sort((a, b) => nameCompare(a.item?.name || '', b.item?.name || ''))
  })

  // Keep groupedByCategory as alias for backwards compatibility with other views
  const groupedByCategory = uncheckedGroupedByCategory

  const itemsGroupedByCategory = computed(() => {
    const grouped = {}
    const uncategorized = []

    for (const item of items.value) {
      const categoryId = item.category_id
      if (categoryId) {
        if (!grouped[categoryId]) {
          const category = categories.value.find(c => c.id === categoryId)
          grouped[categoryId] = {
            category,
            items: []
          }
        }
        grouped[categoryId].items.push(item)
      } else {
        uncategorized.push(item)
      }
    }

    const sorted = Object.values(grouped).sort((a, b) =>
      categoryCompare(a.category, b.category)
    )

    if (uncategorized.length > 0) {
      sorted.push({ category: null, items: uncategorized })
    }

    return sorted
  })

  async function fetchList() {
    const response = await shoppingList.get()
    listItems.value = response.data
  }

  async function fetchItems() {
    const response = await itemsApi.list()
    items.value = response.data
  }

  async function fetchCategories() {
    const response = await categoriesApi.list()
    categories.value = response.data
  }

  async function reorderCategories(ids) {
    // Optimistic: apply the new order locally, then persist
    const previous = categories.value
    categories.value = ids
      .map((id, i) => ({ ...previous.find(c => c.id === id), sort_order: i }))
    try {
      await categoriesApi.reorder(ids)
    } catch (e) {
      categories.value = previous
      throw e
    }
  }

  async function fetchRecipes() {
    const response = await recipesApi.list()
    recipes.value = response.data
  }

  async function fetchPool() {
    const response = await poolApi.get()
    poolItems.value = response.data
  }

  async function fetchSessions() {
    const response = await sessionsApi.list()
    sessions.value = response.data
  }

  async function deleteSession(sessionId) {
    await sessionsApi.delete(sessionId)
    sessions.value = sessions.value.filter(s => s.id !== sessionId)
  }

  const checkedCount = computed(() =>
    listItems.value.filter(i => i.checked).length
  )

  async function toggleCheck(listItemId) {
    const item = listItems.value.find(i => i.id === listItemId)
    if (!item) return
    item.checked = !item.checked
    try {
      const response = await shoppingList.toggleCheck(listItemId)
      item.checked = response.data.checked
    } catch {
      item.checked = !item.checked
    }
  }

  async function purchaseChecked() {
    const checked = listItems.value.filter(i => i.checked)
    const count = checked.length
    if (count === 0) return 0

    listItems.value = listItems.value.filter(i => !i.checked)
    try {
      await shoppingList.purchase()
    } catch {
      await fetchList()
    }
    return count
  }

  async function addItem(itemId, quantity = 1, unit = 'x') {
    const existing = listItems.value.find(i => i.item_id === itemId)
    if (existing) {
      if (existing.unit === unit) {
        existing.quantity += quantity
      } else {
        existing.quantity = quantity
        existing.unit = unit
      }
    }

    const response = await shoppingList.add([{ item_id: itemId, quantity, unit }])

    if (existing) {
      const updated = response.data.find(i => i.item_id === itemId)
      if (updated) {
        existing.quantity = updated.quantity
        existing.unit = updated.unit
      }
    } else {
      const added = response.data.find(i => i.item_id === itemId)
      if (added) listItems.value.push(added)
    }
  }

  async function updateQuantity(listItemId, quantity, unit) {
    if (quantity <= 0) {
      await removeItem(listItemId)
    } else {
      // Optimistically update local state
      const item = listItems.value.find(i => i.id === listItemId)
      if (item) {
        item.quantity = quantity
        if (unit !== undefined) item.unit = unit
      }

      const data = { quantity }
      if (unit !== undefined) data.unit = unit
      await shoppingList.update(listItemId, data)
    }
  }

  async function removeItem(listItemId) {
    // Optimistically remove
    listItems.value = listItems.value.filter(i => i.id !== listItemId)

    await shoppingList.remove(listItemId)
  }

  async function addRecipe(recipeId, multiplier = 1) {
    await shoppingList.addRecipe(recipeId, multiplier)
    await fetchList()
  }

  async function addItems(itemsToAdd) {
    await shoppingList.add(itemsToAdd)
    await fetchList()
  }

  async function createItem(name, categoryId = null) {
    const response = await itemsApi.create({ name, category_id: categoryId })
    items.value.push(response.data)
    return response.data
  }

  async function deleteItem(id) {
    await itemsApi.delete(id)
    items.value = items.value.filter(i => i.id !== id)
    listItems.value = listItems.value.filter(li => li.item_id !== id)
  }

  async function updateItem(id, data) {
    const response = await itemsApi.update(id, data)
    const index = items.value.findIndex(i => i.id === id)
    if (index >= 0) {
      items.value[index] = response.data
    }
    // Update nested item data in listItems
    for (const li of listItems.value) {
      if (li.item_id === id) {
        li.item = response.data
      }
    }
    return response.data
  }

  async function bulkRemoveItems(ids) {
    listItems.value = listItems.value.filter(i => !ids.includes(i.id))
    await shoppingList.bulkRemove(ids)
  }

  async function clearList() {
    listItems.value = []
    await shoppingList.clear()
  }

  async function bulkDeleteItems(ids) {
    await itemsApi.bulkDelete(ids)
    items.value = items.value.filter(i => !ids.includes(i.id))
    listItems.value = listItems.value.filter(li => !ids.includes(li.item_id))
  }

  async function bulkSetCategory(ids, categoryId) {
    await itemsApi.bulkSetCategory(ids, categoryId)
    const category = categoryId ? categories.value.find(c => c.id === categoryId) : null
    for (const item of items.value) {
      if (ids.includes(item.id)) {
        item.category_id = categoryId
        item.category = category
      }
    }
    // Update nested item data in listItems
    for (const li of listItems.value) {
      if (ids.includes(li.item_id)) {
        li.item = { ...li.item, category_id: categoryId, category }
      }
    }
  }

  async function mergeItems(targetId, sourceIds) {
    const response = await itemsApi.merge(targetId, sourceIds)
    items.value = items.value.filter(i => !sourceIds.includes(i.id) || i.id === targetId)
    const index = items.value.findIndex(i => i.id === targetId)
    if (index >= 0) {
      items.value[index] = response.data
    }
    // Update listItems — entries referencing source items now reference the target
    for (const li of listItems.value) {
      if (sourceIds.includes(li.item_id)) {
        li.item_id = targetId
        li.item = response.data
      }
    }
    return response.data
  }

  return {
    listItems,
    items,
    categories,
    recipes,
    poolItems,
    sessions,
    groupedByCategory,
    uncheckedGroupedByCategory,
    checkedItems,
    itemsGroupedByCategory,
    fetchList,
    fetchItems,
    fetchCategories,
    reorderCategories,
    fetchRecipes,
    fetchPool,
    fetchSessions,
    deleteSession,
    addItem,
    updateQuantity,
    removeItem,
    addRecipe,
    addItems,
    createItem,
    deleteItem,
    updateItem,
    bulkRemoveItems,
    clearList,
    bulkDeleteItems,
    bulkSetCategory,
    mergeItems,
    checkedCount,
    toggleCheck,
    purchaseChecked,
  }
})
