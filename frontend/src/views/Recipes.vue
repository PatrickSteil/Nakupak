<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useListStore } from '../stores/list'
import { useToastStore } from '../stores/toast'
import { recipes as recipesApi } from '../services/api'
import { Pencil, Trash2, Plus, Upload, FileDown, Copy, Link } from 'lucide-vue-next'
import { marked } from 'marked'
import { normalizeForSearch } from '../utils/sort'
import PageLayout from '../components/PageLayout.vue'
import AnimatedList from '../components/AnimatedList.vue'
import RecipeModal from '../components/RecipeModal.vue'
import AddRecipeModal from '../components/AddRecipeModal.vue'
import ImportUrlModal from '../components/ImportUrlModal.vue'
import SearchBar from '../components/SearchBar.vue'
import ConfirmModal from '../components/ConfirmModal.vue'
import EmptyState from '../components/EmptyState.vue'
import ItemBadge from '../components/ItemBadge.vue'
import IconButton from '../components/IconButton.vue'
import CollectionCard from '../components/CollectionCard.vue'
import AppButton from '../components/AppButton.vue'

marked.setOptions({ breaks: true })

const { t } = useI18n()
const listStore = useListStore()
const toastStore = useToastStore()

const showModal = ref(false)
const editingRecipe = ref(null)
const expandedRecipes = ref(new Set())
const jsonInput = ref(null)
const searchQuery = ref('')
const prefill = ref(null)
const showUrlModal = ref(false)

const activeCategory = ref(null)
const addTarget = ref(null)

const allCategories = computed(() => {
  const names = new Set()
  for (const r of listStore.recipes) for (const c of r.categories || []) names.add(c)
  return [...names].sort((a, b) => a.localeCompare(b))
})

// A filter for a category that no recipe has anymore must not hide everything
watch(allCategories, (names) => {
  if (activeCategory.value && !names.includes(activeCategory.value)) activeCategory.value = null
})

function toggleCategory(name) {
  activeCategory.value = activeCategory.value === name ? null : name
}

// Match recipe name, category or any ingredient name; the category chips narrow it down further
const filteredRecipes = computed(() => {
  const q = normalizeForSearch(searchQuery.value.trim())
  return listStore.recipes.filter(r => {
    if (activeCategory.value && !(r.categories || []).includes(activeCategory.value)) return false
    if (!q) return true
    return normalizeForSearch(r.name).includes(q) ||
      (r.categories || []).some(c => normalizeForSearch(c).includes(q)) ||
      r.recipe_items?.some(pi => normalizeForSearch(pi.item?.name || '').includes(q))
  })
})

const showDeleteConfirm = ref(false)
const deleteTarget = ref(null)

onMounted(async () => {
  await Promise.all([
    listStore.fetchRecipes(),
    listStore.fetchItems(),
  ])
})

function startCreate() {
  editingRecipe.value = null
  prefill.value = null
  showModal.value = true
}

function toggleExpanded(recipeId) {
  if (expandedRecipes.value.has(recipeId)) {
    expandedRecipes.value.delete(recipeId)
  } else {
    expandedRecipes.value.add(recipeId)
  }
}

function renderMarkdown(text) {
  if (!text) return ''
  return marked(text)
}

function downloadJson(doc, filename) {
  const blob = new Blob([JSON.stringify(doc, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function exportRecipe(recipe) {
  const { data } = await recipesApi.exportOne(recipe.id)
  const slug = recipe.name.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '') || 'recipe'
  downloadJson(data, `${slug}.json`)
}

async function exportAllRecipes() {
  const { data } = await recipesApi.exportAll()
  downloadJson(data, 'nakupak-recipes.json')
}

async function handleJsonFile(event) {
  const files = Array.from(event.target.files || [])
  event.target.value = ''
  if (!files.length) return
  try {
    // Merge all selected files into one document; each file may hold the full
    // document, a list of recipes, or a single recipe
    const recipes = []
    for (const file of files) {
      const doc = JSON.parse(await file.text())
      if (Array.isArray(doc)) recipes.push(...doc)
      else if (doc && Array.isArray(doc.recipes)) recipes.push(...doc.recipes)
      else recipes.push(doc)
    }
    const { data } = await recipesApi.importJson({ recipes })
    await Promise.all([listStore.fetchRecipes(), listStore.fetchItems()])
    toastStore.show(t('recipes.importedJson', { count: data.length }))
  } catch (e) {
    toastStore.show(t('recipes.importJsonError'))
  }
}

function handleUrlImported(data) {
  showUrlModal.value = false
  editingRecipe.value = null
  prefill.value = {
    name: data.name,
    description: data.description,
    image_url: data.image_url,
    ingredientsText: data.ingredients_text,
  }
  showModal.value = true
}

async function duplicateRecipe(recipe) {
  const name = t('recipes.copyName', { name: recipe.name })
  await recipesApi.create({
    name,
    description: recipe.description,
    image_url: recipe.image_url,
    categories: recipe.categories,
    items: recipe.recipe_items.map(pi => ({ item_id: pi.item_id, quantity: pi.quantity, unit: pi.unit })),
  })
  await listStore.fetchRecipes()
  toastStore.show(t('recipes.created', { name }))
}

function startEdit(recipe) {
  editingRecipe.value = recipe
  showModal.value = true
}

async function handleSave(data) {
  const payload = {
    name: data.name,
    description: data.description,
    image_url: data.image_url,
    categories: data.categories,
    items: data.items,
  }

  if (data.id) {
    await recipesApi.update(data.id, payload)
  } else {
    await recipesApi.create(payload)
  }
  await listStore.fetchRecipes()
  showModal.value = false
}

function confirmDeleteRecipe(recipe) {
  deleteTarget.value = recipe
  showDeleteConfirm.value = true
}

async function handleDeleteConfirm() {
  await recipesApi.delete(deleteTarget.value.id)
  await listStore.fetchRecipes()
  showDeleteConfirm.value = false
  deleteTarget.value = null
}

async function addIngredientToList(pi) {
  await listStore.addItem(pi.item_id, pi.quantity, pi.unit || 'x')
  toastStore.show(t('items.addedToList'), { items: [{ name: pi.item?.name, quantity: pi.quantity }] })
}

async function addRecipeToList(recipe, count) {
  await listStore.addRecipe(recipe.id, count)
  const items = recipe.recipe_items?.map(pi => ({
    name: pi.item?.name,
    quantity: Math.round(pi.quantity * count * 1e4) / 1e4,
  })) || []
  const name = count > 1 ? `${count}× ${recipe.name}` : recipe.name
  toastStore.show(t('recipes.added', { name }), { items })
}

async function confirmAddRecipe(count) {
  const recipe = addTarget.value
  addTarget.value = null
  if (recipe) await addRecipeToList(recipe, count)
}
</script>

<template>
  <PageLayout :title="t('recipes.title')">
    <EmptyState v-if="listStore.recipes.length === 0" :title="t('recipes.emptyTitle')" :subtitle="t('recipes.emptySubtitle')" />
    <template v-else>
      <SearchBar v-model="searchQuery" :placeholder="t('recipes.searchPlaceholder')" />
      <div v-if="allCategories.length" class="flex flex-wrap gap-2 mb-4">
        <ItemBadge
          v-for="c in allCategories"
          :key="c"
          :name="c"
          clickable
          :selected="activeCategory === c"
          @click="toggleCategory(c)"
        />
      </div>
      <EmptyState v-if="filteredRecipes.length === 0" :title="t('recipes.noMatch', { query: searchQuery })" />
    </template>

    <AnimatedList :items="filteredRecipes" v-slot="{ item: recipe }">
      <CollectionCard class="mb-4" :expanded="expandedRecipes.has(recipe.id)">
        <template #header>
          <div class="flex items-center gap-3 cursor-pointer" @click="toggleExpanded(recipe.id)">
            <img v-if="recipe.image_url" :src="recipe.image_url" class="w-10 h-10 rounded-full object-cover flex-shrink-0" />
            <div class="flex-1 min-w-0">
              <h3 class="text-base font-medium text-text truncate">{{ recipe.name }}</h3>
              <p v-if="recipe.categories?.length" class="text-xs text-text-muted truncate">
                {{ recipe.categories.join(' · ') }}
              </p>
            </div>
          </div>
        </template>
        <template #actions>
          <IconButton :title="t('recipes.addToListTitle')" @click.stop="addTarget = recipe">
            <Plus class="w-5 h-5" />
          </IconButton>
          <IconButton :title="t('recipes.duplicate')" @click.stop="duplicateRecipe(recipe)">
            <Copy class="w-5 h-5" />
          </IconButton>
          <IconButton :title="t('recipes.exportJson')" @click.stop="exportRecipe(recipe)">
            <FileDown class="w-5 h-5" />
          </IconButton>
          <IconButton @click.stop="startEdit(recipe)">
            <Pencil class="w-5 h-5" />
          </IconButton>
          <IconButton @click.stop="confirmDeleteRecipe(recipe)">
            <Trash2 class="w-5 h-5" />
          </IconButton>
        </template>

        <template v-if="expandedRecipes.has(recipe.id)">
          <div v-if="recipe.image_url" class="w-full mb-3">
            <img :src="recipe.image_url" class="w-full aspect-video object-cover rounded-lg" />
          </div>
          <div
            v-if="recipe.description"
            class="w-full mb-3 text-sm text-text-secondary prose prose-sm max-w-none"
            v-html="renderMarkdown(recipe.description)"
          ></div>
          <ItemBadge
            v-for="pi in recipe.recipe_items"
            :key="pi.item_id"
            :name="pi.item?.name"
            :count="pi.quantity"
            :unit="pi.unit || 'x'"
            clickable
            @click="addIngredientToList(pi)"
          />
        </template>
      </CollectionCard>
    </AnimatedList>

    <RecipeModal
      :show="showModal"
      :edit-recipe="editingRecipe"
      :prefill="prefill"
      @close="showModal = false"
      @save="handleSave"
    />

    <AddRecipeModal
      :show="!!addTarget"
      :recipe="addTarget"
      @close="addTarget = null"
      @confirm="confirmAddRecipe"
    />

    <ImportUrlModal
      :show="showUrlModal"
      @close="showUrlModal = false"
      @imported="handleUrlImported"
    />

    <ConfirmModal
      :show="showDeleteConfirm"
      :title="t('recipes.deleteRecipe')"
      :message="t('recipes.deleteRecipeMessage', { name: deleteTarget?.name })"
      :confirm-text="t('common.delete')"
      :confirm-danger="true"
      @close="showDeleteConfirm = false"
      @confirm="handleDeleteConfirm"
    />

    <template #fab>
      <div class="flex gap-2">
        <input ref="jsonInput" type="file" multiple accept="application/json,.json" class="hidden" @change="handleJsonFile" />
        <AppButton variant="outline" fab :title="t('recipes.exportAll')" @click="exportAllRecipes">
          <FileDown class="w-4 h-4" />
        </AppButton>
        <AppButton variant="outline" fab :title="t('recipes.importJson')" @click="jsonInput.click()">
          <Upload class="w-4 h-4" />
        </AppButton>
        <AppButton variant="outline" fab :title="t('importUrl.title')" @click="showUrlModal = true">
          <Link class="w-4 h-4" />
        </AppButton>
        <AppButton fab @click="startCreate">
          {{ t('recipes.newRecipe') }}
        </AppButton>
      </div>
    </template>
  </PageLayout>
</template>
