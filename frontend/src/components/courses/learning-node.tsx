"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Clock } from "lucide-react";

import { cn } from "@/lib/utils";

export type LearningNodeData = {
  label: string;
  nodeType: string;
  estimatedDuration: number | null;
};

/** Accent color per node-type family (docs/04 taxonomy). */
function accentFor(nodeType: string): string {
  if (nodeType.includes("mastery") || nodeType === "assessment")
    return "border-l-amber-500";
  if (nodeType === "remediation") return "border-l-rose-500";
  if (nodeType === "enrichment") return "border-l-violet-500";
  if (["quiz", "assignment", "project", "lab", "practice"].includes(nodeType))
    return "border-l-emerald-500";
  return "border-l-sky-500";
}

const handleClass =
  "!h-3 !w-3 !border-2 !border-background !bg-muted-foreground transition-colors hover:!bg-primary";

export function LearningNodeCard({ data, selected }: NodeProps) {
  const d = data as unknown as LearningNodeData;
  return (
    <div
      className={cn(
        "min-w-44 max-w-56 rounded-lg border border-l-4 bg-card px-3 py-2 shadow-sm transition-all",
        accentFor(d.nodeType),
        selected
          ? "border-ring ring-3 ring-ring/40"
          : "border-border hover:shadow-md",
      )}
    >
      <Handle type="target" position={Position.Left} className={handleClass} />
      <p className="truncate text-sm font-medium text-foreground" title={d.label}>
        {d.label || "Untitled node"}
      </p>
      <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
        <span className="rounded bg-muted px-1.5 py-0.5 font-medium capitalize">
          {d.nodeType.replace(/_/g, " ")}
        </span>
        {typeof d.estimatedDuration === "number" && (
          <span className="inline-flex items-center gap-0.5">
            <Clock className="size-3" />
            {d.estimatedDuration}m
          </span>
        )}
      </div>
      <Handle type="source" position={Position.Right} className={handleClass} />
    </div>
  );
}
