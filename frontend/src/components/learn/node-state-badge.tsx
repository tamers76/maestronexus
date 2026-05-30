import { Badge } from "@/components/ui/badge";
import type { NodeState } from "@/lib/enrollment";

const STATE_META: Record<
  NodeState,
  { label: string; variant: "default" | "secondary" | "outline" | "success" }
> = {
  locked: { label: "Locked", variant: "outline" },
  available: { label: "Available", variant: "secondary" },
  completed: { label: "Completed", variant: "success" },
  mastered: { label: "Mastered", variant: "default" },
};

export function NodeStateBadge({ state }: { state: NodeState }) {
  const meta = STATE_META[state] ?? STATE_META.locked;
  return <Badge variant={meta.variant}>{meta.label}</Badge>;
}
