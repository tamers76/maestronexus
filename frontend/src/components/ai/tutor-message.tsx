import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { TutorResponse } from "@/lib/ai";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  meta?: Pick<
    TutorResponse,
    "grounded" | "refused" | "escalate" | "escalation_path" | "sources" | "stubbed" | "provider" | "model"
  >;
};

export function TutorMessage({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const meta = message.meta;

  return (
    <div className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "flex max-w-[85%] flex-col gap-2 rounded-2xl px-4 py-3 text-sm shadow-sm",
          isUser
            ? "bg-primary text-primary-foreground"
            : "border border-border bg-card text-card-foreground",
        )}
      >
        {!isUser && meta && (
          <div className="flex flex-wrap items-center gap-1.5">
            {meta.refused ? (
              <Badge variant="destructive">Refused</Badge>
            ) : meta.grounded ? (
              <Badge variant="success">Grounded</Badge>
            ) : (
              <Badge variant="warning">Ungrounded</Badge>
            )}
            {meta.stubbed && <Badge variant="outline">offline stub</Badge>}
            {meta.provider && meta.provider !== "guardrail" && (
              <span className="text-xs text-muted-foreground">
                {meta.provider}/{meta.model}
              </span>
            )}
          </div>
        )}

        <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>

        {!isUser && meta && meta.sources.length > 0 && (
          <div className="mt-1 flex flex-col gap-1.5 border-t border-border/60 pt-2">
            <span className="text-xs font-medium text-muted-foreground">
              Grounded in approved content
            </span>
            <ul className="flex flex-col gap-1">
              {meta.sources.map((s) => (
                <li key={s.content_item_id} className="text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">{s.title}</span> — {s.snippet}
                </li>
              ))}
            </ul>
          </div>
        )}

        {!isUser && meta?.escalate && (
          <div className="mt-1 flex items-center gap-2 border-t border-border/60 pt-2">
            <span className="text-xs text-muted-foreground">Need a human?</span>
            <Link
              href={meta.escalation_path}
              className={cn(buttonVariants({ variant: "outline", size: "xs" }))}
            >
              Escalate to a teacher
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
