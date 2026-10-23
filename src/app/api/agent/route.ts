import { NextRequest } from "next/server";
import { runAgentTurn } from "@/lib/liara/agent/engine";
import { getChatHistory, saveChatMessage } from "@/lib/liara/store";
import type { AgentSseEvent } from "@/lib/liara/types";

export const runtime = "nodejs";
export const maxDuration = 120;

export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as {
      sessionId: string;
      message: string;
    };
    if (!body.message?.trim()) {
      return Response.json({ error: "پیام خالی است" }, { status: 400 });
    }
    const sessionId = body.sessionId || "default";

    const history = await getChatHistory(sessionId, 10);
    await saveChatMessage({
      sessionId,
      role: "user",
      content: body.message,
    });

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        const emit = (e: AgentSseEvent) => {
          try {
            controller.enqueue(encoder.encode(`data: ${JSON.stringify(e)}\n\n`));
          } catch {
            /* closed */
          }
        };

        let finalText = "";
        try {
          await runAgentTurn(
            {
              sessionId,
              message: body.message,
               
              history: history.map((h) => ({ role: h.role, content: h.content })),
            },
            (e) => {
              if (e.type === "delta") finalText += e.text;
              emit(e);
            }
          );
        } catch (e) {
          emit({
            type: "error",
            message: e instanceof Error ? e.message : "خطای غیرمنتظره در موتور ایجنت",
          });
        }

        if (finalText.trim()) {
          try {
            await saveChatMessage({
              sessionId,
              role: "assistant",
              content: finalText,
            });
          } catch {
            /* non-fatal */
          }
        }
        emit({ type: "done", messageId: `msg_${Date.now()}` });
        controller.close();
      },
    });

    return new Response(stream, {
      headers: {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
      },
    });
  } catch (e) {
    return Response.json(
      { error: e instanceof Error ? e.message : "bad request" },
      { status: 500 }
    );
  }
}
