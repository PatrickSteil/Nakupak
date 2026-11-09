<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useListStore } from '../stores/list'
import { useToastStore } from '../stores/toast'
import { nameCompare, categoryCompare, normalizeForSearch } from '../utils/sort'
import { recipes as recipesApi } from '../services/api'
import { Pencil, Trash2, Plus, ListPlus, Tag, Merge, CookingPot, X } from 'lucide-vue-next'
import { Motion, AnimatePresence } from 'motion-v'
import PageLayout from '../components/PageLayout.vue'
import AnimatedCategoryList from '../components/AnimatedCategoryList.vue'
import ItemRow from '../components/ItemRow.vue'
import RecipeModal from '../components/RecipeModal.vue'
import ConfirmModal from '../components/ConfirmModal.vue'
import ItemModal from '../components/ItemModal.vue'
import BaseModal from '../components/BaseModal.vue'
import AppButton from '../components/AppButton.vue'
import EmptyState from '../components/EmptyState.vue'
import SearchBar from '../components/SearchBar.vue'
import IconButton from '../components/IconButton.vue'

const { t } = useI18n()
const listStore = useListStore()
const toastStore = useToastStore()

const searchQuery = ref('')
const selectedIds = ref(new Set())

// Item edit modal
const showItemModal = ref(false)
const editingItem = ref(null)

// Category modal for bulk action
const showCategoryModal = ref(false)
const bulkCategoryId = ref(null)

// Confirm modals
const showDeleteConfirm = ref(false)
const deleteTarget = ref(null)

const showBulkDeleteConfirm = ref(false)

const showMergeConfirm = ref(false)

// Recipe modal
const showRecipeModal = ref(false)

onMounted(async () => {
  await Promise.all([
    listStore.fetchItems(),
    listStore.fetchCategories(),
  ])
})

const allGroupedItems = computed(() => {
  const grouped = {}
  const uncategorized = []

  for (const item of listStore.items) {
    const categoryId = item.category_id
    if (categoryId) {
      if (!grouped[categoryId]) {
        const category = listStore.categories.find(c => c.id === categoryId)
        grouped[categoryId] = { category, items: [] }
      }
      grouped[categoryId].items.push(item)
    } else {
      uncategorized.push(item)
    }
  }

  const sorted = Object.values(grouped).sort((a, b) =>
    categoryCompare(a.category, b.category)
  )

  for (const group of sorted) {
    group.items.sort((a, b) => nameCompare(a.name || '', b.name || ''))
  }

  if (uncategorized.length > 0) {
    uncategorized.sort((a, b) => nameCompare(a.name || '', b.name || ''))
    sorted.push({ category: null, items: uncategorized })
  }

  const query = normalizeForSearch(searchQuery.value)
  if (query) {
    for (const group of sorted) {
      const matching = group.items.filter(i => normalizeForSearch(i.name).includes(query))
      const nonMatching = group.items.filter(i => !normalizeForSearch(i.name).includes(query))
      group.items = [...matching, ...nonMatching]
    }
  }

  return sorted
})

const matchingIds = computed(() => {
  const query = normalizeForSearch(searchQuery.value)
  if (!query) return null
  return new Set(
    listStore.items
      .filter(item => normalizeForSearch(item.name).includes(query))
      .map(item => item.id)
  )
})

function isMatching(itemId) {
  return !matchingIds.value || matchingIds.value.has(itemId)
}

const hasAnyMatch = computed(() => {
  return !matchingIds.value || matchingIds.value.size > 0
})

const selectedCount = computed(() => selectedIds.value.size)

function toggleSelect(itemId) {
  if (selectedIds.value.has(itemId)) {
    selectedIds.value.delete(itemId)
  } else {
    selectedIds.value.add(itemId)
  }
  selectedIds.value = new Set(selectedIds.value)
}

function clearSelection() {
  selectedIds.value = new Set()
}

function startEdit(item) {
  editingItem.value = item
  showItemModal.value = true
}

async function handleItemSave(data) {
  await listStore.updateItem(editingItem.value.id, data)
  showItemModal.value = false
  editingItem.value = null
}

function confirmDeleteItem(item) {
  deleteTarget.value = item
  showDeleteConfirm.value = true
}

async function handleDeleteConfirm() {
  const name = deleteTarget.value.name
  const category = getCategoryForItem(deleteTarget.value)
  await listStore.deleteItem(deleteTarget.value.id)
  selectedIds.value.delete(deleteTarget.value.id)
  selectedIds.value = new Set(selectedIds.value)
  showDeleteConfirm.value = false
  deleteTarget.value = null
  toastStore.show(t('toast.deleted', { name }), { category })
}

function confirmBulkDelete() {
  showBulkDeleteConfirm.value = true
}

async function handleBulkDeleteConfirm() {
  const count = selectedIds.value.size
  await listStore.bulkDeleteItems(Array.from(selectedIds.value))
  clearSelection()
  showBulkDeleteConfirm.value = false
  toastStore.show(t('toast.deletedCount', { count }))
}

function openCategoryModal() {
  bulkCategoryId.value = null
  showCategoryModal.value = true
}

async function applyBulkCategory() {
  const count = selectedIds.value.size
  const category = listStore.categories.find(c => c.id === bulkCategoryId.value)
  await listStore.bulkSetCategory(Array.from(selectedIds.value), bulkCategoryId.value)
  showCategoryModal.value = false
  clearSelection()
  toastStore.show(t('toast.updatedCount', { count }), { category })
}

function confirmMerge() {
  showMergeConfirm.value = true
}

async function handleMergeConfirm() {
  const ids = Array.from(selectedIds.value)
  const targetId = ids[0]
  const targetItem = listStore.items.find(i => i.id === targetId)
  const targetName = targetItem?.name || ''
  const category = getCategoryForItem(targetItem)
  const count = ids.length
  await listStore.mergeItems(targetId, ids)
  clearSelection()
  showMergeConfirm.value = false
  toastStore.show(t('toast.mergedItems', { count, name: targetName }), { category })
}

function openRecipeModal() {
  showRecipeModal.value = true
}

async function handleRecipeSave(data) {
  await recipesApi.create({
    name: data.name,
    color: data.color,
    items: data.items,
  })
  await listStore.fetchRecipes()
  showRecipeModal.value = false
  clearSelection()
  toastStore.show(t('recipes.created', { name: data.name }))
}

async function addToList(item) {
  await listStore.addItem(item.id)
  toastStore.show(t('items.addedToList'), { items: [{ name: item.name, quantity: 1 }] })
}

async function addSelectedToList() {
  const items = Array.from(selectedIds.value)
    .map(id => listStore.items.find(i => i.id === id))
    .filter(Boolean)
  await listStore.addItems(items.map(i => ({ item_id: i.id, quantity: 1 })))
  toastStore.show(t('items.addedToList'), { items: items.map(i => ({ name: i.name, quantity: 1 })) })
  clearSelection()
}

function getCategoryForItem(item) {
  if (!item.category_id) return null
  return listStore.categories.find(c => c.id === item.category_id)
}

const mergeTargetName = computed(() => {
  const ids = Array.from(selectedIds.value)
  if (ids.length < 2) return ''
  const targetItem = listStore.items.find(i => i.id === ids[0])
  return targetItem?.name || ''
})
</script>

<template>
  <PageLayout :title="t('items.title')">
    <template #default>
      <SearchBar v-model="searchQuery" :placeholder="t('items.searchPlaceholder')" />

      <EmptyState v-if="!hasAnyMatch && searchQuery" :title="t('items.noMatch', { query: searchQuery })" />
      <EmptyState v-else-if="listStore.items.length === 0" :title="t('items.emptyTitle')" :subtitle="t('items.emptySubtitle')" />

      <AnimatedCategoryList :groups="allGroupedItems" v-slot="{ group }">
        <TransitionGroup name="item-reorder" tag="div">
        <div
          v-for="item in group.items"
          :key="item.id"
          class="transition-opacity duration-200"
          :class="{ 'opacity-40': !isMatching(item.id) }"
        >
          <ItemRow
            :name="item.name"
            :accent-color="group.category?.color"
            :checked="selectedIds.has(item.id)"
            :clickable="true"
            @click="toggleSelect(item.id)"
            @toggle-check="toggleSelect(item.id)"
          >
            <template #actions>
              <div class="flex items-center gap-1">
                <IconButton small @click.stop="addToList(item)">
                  <Plus class="w-4 h-4" />
                </IconButton>
                <IconButton small @click.stop="startEdit(item)">
                  <Pencil class="w-4 h-4" />
                </IconButton>
                <IconButton small @click.stop="confirmDeleteItem(item)">
                  <Trash2 class="w-4 h-4" />
                </IconButton>
              </div>
            </template>
          </ItemRow>
        </div>
        </TransitionGroup>
      </AnimatedCategoryList>

      <AnimatePresence>
      <Motion
        v-if="selectedCount > 0"
        :initial="{ opacity: 0, y: 20, scale: 0.95 }"
        :animate="{ opacity: 1, y: 0, scale: 1 }"
        :exit="{ opacity: 0, y: 20, scale: 0.95 }"
        :transition="{ duration: 0.2, ease: 'easeOut' }"
        class="fixed bottom-24 left-1/2 -translate-x-1/2 max-w-[90vw] bg-surface-secondary opacity-90 border border-border rounded-xl p-3 z-40 shadow-lg"
      >
        <div class="flex items-center gap-1 overflow-hidden">
          <button
            class="flex items-center gap-1.5 px-2.5 py-1.5 bg-primary text-white rounded-lg text-sm font-medium hover:opacity-90 overflow-hidden min-w-0"
            @click="addSelectedToList"
          >
            <Plus class="w-4 h-4 shrink-0" />
            <span class="hidden min-[340px]:inline truncate">{{ t('items.add') }}</span>
          </button>
          <button
            class="flex items-center gap-1.5 px-2.5 py-1.5 bg-danger text-white rounded-lg text-sm font-medium hover:opacity-90 overflow-hidden min-w-0"
            @click="confirmBulkDelete"
          >
            <Trash2 class="w-4 h-4 shrink-0" />
            <span class="hidden min-[340px]:inline truncate">{{ t('items.delete') }}</span>
          </button>
          <button
            class="flex items-center gap-1.5 px-2.5 py-1.5 bg-surface text-text rounded-lg text-sm font-medium hover:opacity-80 border border-border overflow-hidden min-w-0"
            @click="openCategoryModal"
          >
            <Tag class="w-4 h-4 shrink-0" />
            <span class="hidden min-[340px]:inline truncate">{{ t('items.category') }}</span>
          </button>
          <AnimatePresence>
          <Motion
            v-if="selectedCount >= 2"
            tag="button"
            :initial="{ opacity: 0, width: '0px', padding: '0px' }"
            :animate="{ opacity: 1, width: 'auto', paddingLeft: '10px', paddingRight: '10px', paddingTop: '6px', paddingBottom: '6px' }"
            :exit="{ opacity: 0, width: '0px', padding: '0px' }"
            :transition="{ duration: 0.15, ease: 'easeOut' }"
            class="flex items-center gap-1.5 bg-surface text-text rounded-lg text-sm font-medium hover:opacity-80 border border-border overflow-hidden whitespace-nowrap min-w-0"
            @click="confirmMerge"
          >
            <Merge class="w-4 h-4 shrink-0" />
            <span class="hidden min-[340px]:inline truncate">{{ t('items.merge') }}</span>
          </Motion>
          </AnimatePresence>
          <button
            class="flex items-center gap-1.5 px-2.5 py-1.5 bg-surface text-text rounded-lg text-sm font-medium hover:opacity-80 border border-border overflow-hidden min-w-0"
            @click="openRecipeModal"
          >
            <CookingPot class="w-4 h-4 shrink-0" />
            <span class="hidden min-[340px]:inline truncate">{{ t('items.recipe') }}</span>
          </button>
          <button @click="clearSelection" class="p-2 text-text-muted hover:text-text">
            <X class="w-4 h-4" />
          </button>
        </div>
      </Motion>
      </AnimatePresence>

      <!-- Item Edit Modal -->
      <ItemModal
        :show="showItemModal"
        :item="editingItem"
        @close="showItemModal = false"
        @save="handleItemSave"
      />

      <!-- Single Delete Confirm -->
      <ConfirmModal
        :show="showDeleteConfirm"
        :title="t('items.deleteItem')"
        :message="t('items.deleteItemMessage', { name: deleteTarget?.name })"
        :confirm-text="t('common.delete')"
        :confirm-danger="true"
        @close="showDeleteConfirm = false"
        @confirm="handleDeleteConfirm"
      />

      <!-- Bulk Delete Confirm -->
      <ConfirmModal
        :show="showBulkDeleteConfirm"
        :title="t('items.deleteItems')"
        :message="t('items.deleteItemsMessage', { count: selectedCount })"
        :confirm-text="t('common.delete')"
        :confirm-danger="true"
        @close="showBulkDeleteConfirm = false"
        @confirm="handleBulkDeleteConfirm"
      />

      <!-- Merge Confirm -->
      <ConfirmModal
        :show="showMergeConfirm"
        :title="t('items.mergeItems')"
        :message="t('items.mergeItemsMessage', { count: selectedCount, name: mergeTargetName })"
        :confirm-text="t('items.merge')"
        @close="showMergeConfirm = false"
        @confirm="handleMergeConfirm"
      />

      <!-- Category Modal -->
      <BaseModal :show="showCategoryModal" :title="t('items.setCategory')" @close="showCategoryModal = false">
        <select
          v-model="bulkCategoryId"
          class="w-full px-4 py-3 border border-border rounded-lg text-base bg-surface text-text focus:outline-none focus:border-primary"
        >
          <option :value="null">{{ t('items.noCategory') }}</option>
          <option v-for="cat in listStore.categories" :key="cat.id" :value="cat.id">
            {{ cat.name }}
          </option>
        </select>

        <template #footer>
          <AppButton variant="secondary" @click="showCategoryModal = false">
            {{ t('common.cancel') }}
          </AppButton>
          <AppButton @click="applyBulkCategory">
            {{ t('items.apply') }}
          </AppButton>
        </template>
      </BaseModal>

      <RecipeModal
        :show="showRecipeModal"
        :preselected-item-ids="Array.from(selectedIds)"
        @close="showRecipeModal = false"
        @save="handleRecipeSave"
      />
    </template>
  </PageLayout>
</template>

<style scoped>
.item-reorder-move {
  transition: transform 0.3s ease;
}
</style>
