import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { NextNodeResponse } from "@/lib/adaptive";

/**
 * The adaptive engine's current recommendation. Always shows the human-readable
 * `reason`; flags teacher overrides; offers a "Start / Mark complete" action.
 */
export function NextNodeCard({
  rec,
  onComplete,
  busy,
}: {
  rec: NextNodeResponse | null;
  onComplete?: (nodeId: string) => void;
  busy?: boolean;
}) {
  return (
    <Card className="border-primary/30 bg-primary/5">
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">Recommended next</CardTitle>
          {rec?.source === "teacher_override" && (
            <Badge variant="warning">Teacher assigned</Badge>
          )}
          {rec?.source === "engine" && <Badge variant="secondary">Adaptive engine</Badge>}
        </div>
        <CardDescription>What to focus on right now.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {!rec ? (
          <p className="text-sm text-muted-foreground">Loading recommendation…</p>
        ) : rec.course_complete ? (
          <p className="text-sm font-medium text-emerald-600 dark:text-emerald-400">
            {rec.reason}
          </p>
        ) : rec.recommended_node_id ? (
          <>
            <div>
              <p className="font-medium">{rec.node_title}</p>
              <p className="mt-1 text-sm text-muted-foreground">{rec.reason}</p>
            </div>
            {onComplete && (
              <div>
                <Button
                  size="sm"
                  disabled={busy}
                  onClick={() => onComplete(rec.recommended_node_id!)}
                >
                  {busy ? "Saving…" : "Mark complete"}
                </Button>
              </div>
            )}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">{rec.reason}</p>
        )}
      </CardContent>
    </Card>
  );
}
