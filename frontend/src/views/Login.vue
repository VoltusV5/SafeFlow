<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { Shield, Loader2 } from '@lucide/vue';
import { apiClient } from '../api/index';

const router = useRouter();

const isLogin = ref(true);
const email = ref('');
const password = ref('');
const error = ref('');
const isLoading = ref(false);

const toggleMode = () => {
  isLogin.value = !isLogin.value;
  error.value = '';
};

const handleSubmit = async () => {
  if (!email.value || !password.value) {
    error.value = 'Заполните все поля';
    return;
  }
  
  isLoading.value = true;
  error.value = '';
  
  try {
    if (isLogin.value) {
      // Имитация FormData для OAuth2PasswordRequestForm
      const formData = new FormData();
      formData.append('username', email.value);
      formData.append('password', password.value);
      
      const res = await apiClient.post('/auth/login', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      localStorage.setItem('access_token', res.data.access_token);
    } else {
      const res = await apiClient.post('/auth/register', {
        email: email.value,
        password: password.value
      });
      localStorage.setItem('access_token', res.data.access_token);
    }
    
    router.push('/');
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Ошибка авторизации';
  } finally {
    isLoading.value = false;
  }
};
</script>

<template>
  <div class="min-h-screen bg-background flex flex-col items-center justify-center p-4 text-slate-100 font-sans antialiased">
    
    <div class="glass-panel w-full max-w-sm bg-gradient-to-br from-surface to-surface/50 border-primary/20 relative overflow-hidden">
      <div class="absolute top-0 right-0 w-32 h-32 bg-primary/10 rounded-full blur-2xl -mr-10 -mt-10"></div>
      
      <div class="flex flex-col items-center mb-6">
        <div class="w-12 h-12 rounded-full bg-primary/20 flex items-center justify-center mb-4">
          <Shield class="w-7 h-7 text-primary" />
        </div>
        <h1 class="text-2xl font-bold text-white mb-1">{{ isLogin ? 'Вход в аккаунт' : 'Регистрация' }}</h1>
        <p class="text-sm text-slate-400">SafeFlow VPN</p>
      </div>
      
      <div v-if="error" class="bg-red-500/10 border border-red-500/20 text-red-400 text-sm p-3 rounded-xl mb-4 text-center">
        {{ error }}
      </div>

      <form @submit.prevent="handleSubmit" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-slate-400 mb-1">Email</label>
          <input 
            v-model="email" 
            type="email" 
            placeholder="you@example.com"
            class="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-3 text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all"
            required
          >
        </div>
        
        <div>
          <label class="block text-sm font-medium text-slate-400 mb-1">Пароль</label>
          <input 
            v-model="password" 
            type="password" 
            placeholder="••••••••"
            class="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-3 text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all"
            required
          >
        </div>
        
        <button 
          type="submit" 
          class="w-full bg-primary hover:bg-primary/90 text-white font-medium py-3 rounded-xl transition-colors flex items-center justify-center gap-2 mt-2"
          :disabled="isLoading"
        >
          <Loader2 v-if="isLoading" class="w-5 h-5 animate-spin" />
          <span v-else>{{ isLogin ? 'Войти' : 'Зарегистрироваться' }}</span>
        </button>
      </form>

      <div class="mt-6 text-center text-sm text-slate-400">
        <span v-if="isLogin">
          Нет аккаунта? 
          <button @click="toggleMode" class="text-primary hover:underline font-medium focus:outline-none">Создать</button>
        </span>
        <span v-else>
          Уже есть аккаунт? 
          <button @click="toggleMode" class="text-primary hover:underline font-medium focus:outline-none">Войти</button>
        </span>
      </div>
      
      <!-- Telegram Auth Placeholder (TODO) -->
      <div class="mt-6 pt-6 border-t border-white/10 flex flex-col items-center">
        <p class="text-xs text-slate-500 mb-3">Или войдите через Telegram (скоро)</p>
        <button disabled class="w-full bg-[#2AABEE]/20 text-[#2AABEE] font-medium py-2 rounded-xl flex items-center justify-center gap-2 opacity-50 cursor-not-allowed">
          Войти через Telegram
        </button>
      </div>
    </div>

  </div>
</template>

<style scoped>
.glass-panel {
  @apply bg-surface/80 backdrop-blur-md border border-white/10 rounded-3xl p-6 shadow-xl;
}
</style>
