import { listAudit } from "@/lib/liara/store";

export const runtime = "nodejs";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const limit = Math.min(Number(url.searchParams.get("limit") ?? 100), 300);
  const events = await listAudit(limit);
  return Response.json({ events });
}
