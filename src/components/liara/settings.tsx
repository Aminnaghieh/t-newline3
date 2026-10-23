"use client";
import { useEffect, useState } from "react";
import { SectionCard } from "./dashboard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/hooks/use-toast";
import {
  BadgeCheck,
  Eye,
  EyeOff,
  KeyRound,
  Loader2,
  PlugZap,
  ShieldCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface SettingsData {
  demoMode: boolean;
  hasToken: boolean;
  tokenMasked: string;
  teamId: string;
}

export function SettingsView() {
  const [data, setData] = useState<SettingsData | null>(null);
  const [token, setToken] = useState("");
  const [teamId, setTeamId] = useState("");
  const [showToken, setShowToken] = useState(false);
  const [busy, setBusy] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string; demo?: boolean } | null>(null);
  const [testing, setTesting] = useState(false);
  const { toast } = useToast();

  const load = () =>
    fetch("/api/settings")
      .then((r) => r.json())
      .then((d: SettingsData) => {
        setData(d);
        setTeamId(d.teamId ?? "");
      });

  useEffect(() => {
    load();
  }, []);

  const save = async (patch: Record<string, unknown>, note: string) => {
    setBusy(true);
    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      const d: SettingsData = await res.json();
      setData(d);
      toast({ title: "ذخیره شد ✅", description: note });
      setToken("");
    } finally {
      setBusy(false);
    }
  };

  const test = async () => {
    setTesting(true);
    try {
      const r = await fetch("/api/settings/test");
      const d = await r.json();
      setTestResult(d);
    } finally {
      setTesting(false);
    }
  };

  if (!data) return null;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <SectionCard title="اتصال به API لیارا" icon={<KeyRound className="size-4" />}>
        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-[12.5px] font-bold">توکن API لیارا</label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Input
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder={data.hasToken ? data.tokenMasked : "liara_xxxxxxxxxxxx"}
                  type={showToken ? "text" : "password"}
                  dir="ltr"
                  className="border-white/10 bg-[#161b18] pl-9 text-left text-[12.5px] focus-visible:ring-[#87fcc4]/40"
                />
                <button
                  onClick={() => setShowToken((v) => !v)}
                  className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-[#87fcc4]"
                  aria-label="نمایش توکن"
                >
                  {showToken ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
              <Button
                disabled={busy || !token.trim()}
                onClick={() => save({ liaraToken: token, demoMode: false }, "توکن ذخیره شد — اتصال زنده فعال است")}
                className="liara-gradient font-extrabold text-[#0e1512] hover:opacity-90"
              >
                {busy && <Loader2 className="size-4 animate-spin" />}
                ذخیره
              </Button>
            </div>
            <p className="mt-2 text-[11px] leading-5 text-muted-foreground">
              توکن را از{" "}
              <a
                href="https://console.liara.ir"
                target="_blank"
                rel="noreferrer"
                className="text-[#28c1f5] underline"
              >
                console.liara.ir
              </a>{" "}
              بخش API Token بگیرید. توکن فقط در دیتابیس محلی همین محیط ذخیره می‌شود و هرگز به سمت
              هوش مصنوعی ارسال نمی‌گردد.
            </p>
            {data.hasToken && (
              <div className="mt-2 flex items-center gap-1.5 text-[11.5px] text-[#87fcc4]">
                <BadgeCheck className="size-4" />
                توکن ثبت‌شده: <span className="latin-digits" dir="ltr">{data.tokenMasked}</span>
              </div>
            )}
          </div>

          <div>
            <label className="mb-1.5 block text-[12.5px] font-bold">شناسه تیم (اختیاری — TeamID)</label>
            <Input
              value={teamId}
              onChange={(e) => setTeamId(e.target.value)}
              placeholder="team_xxx"
              dir="ltr"
              className="border-white/10 bg-[#161b18] text-left text-[12.5px] focus-visible:ring-[#87fcc4]/40"
            />
          </div>

          <div className="flex items-center justify-between rounded-xl border border-white/8 bg-white/3 p-3.5">
            <div>
              <div className="text-[13px] font-extrabold">حالت دمو (شبیه‌سازی)</div>
              <p className="mt-0.5 text-[11px] leading-5 text-muted-foreground">
                با فعال بودن این حالت، داده‌ها به‌صورت واقع‌گرایانه شبیه‌سازی می‌شوند و نیازی به توکن نیست.
              </p>
            </div>
            <Switch
              checked={data.demoMode}
              onCheckedChange={(v) => save({ demoMode: v }, v ? "حالت دمو فعال شد" : "اتصال زنده فعال شد")}
              disabled={busy}
              className="data-[state=checked]:bg-[#87fcc4]"
            />
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              onClick={test}
              disabled={testing}
              className="border-[#28c1f5]/30 text-[#28c1f5] hover:bg-[#28c1f5]/10"
            >
              {testing ? <Loader2 className="size-4 animate-spin" /> : <PlugZap className="size-4" />}
              تست اتصال
            </Button>
            {testResult && (
              <span
                className={cn(
                  "rounded-lg px-3 py-1.5 text-[12px] font-bold",
                  testResult.ok ? "bg-[#87fcc4]/10 text-[#87fcc4]" : "bg-[#ff6b6b]/10 text-[#ff6b6b]"
                )}
              >
                {testResult.message}
              </span>
            )}
          </div>
        </div>
      </SectionCard>

      <SectionCard title="امنیت و حریم خصوصی" icon={<ShieldCheck className="size-4" />}>
        <div className="space-y-3 text-[12.5px] leading-6 text-muted-foreground">
          {[
            ["🔐 Human-in-the-Loop", "عملیات restart/scale/resize حذف پروژه هرگز بدون تایید صریح شما اجرا نمی‌شود. هر تاییدیه امضای رمزنگاری‌شده (SHA-256) و مهلت ۱۵ دقیقه‌ای دارد."],
            ["🧹 پاک‌سازی داده‌های حساس", "لاگ‌های ارسالی به مدل هوش مصنوعی پیش از تحلیل از توکن‌ها و کلیدها پاک‌سازی (Redact) می‌شوند."],
            ["📜 ممیزی کامل", "هر عملیات با زمان، منبع، سطح ریسک و نتیجه در گزارش ممیزی تغییرناپذیر ثبت می‌شود."],
            ["🏠 داده‌های محلی", "تنظیمات و تاریخچه گفتگو فقط در دیتابیس SQLite همین سرور نگهداری می‌شود."],
            ["🚦 محدودیت نرخ", "کلاینت API با سقف ۶۰ درخواست خواندن و ۲۰ درخواست نوشتن در دقیقه، در برابر Rate-Limit لیارا محافظت می‌کند."],
          ].map(([t, d]) => (
            <div key={t} className="rounded-xl border border-white/8 bg-white/3 p-3">
              <div className="mb-1 text-[13px] font-extrabold text-foreground">{t}</div>
              {d}
            </div>
          ))}
        </div>
      </SectionCard>
    </div>
  );
}
