<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { Shield, Loader2, Mail } from '@lucide/vue';
import { 
  loginBasic, 
  loginCodeInit, 
  loginCodeConfirm, 
  registerInit, 
  registerConfirm 
} from '../api/auth';

const router = useRouter();

type AuthMode = 'login_password' | 'register_password' | 'login_code_init' | 'login_code_verify' | 'register_verify';
const mode = ref<AuthMode>('login_password');

const email = ref('');
const password = ref('');
const confirmPassword = ref('');
const otpCode = ref('');
const error = ref('');
const isLoading = ref(false);

const toggleMode = (newMode: AuthMode) => {
  mode.value = newMode;
  error.value = '';
  otpCode.value = '';
};

const validateEmail = (email: string) => {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
};

const validatePassword = (pwd: string) => {
  // Хороший пароль: минимум 8 символов, хотя бы одна цифра
  if (pwd.length < 8) return 'Пароль должен быть не менее 8 символов';
  if (!/\d/.test(pwd)) return 'Пароль должен содержать хотя бы одну цифру';
  return null;
};

const handlePasswordSubmit = async () => {
  if (!email.value || !password.value) {
    error.value = 'Заполните все поля';
    return;
  }
  
  if (!validateEmail(email.value)) {
    error.value = 'Введите корректный email';
    return;
  }

  if (mode.value === 'register_password') {
    const pwdError = validatePassword(password.value);
    if (pwdError) {
      error.value = pwdError;
      return;
    }
    
    if (password.value !== confirmPassword.value) {
      error.value = 'Пароли не совпадают';
      return;
    }
  }
  
  isLoading.value = true;
  error.value = '';
  
  try {
    if (mode.value === 'login_password') {
      const res = await loginBasic(email.value, password.value);
      localStorage.setItem('access_token', res.access_token);
      router.push('/');
    } else if (mode.value === 'register_password') {
      await registerInit(email.value, password.value);
      mode.value = 'register_verify';
    }
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Ошибка авторизации';
  } finally {
    isLoading.value = false;
  }
};

const handleOtpRequest = async () => {
  if (!email.value) {
    error.value = 'Введите email';
    return;
  }
  
  if (!validateEmail(email.value)) {
    error.value = 'Введите корректный email';
    return;
  }
  
  isLoading.value = true;
  error.value = '';
  
  try {
    await loginCodeInit(email.value);
    mode.value = 'login_code_verify';
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Ошибка отправки кода';
  } finally {
    isLoading.value = false;
  }
};

const handleOtpVerify = async () => {
  if (!otpCode.value || otpCode.value.length !== 6) {
    error.value = 'Введите 6-значный код';
    return;
  }
  
  isLoading.value = true;
  error.value = '';
  
  try {
    let res;
    if (mode.value === 'login_code_verify') {
      res = await loginCodeConfirm(email.value, otpCode.value);
    } else {
      res = await registerConfirm(email.value, otpCode.value);
    }
    localStorage.setItem('access_token', res.access_token);
    router.push('/');
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Неверный или просроченный код';
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
          <Shield v-if="mode === 'login_password' || mode === 'register_password'" class="w-7 h-7 text-primary" />
          <Mail v-else class="w-7 h-7 text-primary" />
        </div>
        <h1 class="text-2xl font-bold text-white mb-1">
          <template v-if="mode === 'login_password'">Вход по паролю</template>
          <template v-else-if="mode === 'register_password'">Регистрация</template>
          <template v-else-if="mode === 'login_code_init'">Войти по коду</template>
          <template v-else-if="mode === 'login_code_verify' || mode === 'register_verify'">Код из Email</template>
        </h1>
        <p class="text-sm text-slate-400">SafeFlow VPN</p>
      </div>
      
      <div v-if="error" class="bg-red-500/10 border border-red-500/20 text-red-400 text-sm p-3 rounded-xl mb-4 text-center transition-all">
        {{ error }}
      </div>

      <!-- ФОРМА: Пароль -->
      <form v-if="mode === 'login_password' || mode === 'register_password'" @submit.prevent="handlePasswordSubmit" class="space-y-4">
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
        <div v-if="mode === 'register_password'">
          <label class="block text-sm font-medium text-slate-400 mb-1">Повторите пароль</label>
          <input 
            v-model="confirmPassword" 
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
          <span v-else>{{ mode === 'login_password' ? 'Войти' : 'Продолжить' }}</span>
        </button>
      </form>

      <!-- ФОРМА: Запрос OTP (Вход) -->
      <form v-else-if="mode === 'login_code_init'" @submit.prevent="handleOtpRequest" class="space-y-4">
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
        <button 
          type="submit" 
          class="w-full bg-primary hover:bg-primary/90 text-white font-medium py-3 rounded-xl transition-colors flex items-center justify-center gap-2 mt-2"
          :disabled="isLoading"
        >
          <Loader2 v-if="isLoading" class="w-5 h-5 animate-spin" />
          <span v-else>Получить код</span>
        </button>
      </form>

      <!-- ФОРМА: Подтверждение OTP -->
      <form v-else-if="mode === 'login_code_verify' || mode === 'register_verify'" @submit.prevent="handleOtpVerify" class="space-y-4">
        <p class="text-sm text-slate-400 text-center mb-2">Код отправлен на <br><b class="text-white">{{email}}</b></p>
        <div>
          <label class="block text-sm font-medium text-slate-400 mb-1">6-значный код</label>
          <input 
            v-model="otpCode" 
            type="text" 
            maxlength="6"
            placeholder="123456"
            class="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-3 text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all text-center tracking-widest text-lg"
            required
          >
        </div>
        <button 
          type="submit" 
          class="w-full bg-primary hover:bg-primary/90 text-white font-medium py-3 rounded-xl transition-colors flex items-center justify-center gap-2 mt-2"
          :disabled="isLoading"
        >
          <Loader2 v-if="isLoading" class="w-5 h-5 animate-spin" />
          <span v-else>Подтвердить</span>
        </button>
      </form>

      <!-- Навигация между режимами -->
      <div class="mt-6 flex flex-col gap-2 text-center text-sm text-slate-400">
        <div v-if="mode === 'login_password'">
          <button @click="toggleMode('login_code_init')" class="text-primary hover:underline font-medium focus:outline-none mb-1">Войти по коду из Email</button>
          <div>Нет аккаунта? <button @click="toggleMode('register_password')" class="text-primary hover:underline font-medium focus:outline-none">Создать</button></div>
        </div>
        
        <div v-if="mode === 'register_password'">
          Уже есть аккаунт? <button @click="toggleMode('login_password')" class="text-primary hover:underline font-medium focus:outline-none">Войти</button>
        </div>

        <div v-if="mode === 'login_code_init' || mode === 'login_code_verify' || mode === 'register_verify'">
          Вспомнили пароль? <button @click="toggleMode('login_password')" class="text-primary hover:underline font-medium focus:outline-none">Войти по паролю</button>
        </div>
      </div>
      
    </div>

  </div>
</template>

<style scoped>
.glass-panel {
  @apply bg-surface/80 backdrop-blur-md border border-white/10 rounded-3xl p-6 shadow-xl;
}
</style>
