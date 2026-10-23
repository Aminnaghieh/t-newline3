// Plan catalog — ported verbatim (values) from the Python agent's
// utils/constants.py PLAN_CATALOG. Liara does not expose plan details
// via API, so this local catalog is the single source of truth.
import type { PlanInfo } from "./types";

type PlanSeed = Omit<PlanInfo, "priceIRR"> & { priceIRR?: number };

const SEED: Record<string, PlanSeed> = {
  "ir-small": {
    id: "ir-small",
    label: "IR Small",
    cpu: 0.5,
    ramGb: 0.5,
    diskGb: 1,
    bandwidthGb: 50,
    description: "پلن اقتصادی دیتاسنتر ایران — مناسب تست و شروع",
  },
  "ir-medium": {
    id: "ir-medium",
    label: "IR Medium",
    cpu: 1,
    ramGb: 1,
    diskGb: 2.5,
    bandwidthGb: 100,
    description: "پلن استاندارد دیتاسنتر ایران — مناسب استارتاپ‌ها",
  },
  "standard-base": {
    id: "standard-base",
    label: "Standard Base",
    cpu: 1,
    ramGb: 2,
    diskGb: 5,
    bandwidthGb: 200,
    description: "پلن استاندارد پایه با ۲ گیگ رم برای فریم‌ورک‌های سنگین‌تر",
  },
  "standard-plus": {
    id: "standard-plus",
    label: "Standard Plus",
    cpu: 2,
    ramGb: 4,
    diskGb: 10,
    bandwidthGb: 400,
    description: "مناسب پروژه‌های با ترافیک متوسط و پروداکشن",
  },
  pro: {
    id: "pro",
    label: "Pro",
    cpu: 4,
    ramGb: 8,
    diskGb: 25,
    bandwidthGb: 800,
    description: "پلن حرفه‌ای برای بارهای کاری سنگین",
  },
  "pro-plus": {
    id: "pro-plus",
    label: "Pro Plus",
    cpu: 6,
    ramGb: 16,
    diskGb: 50,
    bandwidthGb: 1500,
    description: "بالاترین سطح سازمانی — پردازش‌های فشرده",
  },
  // Aliases
  micro: {
    id: "micro",
    label: "IR Small (Micro)",
    cpu: 0.5,
    ramGb: 0.5,
    diskGb: 1,
    bandwidthGb: 50,
    description: "مناسب تست و پروژه‌های شخصی کوچک",
  },
  small: {
    id: "small",
    label: "IR Medium (Small)",
    cpu: 1,
    ramGb: 1,
    diskGb: 2.5,
    bandwidthGb: 100,
    description: "مناسب پروژه‌های کوچک و استارتاپ‌ها",
  },
  medium: {
    id: "medium",
    label: "Standard Base (Medium)",
    cpu: 2,
    ramGb: 2,
    diskGb: 5,
    bandwidthGb: 200,
    description: "مناسب پروژه‌های متوسط با ترافیک معقول",
  },
};

// Monthly price in IRR (مقادیر تقریبی بازه ۱۴۰۴ — برای نمایش تخمینی)
const PRICE_IRR: Record<string, number> = {
  "ir-small": 390_000,
  "ir-medium": 790_000,
  "standard-base": 1_490_000,
  "standard-plus": 2_890_000,
  pro: 5_790_000,
  "pro-plus": 11_590_000,
  micro: 390_000,
  small: 790_000,
  medium: 1_490_000,
};

export const PLAN_CATALOG: Record<string, PlanInfo> = Object.fromEntries(
  Object.entries(SEED).map(([id, p]) => [id, { ...p, priceIRR: PRICE_IRR[id] ?? 0 }])
);

export const PLAN_ORDER = [
  "ir-small",
  "ir-medium",
  "standard-base",
  "standard-plus",
  "pro",
  "pro-plus",
];

export function getAllPlans(): PlanInfo[] {
  return PLAN_ORDER.map((id) => PLAN_CATALOG[id]);
}

export function getPlan(planId: string): PlanInfo | undefined {
  return PLAN_CATALOG[planId];
}

export function planLabel(planId: string): string {
  return PLAN_CATALOG[planId]?.label ?? planId;
}

export function formatPrice(irr: number): string {
  if (!irr) return "—";
  if (irr >= 1_000_000) return `${(irr / 1_000_000).toFixed(irr % 1_000_000 === 0 ? 0 : 2)} میلیون تومان`;
  return `${Math.round(irr / 10_000)} هزار تومان`;
}
