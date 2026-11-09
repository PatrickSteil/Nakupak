<script setup>
import { ref, computed, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { useListStore } from '../stores/list'
import { categories as categoriesApi } from '../services/api'
import { Pencil, Trash2, ChevronUp, ChevronDown, GripVertical } from 'lucide-vue-next'
import BaseModal from './BaseModal.vue'
import CategoryModal from './CategoryModal.vue'
import ConfirmModal from './ConfirmModal.vue'
import EmptyState from './EmptyState.vue'
import IconButton from './IconButton.vue'
import AppButton from './AppButton.vue'

const { t } = useI18n()

defineProps({
  show: Boolean
})

const emit = defineEmits(['close'])

const listStore = useListStore()

const showCategoryModal = ref(false)
const editingCategory = ref(null)
const showDeleteConfirm = ref(false)
const deleteTarget = ref(null)

function startCreate() {
  editingCategory.value = null
  showCategoryModal.value = true
}

function startEdit(category) {
  editingCategory.value = category
  showCategoryModal.value = true
}

async function handleCategorySave(data) {
  if (editingCategory.value) {
    await categoriesApi.update(editingCategory.value.id, data)
  } else {
    await categoriesApi.create(data)
  }
  await listStore.fetchCategories()
  showCategoryModal.value = false
}

function confirmDelete(category) {
  deleteTarget.value = category
  showDeleteConfirm.value = true
}

async function handleDeleteConfirm() {
  await categoriesApi.delete(deleteTarget.value.id)
  await listStore.fetchCategories()
  showDeleteConfirm.value = false
  deleteTarget.value = null
}

async function move(index, delta) {
  const ids = listStore.categories.map(c => c.id)
  const target = index + delta
  if (target < 0 || target >= ids.length) return
  ;[ids[index], ids[target]] = [ids[target], ids[index]]
  await listStore.reorderCategories(ids)
}

// Drag and drop: rows reorder live while a grip is dragged (pointer events, so
// it works for mouse and touch); the new order is persisted on release.
const listEl = ref(null)
const dragOrder = ref(null)
const draggingId = ref(null)

const displayCategories = computed(() => {
  if (!dragOrder.value) return listStore.categories
  return dragOrder.value.map(id => listStore.categories.find(c => c.id === id)).filter(Boolean)
})

function startDrag(event, id) {
  event.preventDefault()
  draggingId.value = id
  dragOrder.value = listStore.categories.map(c => c.id)
  window.addEventListener('pointermove', onDragMove)
  window.addEventListener('pointerup', endDrag)
  window.addEventListener('pointercancel', cancelDrag)
}

function onDragMove(event) {
  const rows = Array.from(listEl.value?.querySelectorAll('[data-category-id]') || [])
  const order = dragOrder.value
  const from = order.indexOf(draggingId.value)
  let to = from
  rows.forEach((row, i) => {
    const rect = row.getBoundingClientRect()
    const mid = rect.top + rect.height / 2
    if (i < from && event.clientY < mid) to = Math.min(to, i)
    if (i > from && event.clientY > mid) to = Math.max(to, i)
  })
  if (to !== from) {
    const next = [...order]
    next.splice(from, 1)
    next.splice(to, 0, draggingId.value)
    dragOrder.value = next
  }
}

function removeDragListeners() {
  window.removeEventListener('pointermove', onDragMove)
  window.removeEventListener('pointerup', endDrag)
  window.removeEventListener('pointercancel', cancelDrag)
}

async function endDrag() {
  removeDragListeners()
  const ids = dragOrder.value
  const changed = ids && ids.some((id, i) => id !== listStore.categories[i]?.id)
  try {
    if (changed) await listStore.reorderCategories(ids)
  } finally {
    dragOrder.value = null
    draggingId.value = null
  }
}

function cancelDrag() {
  removeDragListeners()
  dragOrder.value = null
  draggingId.value = null
}

onBeforeUnmount(removeDragListeners)

function close() {
  emit('close')
}
</script>

<template>
  <BaseModal :show="show" :title="t('settings.categories')" @close="close">
    <p v-if="listStore.categories.length > 1" class="text-sm text-text-muted mb-3">{{ t('settings.categoryOrderHint') }}</p>
    <div ref="listEl">
    <div v-for="(category, index) in displayCategories" :key="category.id" :data-category-id="category.id" class="flex items-center gap-3 px-4 py-3 bg-surface-secondary border border-border rounded-xl mb-3"
      :class="{ 'ring-2 ring-primary shadow-lg': draggingId === category.id }">
      <span
        class="touch-none cursor-grab active:cursor-grabbing text-text-muted -ml-1"
        :title="t('settings.dragToReorder')"
        @pointerdown="startDrag($event, category.id)"
      >
        <GripVertical class="w-4 h-4" />
      </span>
      <div class="w-4 h-4 rounded-full" :style="{ background: category.color }"></div>
      <span class="flex-1 font-medium text-text">{{ category.name }}</span>
      <IconButton small :title="t('settings.moveUp')" :disabled="index === 0" :class="{ 'opacity-30': index === 0 }" @click="move(index, -1)">
        <ChevronUp class="w-4 h-4" />
      </IconButton>
      <IconButton small :title="t('settings.moveDown')" :disabled="index === listStore.categories.length - 1" :class="{ 'opacity-30': index === listStore.categories.length - 1 }" @click="move(index, 1)">
        <ChevronDown class="w-4 h-4" />
      </IconButton>
      <IconButton @click="startEdit(category)">
        <Pencil class="w-4 h-4" />
      </IconButton>
      <IconButton @click="confirmDelete(category)">
        <Trash2 class="w-4 h-4" />
      </IconButton>
    </div>
    </div>

    <EmptyState v-if="listStore.categories.length === 0" :title="t('settings.emptyCategoriesTitle')" :subtitle="t('settings.emptyCategoriesSubtitle')" />

    <template #footer>
      <AppButton variant="primary" @click="startCreate">
        {{ t('settings.addCategory') }}
      </AppButton>
    </template>

    <CategoryModal
      :show="showCategoryModal"
      :category="editingCategory"
      @close="showCategoryModal = false"
      @save="handleCategorySave"
    />

    <ConfirmModal
      :show="showDeleteConfirm"
      :title="t('settings.deleteCategory')"
      :message="t('settings.deleteCategoryMessage', { name: deleteTarget?.name })"
      :confirm-text="t('common.delete')"
      :confirm-danger="true"
      @close="showDeleteConfirm = false"
      @confirm="handleDeleteConfirm"
    />
  </BaseModal>
</template>
