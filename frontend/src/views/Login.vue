<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Eye, EyeOff } from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'
import { useSyncStore } from '../stores/sync'
import AppButton from '../components/AppButton.vue'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const syncStore = useSyncStore()

const name = ref('')
const password = ref('')
const showPassword = ref(false)
const error = ref('')
const loading = ref(false)

function errorMessage(e) {
  const status = e.response?.status
  if (status === 401) return t('login.invalidCredentials')
  if (status === 429) {
    const minutes = Math.max(1, Math.ceil(Number(e.response?.headers?.['retry-after']) / 60) || 1)
    return t('login.tooManyAttempts', { minutes })
  }
  return e.response?.data?.detail || t('login.error')
}

async function submit() {
  if (loading.value) return
  error.value = ''
  if (!name.value.trim()) {
    error.value = t('login.fillBoth')
    return
  }
  loading.value = true

  try {
    await authStore.login(name.value.trim(), password.value)
    syncStore.connect()
    router.push('/')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-[100svh] flex items-center justify-center p-4">
    <div class="w-full max-w-xs text-center">
      <h1 class="text-3xl font-bold text-primary mb-1">{{ t('login.title') }}</h1>
      <p class="text-text-muted mb-8">{{ t('login.tagline') }}</p>

      <form class="flex flex-col gap-4" @submit.prevent="submit">
        <input
          v-model="name"
          type="text"
          autocomplete="username"
          :placeholder="t('login.name')"
          :disabled="loading"
          class="px-4 py-3 border border-border rounded-lg text-base bg-surface text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10"
        />

        <div class="relative">
          <input
            v-model="password"
            :type="showPassword ? 'text' : 'password'"
            autocomplete="current-password"
            :placeholder="t('login.password')"
            :disabled="loading"
            class="w-full pl-4 pr-12 py-3 border border-border rounded-lg text-base bg-surface text-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10"
          />
          <button
            type="button"
            class="absolute inset-y-0 right-0 px-3 text-text-muted hover:text-text-secondary"
            :aria-label="showPassword ? t('login.hidePassword') : t('login.showPassword')"
            @click="showPassword = !showPassword"
          >
            <EyeOff v-if="showPassword" class="w-5 h-5" />
            <Eye v-else class="w-5 h-5" />
          </button>
        </div>

        <AppButton type="submit" variant="primary" block :disabled="loading">
          {{ loading ? t('login.loading') : t('login.login') }}
        </AppButton>

        <p v-if="error" class="text-danger text-sm">{{ error }}</p>
      </form>
    </div>
  </div>
</template>
