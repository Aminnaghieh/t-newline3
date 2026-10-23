// Plan recommender — direct port of core/planner.py heuristic matrix.
import type { AnalysisResult, PlanRecommendationResult } from "./types";
import { PLAN_ORDER, getPlan } from "./plans";

export function recommendPlan(analysis: AnalysisResult): PlanRecommendationResult {
  let recId = "ir-small";
  const reasons: string[] = [];

  const platform = analysis.platform.toLowerCase();
  const framework = (analysis.framework ?? "").toLowerCase();
  const sizeMb = analysis.projectSizeMb;
  const depCount = analysis.dependencies.length;

  let reqCpu = 0.5;
  let reqRam = 0.5;

  if (["django", "next", "nuxt", "rails", "spring"].includes(framework)) {
    recId = "ir-medium";
    reqCpu = 1;
    reqRam = 1;
    reasons.push(
      `فریم‌ورک «${framework}» برای بیلد و رانتایم به حداقل ۱ گیگابایت رم نیاز دارد`
    );
  } else if (["dotnet", "java", "rust"].includes(platform)) {
    recId = "ir-medium";
    reqCpu = 1;
    reqRam = 1;
    reasons.push(`پلتفرم «${platform}» برای فرآیند کامپایل به منابع بالاتری نیاز دارد`);
  }

  if (depCount > 40) {
    if (recId === "ir-small") {
      recId = "ir-medium";
      reqRam = 1;
      reasons.push(`تعداد وابستگی‌ها بالاست (${depCount} پکیج)`);
    } else if (recId === "ir-medium" && sizeMb > 50) {
      recId = "standard-base";
      reqCpu = 1;
      reqRam = 2;
      reasons.push("حجم پروژه و پکیج‌ها فراتر از پلن پایه است");
    }
  }

  if (sizeMb > 100) {
    recId = "standard-base";
    reqCpu = 1;
    reqRam = 2;
    reasons.push(`حجم پروژه ${sizeMb.toFixed(1)} مگابایت است و به دیسک و رم بیشتری نیاز دارد`);
  }

  if (!reasons.length) {
    reasons.push("پروژه سبک و بهینه است؛ پلن IR Small برای شروع کاملاً اقتصادی و کافی است");
  }

  const curIdx = PLAN_ORDER.indexOf(recId) >= 0 ? PLAN_ORDER.indexOf(recId) : 0;
  const alternatives: string[] = [];
  if (curIdx > 0) alternatives.push(PLAN_ORDER[curIdx - 1]);
  if (curIdx < PLAN_ORDER.length - 1) alternatives.push(PLAN_ORDER[curIdx + 1]);

  return {
    recommendedPlan: recId,
    reason: reasons.join(" • "),
    alternatives,
    estimatedRequirements: { cpuCores: reqCpu, ramGb: reqRam, projectSizeMb: sizeMb },
  };
}

export function comparePlans(currentPlan: string, targetPlan: string) {
  const curr = getPlan(currentPlan);
  const target = getPlan(targetPlan);
  return {
    current: curr ?? null,
    target: target ?? null,
    diff: {
      cpu: (target?.cpu ?? 0) - (curr?.cpu ?? 0),
      ramGb: (target?.ramGb ?? 0) - (curr?.ramGb ?? 0),
      diskGb: (target?.diskGb ?? 0) - (curr?.diskGb ?? 0),
      bandwidthGb: (target?.bandwidthGb ?? 0) - (curr?.bandwidthGb ?? 0),
      priceIRR: (target?.priceIRR ?? 0) - (curr?.priceIRR ?? 0),
    },
    isUpgrade:
      (target?.ramGb ?? 0) > (curr?.ramGb ?? 0) || (target?.cpu ?? 0) > (curr?.cpu ?? 0),
  };
}
