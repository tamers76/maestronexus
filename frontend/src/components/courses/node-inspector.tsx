"use client";

import { Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NODE_TYPES } from "@/lib/courses";

export type InspectorValues = {
  title: string;
  type: string;
  estimated_duration: number | null;
};

export function NodeInspector({
  initial,
  disabled,
  saving,
  onSave,
  onDelete,
}: {
  initial: InspectorValues;
  disabled: boolean;
  saving: boolean;
  onSave: (values: InspectorValues) => void;
  onDelete: () => void;
}) {
  // Parent supplies a stable `key` per node, so initial values seed state once.
  const [title, setTitle] = useState(initial.title);
  const [type, setType] = useState(initial.type);
  const [duration, setDuration] = useState<string>(
    initial.estimated_duration != null ? String(initial.estimated_duration) : "",
  );

  function submit(e: React.FormEvent) {
    e.preventDefault();
    onSave({
      title: title.trim() || "Untitled node",
      type,
      estimated_duration: duration.trim() === "" ? null : Math.max(0, Number(duration) || 0),
    });
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="node-title">Title</Label>
        <Input
          id="node-title"
          value={title}
          disabled={disabled}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Intro to Variables"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="node-type">Type</Label>
        <select
          id="node-type"
          value={type}
          disabled={disabled}
          onChange={(e) => setType(e.target.value)}
          className="flex h-9 w-full rounded-lg border border-border bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
        >
          {NODE_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="node-duration">Estimated duration (min)</Label>
        <Input
          id="node-duration"
          type="number"
          min={0}
          value={duration}
          disabled={disabled}
          onChange={(e) => setDuration(e.target.value)}
          placeholder="optional"
        />
      </div>

      <div className="mt-1 flex items-center justify-between gap-2">
        <Button type="submit" size="sm" disabled={disabled || saving}>
          {saving ? "Saving…" : "Save node"}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="destructive"
          disabled={disabled || saving}
          onClick={onDelete}
        >
          <Trash2 /> Delete
        </Button>
      </div>
    </form>
  );
}
