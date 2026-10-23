import { NextRequest } from "next/server";
import { saveChatMessage, getChatHistory, clearChatHistory } from "@/lib/liara/store";

export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  const sessionId = req.nextUrl.searchParams.get("sessionId") ?? "default";
  const history = await getChatHistory(sessionId, 60);
  return Response.json({ history });
}

export async function DELETE(req: NextRequest) {
  const sessionId = req.nextUrl.searchParams.get("sessionId") ?? "default";
  await clearChatHistory(sessionId);
  return Response.json({ ok: true });
}

export async function POST(req: NextRequest) {
  // Used by the client to persist assistant messages containing proposals
  const body = (await req.json()) as {
    sessionId: string;
    role: "user" | "assistant";
    content: string;
    payload?: unknown;
  };
  if (!body.content?.trim()) return Response.json({ ok: false }, { status: 400 });
  const msg = await saveChatMessage({
    sessionId: body.sessionId || "default",
    role: body.role,
    content: body.content,
    payload: body.payload,
  });
  return Response.json({ ok: true, id: msg.id });
}
