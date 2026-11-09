<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useListStore } from '../stores/list'
import { categories as categoriesApi } from '../services/api'
import { Pencil, Trash2, ChevronUp, ChevronDown } from 'lucide-vue-next'
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

function close() {
  emit('close')
}
</script>

<template>
  <BaseModal :show="show" :title="t('settings.categories')" @close="close">
    <p v-if="listStore.categories.length > 1" class="text-sm text-text-muted mb-3">{{ t('settings.categoryOrderHint') }}</p>
    <div v-for="(category, index) in listStore.categories" :key="category.id" class="flex items-center gap-3 px-4 py-3 bg-surface-secondary border border-border rounded-xl mb-3">
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
