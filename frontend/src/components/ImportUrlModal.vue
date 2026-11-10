<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { recipes as recipesApi } from '../services/api'
import BaseModal from './BaseModal.vue'
import AppButton from './AppButton.vue'
import { Loader2 } from 'lucide-vue-next'

const { t } = useI18n()

defineProps({ show: Boolean })
const emit = defineEmits(['close', 'imported'])

const url = ref('')
const loading = ref(false)
const error = ref('')

function close() {
  url.value = ''
  error.value = ''
  emit('close')
}

async function submit() {
  if (!url.value.trim() || loading.value) return
  error.value = ''
  loading.value = true
  try {
    const { data } = await recipesApi.importUrl(url.value.trim())
    emit('imported', data)
    url.value = ''
  } catch (e) {
    error.value = e.response?.status === 422 ? t('importUrl.notFound') : t('importUrl.error')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <BaseModal :show="show" :title="t('importUrl.title')" @close="close">
    <p class="mb-3 text-sm text-text-secondary">{{ t('importUrl.hint') }}</p>
    <input
      v-model="url"
      type="url"
      :placeholder="t('importUrl.placeholder')"
      class="w-full px-4 py-3 border border-border rounded-lg text-base bg-surface text-text focus:outline-none focus:border-primary"
      @keydown.enter="submit"
    />

    <div v-if="error" class="mt-4 p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm">
      {{ error }}
    </div>

    <div v-if="loading" class="flex items-center justify-center gap-2 py-4 text-text-secondary">
      <Loader2 class="w-5 h-5 animate-spin" />
      <span>{{ t('importUrl.loading') }}</span>
    </div>

    <template #footer>
      <AppButton variant="secondary" @click="close">{{ t('common.cancel') }}</AppButton>
      <AppButton :disabled="loading || !url.trim()" @click="submit">{{ t('importUrl.submit') }}</AppButton>
    </template>
  </BaseModal>
</template>
