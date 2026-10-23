"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { AgentSseEvent, ActionProposal, ChatHistoryItem } from "@/lib/liara/types";
import { ProposalCard, type ProposalState } from "./proposal-card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Send, Trash2, Bot, User, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useToast } from "@/hooks/use-toast";

interface ToolChip {
  id: string;
  label: string;
  summary: string;
  expanded: boolean;
}

interface UiMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  status?: string;
  tools?: ToolChip[];
  proposals?: ActionProposal[];
  resolved?: Record<string, ProposalState>;
}

const QUICK_PROMPTS = [
  { icon: "🩺", text: "وضعیت همه پروژه‌هام رو بگو" },
  { icon: "🔍", text: "چرا orders-api خطا می‌ده؟ عیب‌یابی کن" },
  { icon: "📈", text: "مصرف رم orders-api در یک ساعت گذشته چقدره؟" },
  { icon: "💰", text: "برای یه فروشگاه Next.js کدوم پلن لیارا مناسب‌تره؟" },
  { icon: "🔄", text: "می‌خوام shop-front رو ری‌استارت کنم" },
  { icon: "🚀", text: "نحوه دیپلوی روی لیارا رو توضیح بده" },
];

function summariseTool(result: unknown): string {
   
  const r = result as any;
  if (!r) return "";
  if (r.count !== undefined && r.projects) return `${r.count} پروژه یافت شد`;
  if (r.summary && r.metric) return `${r.metric}: avg ${r.summary.avg}${r.unit === "%" ? "٪" : ""} / p95 ${r.summary.p95}`;
  if (r.errorCount !== undefined) return `${r.errorCount} خطا، ${r.warnCount} هشدار`;
  if (r.diagnosis) return `احتمال اصلی: ${(r.diagnosis.hypotheses?.[0]?.probability ?? 0) * 100 | 0}٪`;
  if (r.recommended) return `پیشنهاد: ${r.recommended.label}`;
  if (r.proposal) return `کارت تایید ایجاد شد`;
  if (r.results) return `${r.results.length} نتیجه از دانش‌نامه`;
  if (r.status) return `وضعیت: ${r.status}`;
  if (r.ok) return "اتصال برقرار";
  return "انجام شد";
}

export function AgentChat() {
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [sessionId, setSessionId] = useState("default");
  const [demo, setDemo] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();

  useEffect(() => {
    let sid = localStorage.getItem("liara-agent-session");
    if (!sid) {
      sid = `s_${Math.random().toString(36).slice(2, 10)}`;
      localStorage.setItem("liara-agent-session", sid);
    }
    setSessionId(sid);
    fetch(`/api/chat/history?sessionId=${sid}`)
      .then((r) => r.json())
      .then((d) => {
        if (d.history?.length) {
          setMessages(
             
            d.history.map((h: any, i: number) => ({
              id: h.id ?? `h${i}`,
              role: h.role,
              content: h.content,
            }))
          );
          setTimeout(scrollDown, 60);
        }
      })
      .catch(() => {});
    fetch("/api/projects")
      .then((r) => r.json())
      .then((d) => setDemo(Boolean(d.demo)))
      .catch(() => {});
  }, []);

  const scrollDown = useCallback((smooth = true) => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? "smooth" : "auto" });
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < 260;
    if (near) scrollDown(false);
  }, [messages, scrollDown]);

  const send = async (text?: string) => {
    const msg = (text ?? input).trim();
    if (!msg || busy) return;
    setInput("");
    setBusy(true);

    const userMsg: UiMessage = { id: `u${Date.now()}`, role: "user", content: msg };
    const botId = `a${Date.now()}`;
    const botMsg: UiMessage = { id: botId, role: "assistant", content: "", streaming: true, tools: [] };
    setMessages((m) => [...m, userMsg, botMsg]);

    try {
      const res = await fetch("/api/agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId, message: msg }),
      });
      if (!res.body) throw new Error("no stream");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      let acc = "";

      const patch = (fn: (m: UiMessage) => UiMessage) =>
        setMessages((ms) => ms.map((m) => (m.id === botId ? fn(m) : m)));

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          let evt: AgentSseEvent;
          try {
            evt = JSON.parse(line.slice(5).trim());
          } catch {
            continue;
          }
          if (evt.type === "status") {
            patch((m) => ({ ...m, status: evt.type === "status" ? evt.label : undefined }));
          } else if (evt.type === "tool") {
            if (evt.type !== "tool") continue;
            patch((m) => ({
              ...m,
              status: undefined,
              tools: [
                ...(m.tools ?? []),
                {
                  id: `${evt.tool}-${Date.now()}`,
                  label: evt.label,
                  summary: summariseTool(evt.result),
                  expanded: false,
                },
              ],
            }));
          } else if (evt.type === "delta") {
            acc += evt.text;
            patch((m) => ({ ...m, content: acc, status: undefined }));
          } else if (evt.type === "proposal") {
            patch((m) => ({
              ...m,
              proposals: [...(m.proposals ?? []), evt.type === "proposal" ? evt.proposal : null].filter(
                Boolean
              ) as ActionProposal[],
            }));
          } else if (evt.type === "error") {
            toast({ title: "خطای ایجنت", description: evt.message, variant: "destructive" });
          }
        }
      }
      patch((m) => ({ ...m, streaming: false, status: undefined }));
    } catch {
      setMessages((ms) =>
        ms.map((m) =>
          m.id === botId
            ? { ...m, streaming: false, content: m.content || "⚠️ ارتباط با موتور ایجنت برقرار نشد." }
            : m
        )
      );
    } finally {
      setBusy(false);
    }
  };

  const clearChat = async () => {
    setMessages([]);
    await fetch(`/api/chat/history?sessionId=${sessionId}`, { method: "DELETE" });
  };

  const onProposalResolved = (botId: string, proposalId: string, state: ProposalState, message: string) => {
    setMessages((ms) =>
      ms.map((m) =>
        m.id === botId
          ? {
              ...m,
              resolved: { ...(m.resolved ?? {}), [proposalId]: state },
              content: state === "success" ? `${m.content}\n\n---\n✅ ${message}` : m.content,
            }
          : m
      )
    );
  };

  return (
    <div className="flex h-[calc(100vh-190px)] min-h-[540px] flex-col rounded-2xl border border-white/8 bg-[#1d231f]/60 backdrop-blur">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/6 px-4 py-3">
        <div className="flex items-center gap-2.5">
          <span className="relative flex size-9 items-center justify-center rounded-xl liara-gradient text-[#0e1512]">
            <Bot className="size-5" />
          </span>
          <div>
            <div className="text-[14px] font-extrabold">سوپر ایجنت لیارا</div>
            <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <span className={cn("size-1.5 rounded-full", busy ? "bg-[#ffc000] pulse-dot" : "bg-[#87fcc4]")} />
              {busy ? "در حال پردازش..." : "آنلاین — آماده کمک"}
              {demo && <span className="text-[#ffc000]/80">• دمو</span>}
            </div>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={clearChat}
          className="text-muted-foreground hover:bg-white/5 hover:text-[#ff6b6b]"
        >
          <Trash2 className="size-4" />
          گفتگوی جدید
        </Button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
            <div className="flex size-16 items-center justify-center rounded-2xl liara-gradient text-3xl text-[#0e1512]">
              🛡
            </div>
            <div>
              <div className="text-lg font-extrabold">سلام! من سوپر ایجنت لیارام 🤖</div>
              <p className="mt-1 max-w-md text-[13px] leading-6 text-muted-foreground">
                مهندس SRE اختصاصی تو روی پلتفرم ابری لیارا. وضعیت سرویس‌ها رو بپرس، خطاها رو عیب‌یابی کن،
                پلن مناسب بگیر یا عملیات‌ها رو با تایید خودت اجرا کنم.
              </p>
            </div>
            <div className="grid w-full max-w-xl grid-cols-1 gap-2 sm:grid-cols-2">
              {QUICK_PROMPTS.map((q) => (
                <button
                  key={q.text}
                  onClick={() => send(q.text)}
                  className="group flex items-center gap-2.5 rounded-xl border border-white/8 bg-white/3 px-3.5 py-2.5 text-right text-[12.5px] transition-all hover:border-[#87fcc4]/35 hover:bg-[#87fcc4]/6"
                >
                  <span className="text-base">{q.icon}</span>
                  <span className="flex-1 text-muted-foreground group-hover:text-foreground">{q.text}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) => (
          <div key={m.id} className={cn("flex gap-3", m.role === "user" && "flex-row-reverse")}>
            <span
              className={cn(
                "mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg",
                m.role === "user" ? "bg-white/8 text-foreground" : "liara-gradient text-[#0e1512]"
              )}
            >
              {m.role === "user" ? <User className="size-4" /> : <Bot className="size-4" />}
            </span>
            <div className={cn("min-w-0 max-w-[86%] flex-1", m.role === "user" && "flex flex-col items-end")}>
              {m.role === "user" ? (
                <div className="w-fit max-w-full rounded-2xl rounded-tr-sm bg-[#26302a] px-4 py-2.5 text-[13.5px] leading-7">
                  {m.content}
                </div>
              ) : (
                <div className="w-full space-y-2.5">
                  {/* status chip */}
                  {m.streaming && m.status && (
                    <div className="inline-flex items-center gap-2 rounded-full border border-[#28c1f5]/25 bg-[#28c1f5]/8 px-3 py-1 text-[11.5px] font-bold text-[#28c1f5]">
                      <Loader2 className="size-3 animate-spin" />
                      {m.status}
                    </div>
                  )}
                  {/* tool chips */}
                  {m.tools?.map((t) => (
                    <div
                      key={t.id}
                      className="flex items-center gap-2 rounded-lg border border-white/8 bg-white/3 px-3 py-1.5 text-[11.5px]"
                    >
                      <span className="text-[#87fcc4]">⚙︎</span>
                      <span className="font-bold text-[#d0e0ef]">{t.label}</span>
                      <span className="text-muted-foreground">— {t.summary}</span>
                    </div>
                  ))}
                  {/* answer */}
                  {(m.content || m.streaming) && (
                    <div
                      className={cn(
                        "chat-md rounded-2xl rounded-ts-sm border border-white/8 bg-[#202723]/80 px-4 py-3 text-[13.5px]",
                        m.streaming && !m.content && "py-3.5"
                      )}
                    >
                      {m.content ? (
                        <>
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                          {m.streaming && <span className="type-caret" />}
                        </>
                      ) : (
                        <span className="flex items-center gap-1.5 py-1">
                          <span className="thinking-dot size-2 rounded-full bg-[#87fcc4]" />
                          <span className="thinking-dot size-2 rounded-full bg-[#87fcc4]" />
                          <span className="thinking-dot size-2 rounded-full bg-[#87fcc4]" />
                        </span>
                      )}
                    </div>
                  )}
                  {/* proposals */}
                  {m.proposals?.map((p) => (
                    <ProposalCard
                      key={p.proposalId}
                      proposal={p}
                      onResolved={(state, msg) => onProposalResolved(m.id, p.proposalId, state, msg)}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Input */}
      <div className="border-t border-white/6 p-3.5">
        <div className="flex items-end gap-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder="سوالت رو بپرس… مثلاً: چرا اپم OOM می‌خوره؟"
            className="min-h-[52px] max-h-32 resize-none border-white/10 bg-[#161b18] text-[13.5px] focus-visible:ring-[#87fcc4]/40"
            rows={1}
          />
          <Button
            onClick={() => send()}
            disabled={busy || !input.trim()}
            size="icon"
            className="liara-gradient size-[52px] shrink-0 text-[#0e1512] hover:opacity-90 disabled:opacity-40"
            aria-label="ارسال"
          >
            {busy ? <Loader2 className="size-5 animate-spin" /> : <Send className="size-5 -scale-x-100" />}
          </Button>
        </div>
        <div className="mt-2 text-center text-[10.5px] text-muted-foreground/60">
          عملیات پرریسک فقط با تایید شما اجرا می‌شود • Shift+Enter برای خط جدید
        </div>
      </div>
    </div>
  );
}
