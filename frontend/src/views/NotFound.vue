<script setup lang="ts">
import { useRouter } from 'vue-router';
import { Home } from '@lucide/vue';

const router = useRouter();

const goHome = () => {
  router.push('/');
};
</script>

<template>
  <div class="min-h-screen bg-background flex flex-col items-center justify-center p-4 text-slate-100 font-sans antialiased">
    <div class="glass-panel w-full max-w-sm bg-gradient-to-br from-surface to-surface/50 border-primary/20 relative overflow-hidden text-center p-8">
      <div class="absolute top-0 right-0 w-32 h-32 bg-primary/10 rounded-full blur-2xl -mr-10 -mt-10"></div>
      <div class="absolute bottom-0 left-0 w-24 h-24 bg-accent/10 rounded-full blur-xl -ml-10 -mb-10"></div>
      
      <div class="text-[6rem] font-black text-transparent bg-clip-text bg-gradient-to-b from-white to-white/20 leading-none mb-4">
        404
      </div>
      
      <h1 class="text-xl font-bold text-white mb-2">Страница не найдена</h1>
      <p class="text-slate-400 text-sm mb-8">
        Возможно, она была удалена или вы ввели неверный адрес.
      </p>
      
      <button 
        @click="goHome" 
        class="w-full bg-white/10 hover:bg-white/20 text-white font-medium py-3 px-4 rounded-xl transition-all duration-300 flex items-center justify-center gap-2 border border-white/5 hover:border-white/20"
      >
        <Home class="w-5 h-5" /> Вернуться на главную
      </button>
    </div>
  </div>
</template>

<style scoped>
.glass-panel {
  @apply bg-surface/80 backdrop-blur-md border border-white/10 rounded-3xl shadow-xl;
}
</style>
