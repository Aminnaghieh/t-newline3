"use client";
import { useEffect, useState } from "react";
import { useAppStore, type Section } from "@/lib/store";
import { DemoBadge, LiaraLogo } from "./badges";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Bot,
  Boxes,
  Rocket,
  ScrollText,
  Settings2,
  Menu,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

const NAV: { id: Section; label: string; icon: typeof LayoutDashboard; hint: string }[] = [
  { id: "dashboard", label: "نمای کلی", icon: LayoutDashboard, hint: "وضعیت سرویس‌ها و هشدارها" },
  { id: "agent", label: "سوپر ایجنت", icon: Bot, hint: "گفتگو و عیب‌یابی هوشمند" },
  { id: "projects", label: "سرویس‌ها", icon: Boxes, hint: "مدیریت اپلیکیشن‌ها" },
  { id: "deploy", label: "استقرار", icon: Rocket, hint: "دیپلوی هوشمند" },
  { id: "audit", label: "ممیزی", icon: ScrollText, hint: "گزارش عملیات" },
  { id: "settings", label: "تنظیمات", icon: Settings2, hint: "اتصال به API لیارا" },
];

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  const { section, navigate, selectedProject } = useAppStore();
  return (
    <nav className="flex flex-col gap-1 px-3">
      {NAV.map((item) => {
        const active = section === item.id || (section === "projects" && item.id === "projects");
        const isProjects = item.id === "projects";
        return (
          <button
            key={item.id}
            onClick={() => {
              navigate(item.id, isProjects ? selectedProject : null);
              onNavigate?.();
            }}
            className={cn(
              "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-right transition-all",
              active
                ? "bg-white/6 text-foreground ring-1 ring-inset ring-[#87fcc4]/25"
                : "text-muted-foreground hover:bg-white/4 hover:text-foreground"
            )}
          >
            <span
              className={cn(
                "flex size-8 items-center justify-center rounded-lg transition-colors",
                active ? "liara-gradient text-[#0e1512]" : "bg-white/5 text-muted-foreground group-hover:text-[#87fcc4]"
              )}
            >
              <item.icon className="size-4" />
            </span>
            <span className="flex-1">
              <span className={cn("block text-[13px] font-bold", active && "text-[#87fcc4]")}>
                {item.label}
              </span>
              <span className="block text-[10.5px] text-muted-foreground">{item.hint}</span>
            </span>
            {active && <span className="h-6 w-1 rounded-full liara-gradient" />}
          </button>
        );
      })}
    </nav>
  );
}

function SidebarInner({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col">
      <div className="px-5 pb-5 pt-6">
        <LiaraLogo />
      </div>
      <NavList onNavigate={onNavigate} />
      <div className="mt-auto p-4">
        <div className="rounded-xl border border-white/8 bg-white/3 p-3.5 text-[11px] leading-6 text-muted-foreground">
          <div className="mb-1 font-bold text-[#87fcc4]">🛡 Human-in-the-Loop</div>
          عملیات پرریسک فقط با تایید صریح شما و امضای رمزنگاری‌شده اجرا می‌شود و در گزارش ممیزی ثبت می‌گردد.
        </div>
        <div className="mt-3 text-center text-[10px] text-muted-foreground/60" dir="ltr">
          Powered by Liara PaaS API v1/v2
        </div>
      </div>
    </div>
  );
}

export function AppShell({
  children,
  title,
  subtitle,
  actions,
}: {
  children: React.ReactNode;
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}) {
  const [demo, setDemo] = useState(true);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    fetch("/api/projects")
      .then((r) => r.json())
      .then((d) => setDemo(Boolean(d.demo)))
      .catch(() => {});
  }, []);

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar (RTL → right side) */}
      <aside className="sticky top-0 hidden h-screen w-[272px] shrink-0 border-l border-white/6 bg-[#191f1b] lg:block">
        <SidebarInner />
      </aside>

      {/* Mobile drawer */}
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger asChild>
          <Button
            variant="outline"
            size="icon"
            className="fixed top-4 right-4 z-50 lg:hidden"
            aria-label="باز کردن منو"
          >
            {open ? <X className="size-4" /> : <Menu className="size-4" />}
          </Button>
        </SheetTrigger>
        <SheetContent side="right" className="w-[290px] bg-[#191f1b] p-0">
          <SheetTitle className="sr-only">منوی ناوبری</SheetTitle>
          <SidebarInner onNavigate={() => setOpen(false)} />
        </SheetContent>
      </Sheet>

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-40 border-b border-white/6 bg-background/80 backdrop-blur-xl">
          <div className="flex flex-wrap items-center gap-3 px-4 py-3.5 pl-4 pr-16 sm:px-6 lg:pr-6">
            <div className="min-w-0 flex-1 pl-10 lg:pl-0">
              <h1 className="truncate text-[17px] font-extrabold">{title}</h1>
              {subtitle && (
                <p className="mt-0.5 truncate text-[12px] text-muted-foreground">{subtitle}</p>
              )}
            </div>
            <div className="flex items-center gap-2.5">
              {actions}
              <DemoBadge demo={demo} />
            </div>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1200px] flex-1 px-4 pb-10 pt-5 sm:px-6">
          {children}
        </main>
        <footer className="mt-auto border-t border-white/6 py-4 text-center text-[11px] text-muted-foreground/70">
          ساخته‌شده برای مشتریان لیارا — استقرار، پایش و عیب‌یابی با هوش مصنوعی •{" "}
          <span dir="ltr">liara.ir</span>
        </footer>
      </div>
    </div>
  );
}
