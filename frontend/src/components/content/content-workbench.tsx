"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ContentItemsPanel } from "@/components/content/content-items-panel";
import { MediaPanel } from "@/components/content/media-panel";
import { QuizBuilderPanel } from "@/components/content/quiz-builder-panel";

type Tab = "content" | "media" | "quiz";

const TABS: { key: Tab; label: string }[] = [
  { key: "content", label: "Content items" },
  { key: "media", label: "Media" },
  { key: "quiz", label: "Quiz builder" },
];

export function ContentWorkbench() {
  const [nodeInput, setNodeInput] = useState("");
  const [nodeId, setNodeId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("content");

  const loadNode = () => {
    const trimmed = nodeInput.trim();
    setNodeId(trimmed || null);
  };

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 py-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Content &amp; Assessment</h1>
        <p className="text-sm text-muted-foreground">
          Author content, upload media, and build quizzes attached to a learning node.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Learning node</CardTitle>
          <CardDescription>
            Paste the ID of the node you&apos;re authoring for. Content, media, and quizzes all
            attach to it.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-2">
            <div className="flex flex-1 flex-col gap-1.5">
              <Label htmlFor="node-id">Node ID</Label>
              <Input
                id="node-id"
                value={nodeInput}
                onChange={(e) => setNodeInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && loadNode()}
                placeholder="00000000-0000-0000-0000-000000000000"
                className="font-mono"
              />
            </div>
            <Button onClick={loadNode} disabled={!nodeInput.trim()}>
              Load
            </Button>
          </div>
        </CardContent>
      </Card>

      {nodeId ? (
        <>
          <div className="flex gap-1 rounded-lg border border-border bg-muted/40 p-1">
            {TABS.map((t) => (
              <Button
                key={t.key}
                size="sm"
                variant={tab === t.key ? "default" : "ghost"}
                onClick={() => setTab(t.key)}
                className="flex-1"
              >
                {t.label}
              </Button>
            ))}
          </div>

          {tab === "content" && <ContentItemsPanel key={nodeId} nodeId={nodeId} />}
          {tab === "media" && <MediaPanel />}
          {tab === "quiz" && <QuizBuilderPanel key={nodeId} nodeId={nodeId} />}
        </>
      ) : (
        <Card>
          <CardContent className="flex min-h-40 items-center justify-center">
            <p className="text-sm text-muted-foreground">
              Enter a learning node ID above to start authoring.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
