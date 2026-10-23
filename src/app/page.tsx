"use client";
import { useAppStore } from "@/lib/store";
import { AppShell } from "@/components/liara/shell";
import { Dashboard } from "@/components/liara/dashboard";
import { AgentChat } from "@/components/liara/chat";
import { ProjectsView } from "@/components/liara/projects";
import { DeployWizard } from "@/components/liara/deploy-wizard";
import { AuditView } from "@/components/liara/audit";
import { SettingsView } from "@/components/liara/settings";
import { Button } from "@/components/ui/button";
import { Bot } from "lucide-react";

const TITLES: Record<string, { title: string; subtitle: string }> = {
  dashboard: {
    title: "نمای کلی",
    subtitle: "وضعیت زنده سرویس‌ها، هشدارهای زودهنگام و شاخص‌های حیاتی",
  },
  agent: {
    title: "سوپر ایجنت",
    subtitle: "عیب‌یابی هوشمند، تحلیل متریک و اجرای عملیات با تایید شما (Human-in-the-Loop)",
  },
  projects: {
    title: "مدیریت سرویس‌ها",
    subtitle: "مانیتورینگ، لاگ زنده، ریلیزها و عملیات پروداکشن",
  },
  deploy: {
    title: "استقرار هوشمند",
    subtitle: "تحلیل خودکار سورس، پیشنهاد پلن بهینه و دیپلوی بدون وقفه",
  },
  audit: {
    title: "گزارش ممیزی",
    subtitle: "لاگ تغییرناپذیر تمام عملیات حساس (Append-Only Audit Trail)",
  },
  settings: {
    title: "تنظیمات",
    subtitle: "اتصال به API لیارا، امنیت و مدیریت توکن",
  },
};

export default function Home() {
  const { section, selectedProject } = useAppStore();
  const meta = TITLES[section] ?? TITLES.dashboard;

  return (
    <AppShell
      title={meta.title}
      subtitle={meta.subtitle}
      actions={
        section !== "agent" ? (
          <Button
            onClick={() => useAppStore.getState().navigate("agent")}
            className="liara-gradient hidden font-extrabold text-[#0e1512] hover:opacity-90 sm:inline-flex"
          >
            <Bot className="size-4" />
            پرسش از ایجنت
          </Button>
        ) : null
      }
    >
      {section === "dashboard" && <Dashboard />}
      {section === "agent" && <AgentChat />}
      {section === "projects" && <ProjectsView selected={selectedProject} />}
      {section === "deploy" && <DeployWizard />}
      {section === "audit" && <AuditView />}
      {section === "settings" && <SettingsView />}
    </AppShell>
  );
}
