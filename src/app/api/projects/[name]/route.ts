import { NextRequest } from "next/server";
import { getProjectDetail } from "@/lib/liara/client";

export const runtime = "nodejs";

export async function GET(
  _req: NextRequest,
  ctx: { params: Promise<{ name: string }> }
) {
  try {
    const { name } = await ctx.params;
    const { project, demo } = await getProjectDetail(name);
    return Response.json({ project, demo });
  } catch (e) {
    return Response.json(
      { error: e instanceof Error ? e.message : "پروژه یافت نشد" },
      { status: 404 }
    );
  }
}
