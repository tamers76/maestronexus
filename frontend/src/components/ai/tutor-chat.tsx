"use client";

import { useEffect, useRef, useState } from "react";

import { TutorMessage, type ChatMessage } from "@/components/ai/tutor-message";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { askTutor } from "@/lib/ai";
import { ApiError } from "@/lib/api";

const SUGGESTIONS = [
  "Explain this concept in simple terms.",
  "Give me a worked example I can follow.",
  "What should I review before the next node?",
];

let messageCounter = 0;
function nextId(): string {
  messageCounter += 1;
  return `m${messageCounter}-${Date.now()}`;
}

export function TutorChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [nodeId, setNodeId] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending) return;

    setError(null);
    setQuestion("");
    const userMessage: ChatMessage = { id: nextId(), role: "user", content: trimmed };
    setMessages((prev) => [...prev, userMessage]);
    setSending(true);

    try {
      const res = await askTutor({
        question: trimmed,
        node_id: nodeId.trim() || null,
      });
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: "assistant",
          content: res.answer,
          meta: {
            grounded: res.grounded,
            refused: res.refused,
            escalate: res.escalate,
            escalation_path: res.escalation_path,
            sources: res.sources,
            stubbed: res.stubbed,
            provider: res.provider,
            model: res.model,
          },
        },
      ]);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "The tutor is unavailable right now. Try again.",
      );
    } finally {
      setSending(false);
    }
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    void send(question);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send(question);
    }
  }

  return (
    <div className="flex h-[calc(100vh-12rem)] min-h-[28rem] flex-col gap-4">
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto rounded-xl border border-border bg-muted/20 p-4"
      >
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
            <div className="max-w-md">
              <p className="text-sm font-medium text-foreground">
                Ask anything about your approved course material.
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                The tutor answers grounded in approved content, won&apos;t reveal graded
                assessment answers, and can escalate to a teacher.
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <Button
                  key={s}
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => void send(s)}
                >
                  {s}
                </Button>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {messages.map((m) => (
              <TutorMessage key={m.id} message={m} />
            ))}
            {sending && (
              <div className="flex justify-start">
                <div className="rounded-2xl border border-border bg-card px-4 py-3 text-sm text-muted-foreground">
                  <span className="inline-flex items-center gap-1">
                    Thinking
                    <span className="animate-pulse">…</span>
                  </span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <form onSubmit={onSubmit} className="flex flex-col gap-2">
        <div className="flex items-end gap-2">
          <div className="flex flex-1 flex-col gap-1.5">
            <Textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Ask the tutor a question… (Enter to send, Shift+Enter for a new line)"
              className="min-h-12 resize-none"
              disabled={sending}
            />
          </div>
          <Button type="submit" disabled={sending || !question.trim()} className="h-12 px-5">
            Send
          </Button>
        </div>
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer select-none">Optional context</summary>
          <div className="mt-2 flex max-w-sm flex-col gap-1.5">
            <Label htmlFor="tutor-node-id" className="text-xs">
              Learning node ID
            </Label>
            <Input
              id="tutor-node-id"
              value={nodeId}
              onChange={(e) => setNodeId(e.target.value)}
              placeholder="Scope answers to a specific node (UUID)"
            />
          </div>
        </details>
      </form>
    </div>
  );
}
