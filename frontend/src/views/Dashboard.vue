<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { Shield, Plus, Copy, ChevronRight, Loader2, User as UserIcon, LogOut } from '@lucide/vue';
import { apiClient } from '../api/index';
import { authTelegram } from '../api/auth';
import { fetchUserProfile } from '../api/user';
import type { UserMeResponse } from '../api/user';
import { fetchMyKeys } from '../api/keys';
import type { VpnKey } from '../api/keys';

const router = useRouter();

const isLoading = ref(true);
const error = ref<string | null>(null);

const profile = ref<UserMeResponse | null>(null);
const keys = ref<VpnKey[]>([]);

const isLogoutMenuOpen = ref(false);
const isCreatingKey = ref(false);
const isTariffMenuOpen = ref(false);

const toggleLogoutMenu = () => {
  isLogoutMenuOpen.value = !isLogoutMenuOpen.value;
};

const handleLogout = () => {
  localStorage.removeItem('access_token');
  router.push('/login');
};

const copyToClipboard = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text);
    alert('Ключ скопирован!');
  } catch (err) {
    console.error('Failed to copy text: ', err);
  }
};

const formatDate = (dateString: string | null) => {
  if (!dateString) return 'Без ограничений';
  const d = new Date(dateString);
  return d.toLocaleDateString('ru-RU');
};

const getDeviceName = (protocol: string, id: number) => {
  return `${protocol} Устройство #${id}`;
};

const createKey = async () => {
  try {
    isCreatingKey.value = true;
    await apiClient.post('/keys');
    keys.value = await fetchMyKeys();
  } catch (err: any) {
    console.error(err);
    alert(err.response?.data?.detail || 'Ошибка при создании ключа');
  } finally {
    isCreatingKey.value = false;
  }
};

const handleTopup = async () => {
  const amountStr = prompt('Введите сумму пополнения в рублях:');
  if (!amountStr) return;
  const amount = parseInt(amountStr, 10);
  if (isNaN(amount) || amount <= 0) {
    alert('Неверная сумма');
    return;
  }
  
  try {
    const res = await apiClient.post('/payments/create', { amount, plan: 'BASE' });
    if (res.data.payment_url) {
      window.open(res.data.payment_url, '_blank');
    }
  } catch (err) {
    console.error(err);
    alert('Ошибка создания платежа');
  }
};

const handlePlanBuy = async (plan: string, amount: number) => {
  try {
    const res = await apiClient.post('/payments/create', { amount, plan });
    if (res.data.payment_url) {
      window.open(res.data.payment_url, '_blank');
    }
  } catch (err) {
    console.error(err);
    alert('Ошибка создания платежа');
  }
};

onMounted(async () => {
  try {
    isLoading.value = true;
    
    // Проверяем, есть ли уже токен (например, от логина по Email)
    let hasToken = !!localStorage.getItem('access_token');
    
    // Пытаемся получить initData из Telegram WebApp
    // @ts-ignore
    const tg = window.Telegram?.WebApp;
    let initData = tg?.initData;

    // Если нет токена и мы внутри Telegram - авторизуемся
    if (!hasToken && initData) {
      const authResponse = await authTelegram(initData);
      if (authResponse.access_token) {
        localStorage.setItem('access_token', authResponse.access_token);
        hasToken = true;
      }
    } else if (!hasToken) {
      // Если мы вне телеги и нет токена - перенаправляем на /login
      router.push('/login');
      return;
    }

    // Загружаем данные профиля и ключи
    if (hasToken) {
      const [profileData, keysData] = await Promise.all([
        fetchUserProfile(),
        fetchMyKeys()
      ]);
      
      profile.value = profileData;
      keys.value = keysData;
    }
    
    // Говорим Telegram, что мы загрузились
    tg?.ready();
    tg?.expand();
  } catch (err: any) {
    console.error(err);
    error.value = err.message || "Ошибка загрузки данных";
  } finally {
    isLoading.value = false;
  }
});
</script>

<template>
  <div class="min-h-screen bg-background p-4 pb-20 max-w-md mx-auto relative text-slate-100 font-sans antialiased" @click="isLogoutMenuOpen = false">
    
    <div v-if="isLoading" class="flex flex-col items-center justify-center h-[80vh]">
      <Loader2 class="w-10 h-10 text-primary animate-spin mb-4" />
      <p class="text-slate-400">Загрузка данных...</p>
    </div>
    
    <div v-else-if="error" class="flex flex-col items-center justify-center h-[80vh] text-center">
      <div class="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mb-4">
        <span class="text-red-500 text-2xl">!</span>
      </div>
      <p class="text-white font-medium mb-2">Ошибка подключения</p>
      <p class="text-slate-400 text-sm px-4">{{ error }}</p>
      <p class="text-slate-500 text-xs mt-4">Убедитесь, что вы авторизованы или открываете приложение внутри Telegram.</p>
    </div>

    <template v-else-if="profile">
      <!-- Header -->
      <header class="flex items-center justify-between mb-6">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center">
            <Shield class="w-6 h-6 text-primary" />
          </div>
          <div>
            <h1 class="text-xl font-bold text-white">SafeFlow VPN</h1>
            <p class="text-sm text-slate-400" v-if="profile.user.username">@{{ profile.user.username }}</p>
            <p class="text-sm text-slate-400" v-else-if="profile.user.telegram_id">@{{ profile.user.telegram_id }}</p>
          </div>
        </div>
        
        <!-- User Profile Dropdown -->
        <div class="relative" @click.stop>
          <button @click="toggleLogoutMenu" class="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center hover:bg-white/20 transition">
            <UserIcon class="w-5 h-5 text-white" />
          </button>
          
          <div v-if="isLogoutMenuOpen" class="absolute right-0 mt-2 w-40 glass-panel !p-2 z-50">
            <button @click="handleLogout" class="w-full text-left px-3 py-2 text-sm text-red-400 hover:bg-red-500/10 rounded-lg flex items-center gap-2 transition-colors">
              <LogOut class="w-4 h-4" /> Выйти
            </button>
          </div>
        </div>
      </header>

      <!-- Balance & Status Card -->
      <div class="glass-panel mb-6 bg-gradient-to-br from-surface to-surface/50 border-primary/20 relative overflow-hidden">
        <div class="absolute top-0 right-0 w-32 h-32 bg-primary/10 rounded-full blur-2xl -mr-10 -mt-10"></div>
        
        <div class="flex justify-between items-start mb-4">
          <div>
            <p class="text-sm text-slate-400 mb-1">Баланс</p>
            <div class="flex items-baseline gap-1">
              <h2 class="text-3xl font-bold text-white">{{ profile.user.balance }}</h2>
              <span class="text-slate-400 text-sm">₽</span>
            </div>
          </div>
          <button @click="handleTopup" class="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center hover:bg-white/10 transition">
            <Plus class="w-5 h-5 text-white" />
          </button>
        </div>

        <div class="bg-black/20 rounded-xl p-3 mt-4 relative">
          <div class="flex items-center justify-between cursor-pointer hover:bg-white/5 transition rounded-lg p-2 -m-2" @click="isTariffMenuOpen = !isTariffMenuOpen">
            <div class="flex items-center gap-3" v-if="profile.active_subscription">
              <div class="w-2 h-2 rounded-full bg-accent animate-pulse"></div>
              <div>
                <p class="text-sm font-medium text-white">Тариф {{ profile.active_subscription.plan }}</p>
                <p class="text-xs text-slate-400">Активен до {{ formatDate(profile.active_subscription.expires_at) }}</p>
              </div>
            </div>
            <div class="flex items-center gap-3" v-else>
              <div class="w-2 h-2 rounded-full bg-slate-500"></div>
              <div>
                <p class="text-sm font-medium text-white">Нет активной подписки</p>
                <p class="text-xs text-slate-400">Нажмите чтобы выбрать тариф</p>
              </div>
            </div>
            <ChevronRight class="w-5 h-5 text-slate-500 transition-transform" :class="{ 'rotate-90': isTariffMenuOpen }" />
          </div>
          
          <div v-if="isTariffMenuOpen" class="mt-3 pt-3 border-t border-white/10 flex flex-col gap-2">
            <button @click="handlePlanBuy('BASE', 100)" class="w-full text-left p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors border border-white/5 flex justify-between items-center">
              <div>
                <span class="text-white font-medium block">Базовый (BASE)</span>
                <span class="text-xs text-slate-400">Оптимально для одного устройства</span>
              </div>
              <span class="text-primary font-bold">100 ₽</span>
            </button>
            <button @click="handlePlanBuy('PREMIUM', 150)" class="w-full text-left p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors border border-white/5 flex justify-between items-center">
              <div>
                <span class="text-white font-medium block">Расширенный (PREMIUM)</span>
                <span class="text-xs text-slate-400">Для всех устройств</span>
              </div>
              <span class="text-primary font-bold">150 ₽</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Keys List -->
      <div class="flex items-center justify-between mb-3 mt-6">
        <h3 class="text-lg font-semibold text-white flex items-center gap-2">
          <Shield class="w-5 h-5 text-primary" />
          Мои ключи
        </h3>
        <button 
          @click="createKey" 
          :disabled="isCreatingKey"
          class="text-sm text-primary font-medium flex items-center gap-1 hover:text-blue-400 transition-colors disabled:opacity-50"
        >
          <Loader2 v-if="isCreatingKey" class="w-4 h-4 animate-spin" />
          <Plus v-else class="w-4 h-4" /> 
          Новый
        </button>
      </div>
      
      <div v-if="keys.length === 0" class="text-center py-8">
        <p class="text-slate-400 text-sm">У вас пока нет ключей доступа.</p>
        <button @click="createKey" :disabled="isCreatingKey" class="mt-3 text-primary text-sm font-medium hover:underline flex items-center justify-center gap-2 mx-auto disabled:opacity-50">
          <Loader2 v-if="isCreatingKey" class="w-4 h-4 animate-spin" />
          Создать первый ключ
        </button>
      </div>
      
      <div v-else class="space-y-3">
        <div v-for="key in keys" :key="key.id" class="glass-panel p-3 flex items-center justify-between group">
          <div>
            <p class="font-medium text-white text-sm mb-1">{{ getDeviceName(key.protocol, key.id) }}</p>
            <div class="flex items-center gap-2 text-xs">
              <span class="px-2 py-0.5 rounded-full" :class="key.status === 'active' ? 'bg-accent/20 text-accent' : 'bg-red-500/20 text-red-500'">
                {{ key.status === 'active' ? 'Активен' : 'Отключен' }}
              </span>
              <span class="text-slate-400" v-if="key.expires_at">до {{ formatDate(key.expires_at) }}</span>
            </div>
          </div>
          <button 
            @click="copyToClipboard(key.config_data)"
            class="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center hover:bg-primary/20 hover:text-primary transition-colors text-slate-400"
          >
            <Copy class="w-5 h-5" />
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<style>
/* Any extra component specific styles here */
.glass-panel {
  @apply bg-surface/80 backdrop-blur-md border border-white/10 rounded-2xl p-4 shadow-lg;
}
</style>
