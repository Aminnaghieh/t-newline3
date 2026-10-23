"""Plan recommender and resource mapping logic."""

from __future__ import annotations

from typing import Any

from liara_agent.core.analyzer import ProjectAnalysis
from liara_agent.models.plans import PlanInfo, PlanRecommendation, get_plan_by_id


class PlanRecommender:
    """Recommends optimal Liara plans based on analyzed project requirements."""

    def recommend(self, analysis: ProjectAnalysis) -> PlanRecommendation:
        """Recommend a plan based on framework, size, and dependencies."""
        rec_id = "ir-small"
        reasons: list[str] = []
        alternatives: list[str] = []

        platform = analysis.platform.lower()
        framework = (analysis.framework or "").lower()
        size_mb = analysis.project_size_mb
        dep_count = len(analysis.dependencies)

        # Base requirement estimation
        req_cpu = 0.5
        req_ram = 0.5

        # Heavy frameworks
        if framework in ("django", "next", "nuxt", "rails", "spring"):
            rec_id = "ir-medium"
            req_cpu = 1.0
            req_ram = 1.0
            reasons.append(f"فریم‌ورک '{framework}' نیاز به حداقل ۱ گیگابایت رم برای بیلد و رانتایم دارد")
        elif platform in ("dotnet", "java", "rust"):
            rec_id = "ir-medium"
            req_cpu = 1.0
            req_ram = 1.0
            reasons.append(f"پلتفرم '{platform}' برای فرآیند کامپایل به منابع بالاتری نیاز دارد")

        # Dependency scaling
        if dep_count > 40:
            if rec_id == "ir-small":
                rec_id = "ir-medium"
                req_ram = 1.0
                reasons.append(f"تعداد وابستگی‌ها بالاست ({dep_count} پکیج)")
            elif rec_id == "ir-medium" and size_mb > 50:
                rec_id = "standard-base"
                req_cpu = 1.0
                req_ram = 2.0
                reasons.append("حجم پروژه و پکیج‌ها فراتر از پلن پایه است")

        if size_mb > 100:
            rec_id = "standard-base"
            req_cpu = 1.0
            req_ram = 2.0
            reasons.append(f"حجم پروژه {size_mb:.1f}MB است و نیاز به دیسک و رم بیشتر دارد")

        if not reasons:
            reasons.append("پروژه سبک و بهینه است؛ پلن IR Small برای شروع کاملاً اقتصادی و کافی است")

        plan_order = ["ir-small", "ir-medium", "standard-base", "standard-plus", "pro", "pro-plus"]
        cur_idx = plan_order.index(rec_id) if rec_id in plan_order else 0
        if cur_idx > 0:
            alternatives.append(plan_order[cur_idx - 1])
        if cur_idx < len(plan_order) - 1:
            alternatives.append(plan_order[cur_idx + 1])

        return PlanRecommendation(
            recommended_plan=rec_id,
            reason=" | ".join(reasons),
            alternatives=alternatives,
            estimated_requirements={
                "cpu_cores": req_cpu,
                "ram_gb": req_ram,
                "project_size_mb": size_mb,
            },
        )

    def compare_plans(self, current_plan: str, target_plan: str) -> dict[str, Any]:
        """Compare two plans."""
        curr = get_plan_by_id(current_plan) or PlanInfo(
            id=current_plan, label=current_plan, cpu=0, ram_gb=0, disk_gb=0, bandwidth_gb=0, description=""
        )
        target = get_plan_by_id(target_plan) or PlanInfo(
            id=target_plan, label=target_plan, cpu=0, ram_gb=0, disk_gb=0, bandwidth_gb=0, description=""
        )

        return {
            "current": curr.model_dump(),
            "target": target.model_dump(),
            "diff": {
                "cpu": target.cpu - curr.cpu,
                "ram_gb": target.ram_gb - curr.ram_gb,
                "disk_gb": target.disk_gb - curr.disk_gb,
                "bandwidth_gb": target.bandwidth_gb - curr.bandwidth_gb,
            },
            "is_upgrade": (target.ram_gb > curr.ram_gb or target.cpu > curr.cpu),
        }
