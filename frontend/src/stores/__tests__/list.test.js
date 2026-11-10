import { setActivePinia, createPinia } from 'pinia'
import { useListStore } from '../list'
import { vi } from 'vitest'

vi.mock('../../services/api', () => ({
  shoppingList: {
    get: vi.fn(),
    add: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    addRecipe: vi.fn(),
  },
  items: { list: vi.fn(), create: vi.fn(), delete: vi.fn(), update: vi.fn(), merge: vi.fn() },
  categories: { list: vi.fn(), reorder: vi.fn() },
  recipes: { list: vi.fn() },
  pool: { get: vi.fn() },
  sessions: { list: vi.fn(), delete: vi.fn() },
}))

import { shoppingList, categories as categoriesApi } from '../../services/api'

describe('list store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('groupedByCategory', () => {
    it('returns empty array for empty list', () => {
      const store = useListStore()
      expect(store.groupedByCategory).toEqual([])
    })

    it('groups items by category id', () => {
      const store = useListStore()
      store.categories = [{ id: 1, name: 'Dairy' }]
      store.listItems = [
        { id: 10, item: { category_id: 1, name: 'Milk' }, quantity: 1 },
        { id: 11, item: { category_id: 1, name: 'Cheese' }, quantity: 1 },
      ]
      const groups = store.groupedByCategory
      expect(groups).toHaveLength(1)
      expect(groups[0].items).toHaveLength(2)
    })

    it('orders groups by category sort_order, not name', () => {
      const store = useListStore()
      store.categories = [
        { id: 1, name: 'Water', sort_order: 2 },
        { id: 2, name: 'Fruit', sort_order: 0 },
        { id: 3, name: 'Frozen', sort_order: 1 },
      ]
      store.listItems = [
        { id: 10, item: { category_id: 1, name: 'Sparkling' }, quantity: 1 },
        { id: 11, item: { category_id: 3, name: 'Peas' }, quantity: 1 },
        { id: 12, item: { category_id: 2, name: 'Apple' }, quantity: 1 },
      ]
      expect(store.groupedByCategory.map(g => g.category.name)).toEqual(['Fruit', 'Frozen', 'Water'])
    })

    it('reorderCategories updates order locally and persists it', async () => {
      const store = useListStore()
      store.categories = [{ id: 1, name: 'A', sort_order: 0 }, { id: 2, name: 'B', sort_order: 1 }]
      categoriesApi.reorder.mockResolvedValue({})
      await store.reorderCategories([2, 1])
      expect(store.categories.map(c => c.id)).toEqual([2, 1])
      expect(categoriesApi.reorder).toHaveBeenCalledWith([2, 1])
    })

    it('puts uncategorized items last', () => {
      const store = useListStore()
      store.categories = [{ id: 1, name: 'Dairy' }]
      store.listItems = [
        { id: 10, item: { category_id: 1, name: 'Milk' }, quantity: 1 },
        { id: 11, item: { category_id: null, name: 'Random' }, quantity: 1 },
      ]
      const groups = store.groupedByCategory
      expect(groups).toHaveLength(2)
      expect(groups[1].category).toBeNull()
    })

    it('sorts groups by category name', () => {
      const store = useListStore()
      store.categories = [
        { id: 1, name: 'Zebra' },
        { id: 2, name: 'Apple' },
      ]
      store.listItems = [
        { id: 10, item: { category_id: 1, name: 'Z Item' }, quantity: 1 },
        { id: 11, item: { category_id: 2, name: 'A Item' }, quantity: 1 },
      ]
      const groups = store.groupedByCategory
      expect(groups[0].category.name).toBe('Apple')
      expect(groups[1].category.name).toBe('Zebra')
    })

    it('handles emoji in category names for sorting', () => {
      const store = useListStore()
      store.categories = [
        { id: 1, name: '🥛 Dairy' },
        { id: 2, name: 'Bakery' },
      ]
      store.listItems = [
        { id: 10, item: { category_id: 1, name: 'Milk' }, quantity: 1 },
        { id: 11, item: { category_id: 2, name: 'Bread' }, quantity: 1 },
      ]
      const groups = store.groupedByCategory
      expect(groups[0].category.name).toBe('Bakery')
      expect(groups[1].category.name).toBe('🥛 Dairy')
    })
  })

  describe('optimistic updates', () => {
    it('updateQuantity optimistically updates local state', async () => {
      shoppingList.update.mockResolvedValue({ data: {} })
      const store = useListStore()
      store.listItems = [{ id: 10, item: { name: 'Milk' }, quantity: 1 }]
      const promise = store.updateQuantity(10, 5)
      expect(store.listItems[0].quantity).toBe(5)
      await promise
    })

    it('removeItem optimistically removes from list', async () => {
      shoppingList.remove.mockResolvedValue({ data: {} })
      const store = useListStore()
      store.listItems = [{ id: 10, item: { name: 'Milk' }, quantity: 1 }]
      const promise = store.removeItem(10)
      expect(store.listItems).toHaveLength(0)
      await promise
    })
  })

  describe('addRecipe', () => {
    it('passes the multiplier to the API and defaults to 1', async () => {
      shoppingList.addRecipe.mockResolvedValue({ data: [] })
      shoppingList.get.mockResolvedValue({ data: [] })
      const store = useListStore()
      await store.addRecipe(7, 3)
      expect(shoppingList.addRecipe).toHaveBeenLastCalledWith(7, 3)
      await store.addRecipe(7)
      expect(shoppingList.addRecipe).toHaveBeenLastCalledWith(7, 1)
    })
  })
})
