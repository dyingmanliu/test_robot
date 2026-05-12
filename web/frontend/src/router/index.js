import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "@/stores/auth";

import LoginView from "@/views/LoginView.vue";
import RegisterView from "@/views/RegisterView.vue";
import CasesView from "@/views/CasesView.vue";
import HomeDashboardView from "@/views/HomeDashboardView.vue";
import ProfileView from "@/views/ProfileView.vue";
import DashboardView from "@/views/DashboardView.vue";
import AdminUsersView from "@/views/AdminUsersView.vue";
import ProjectsView from "@/views/ProjectsView.vue";
import ProjectDashboardView from "@/views/ProjectDashboardView.vue";
import ProjectRunsHistoryView from "@/views/ProjectRunsHistoryView.vue";
import RobotMarketplaceView from "@/views/RobotMarketplaceView.vue";
import PaymentView from "@/views/PaymentView.vue";
import MonitorOpsView from "@/views/MonitorOpsView.vue";
import FunctionalTaskWizardView from "@/views/FunctionalTaskWizardView.vue";
import AdminRentalOrdersView from "@/views/AdminRentalOrdersView.vue";
import PlatformIntroView from "@/views/PlatformIntroView.vue";
import MyRobotsShell from "@/views/MyRobotsShell.vue";
import MyRobotsView from "@/views/MyRobotsView.vue";
import MyRobotDetailView from "@/views/MyRobotDetailView.vue";
import MyRentalApplicationsView from "@/views/MyRentalApplicationsView.vue";

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: "/", name: "home", component: HomeDashboardView, meta: { requiresAuth: true } },
    { path: "/cases", name: "cases", component: CasesView, meta: { requiresAuth: true } },
    { path: "/profile", name: "profile", component: ProfileView, meta: { requiresAuth: true } },
    {
      path: "/projects",
      name: "projects",
      component: ProjectsView,
      meta: { requiresAuth: true },
    },
    {
      path: "/projects/:projectId/dashboard",
      name: "projectDashboard",
      component: ProjectDashboardView,
      meta: { requiresAuth: true },
    },
    {
      path: "/projects/:projectId/runs",
      name: "projectRunsHistory",
      component: ProjectRunsHistoryView,
      meta: { requiresAuth: true },
    },
    {
      path: "/projects/:projectId/functional-task",
      name: "functionalTaskWizard",
      component: FunctionalTaskWizardView,
      meta: { requiresAuth: true },
    },
    {
      path: "/dashboard",
      name: "dashboard",
      component: DashboardView,
      meta: { requiresAuth: true },
    },
    {
      path: "/marketplace",
      name: "robotMarketplace",
      component: RobotMarketplaceView,
      meta: { requiresAuth: true },
    },
    {
      path: "/my-robots",
      component: MyRobotsShell,
      meta: { requiresAuth: true },
      children: [
        { path: "", name: "myRobots", component: MyRobotsView },
        {
          path: ":instanceId(\\d+)",
          name: "myRobotDetail",
          component: MyRobotDetailView,
        },
      ],
    },
    {
      path: "/my-rental-applications",
      name: "myRentalApplications",
      component: MyRentalApplicationsView,
      meta: { requiresAuth: true },
    },
    {
      path: "/payment",
      name: "payment",
      component: PaymentView,
      meta: { requiresAuth: true },
    },
    {
      path: "/monitor",
      name: "monitorOps",
      component: MonitorOpsView,
      meta: { requiresAuth: true, roles: ["platform_admin", "tse"], fullBleed: true },
    },
    {
      path: "/admin/rental-orders",
      name: "adminRentalOrders",
      component: AdminRentalOrdersView,
      meta: { requiresAuth: true, roles: ["platform_admin"] },
    },
    {
      path: "/admin/users",
      name: "adminUsers",
      component: AdminUsersView,
      meta: { requiresAuth: true, roles: ["platform_admin"] },
    },
    {
      path: "/platform-intro",
      name: "platformIntro",
      component: PlatformIntroView,
      meta: { fullBleed: true },
    },
    { path: "/login", name: "login", component: LoginView },
    { path: "/register", name: "register", component: RegisterView },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (to.meta.requiresAuth && !auth.token) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (to.meta.requiresAuth && auth.token && !auth.role) {
    try {
      await auth.fetchMe();
    } catch {
      auth.clear();
      return { name: "login", query: { redirect: to.fullPath } };
    }
  }
  if (to.meta.roles?.length) {
    if (!to.meta.roles.includes(auth.role)) {
      return { name: "home" };
    }
  }
  return true;
});

export default router;
