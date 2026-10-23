import { testConnection } from "@/lib/liara/client";

export const runtime = "nodejs";

export async function GET() {
  const result = await testConnection();
  return Response.json(result);
}
