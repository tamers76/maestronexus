"use client";

import { Crown, Users } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { CouncilTranscript } from "@/lib/stages";

export function CouncilTranscriptView({
  transcript,
  finalText,
}: {
  transcript: CouncilTranscript;
  finalText?: string;
}) {
  const members = transcript.members ?? [];
  if (members.length === 0) return null;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 text-sm font-medium">
        <Users className="size-4 text-primary" />
        Council deliberation
        <Badge variant="secondary">{members.length} members</Badge>
      </div>
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
        {members.map((m, i) => (
          <div key={`${m.model}-${i}`} className="rounded-lg border border-border p-3">
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="text-xs font-medium">
                Member {i + 1} · {m.model}
              </span>
              {m.stubbed && <Badge variant="outline">stub</Badge>}
              {m.error && <Badge variant="destructive">failed</Badge>}
            </div>
            <pre className="max-h-48 overflow-auto whitespace-pre-wrap text-xs text-muted-foreground">
              {m.error ? m.error : m.text}
            </pre>
          </div>
        ))}
      </div>
      {finalText && (
        <div className="rounded-lg border border-primary/30 bg-primary/5 p-3">
          <div className="mb-1 flex items-center gap-2 text-xs font-medium">
            <Crown className="size-4 text-primary" />
            Chairman synthesis · {transcript.chairman_model}
          </div>
          <pre className="max-h-72 overflow-auto whitespace-pre-wrap text-xs">{finalText}</pre>
        </div>
      )}
    </div>
  );
}
