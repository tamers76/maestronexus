import { Badge } from "@/components/ui/badge";
import { READINESS_META, type ReadinessState } from "@/lib/blueprint";

/**
 * Blueprint readiness badge (not_ready → advanced). Shared across the learner
 * journey and the faculty roster. Tolerates unknown/legacy strings.
 */
export function ReadinessStateBadge({
  state,
}: {
  state: ReadinessState | string | null | undefined;
}) {
  if (!state) return <span className="text-xs text-muted-foreground">—</span>;
  const meta = READINESS_META[state as ReadinessState];
  if (!meta) return <Badge variant="outline">{state}</Badge>;
  return <Badge variant={meta.variant}>{meta.label}</Badge>;
}
