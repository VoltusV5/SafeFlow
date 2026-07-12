import { createRouter, createWebHistory } from 'vue-router';
import type { RouteRecordRaw } from 'vue-router';
import Dashboard from '../views/Dashboard.vue';
import Login from '../views/Login.vue';
import NotFound from '../views/NotFound.vue';

const routes: Array<RouteRecordRaw> = [
  {
    path: '/',
    name: 'Dashboard',
    component: Dashboard,
    meta: { requiresAuth: true }
  },
  {
    path: '/login',
    name: 'Login',
    component: Login
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: NotFound
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

// Guard
router.beforeEach((to, from, next) => {
  const isAuthenticated = !!localStorage.getItem('access_token');
  
  if (to.meta.requiresAuth && !isAuthenticated) {
    next('/login');
  } else if (to.name === 'Login' && isAuthenticated) {
    next('/');
  } else {
    next();
  }
});

export default router;
