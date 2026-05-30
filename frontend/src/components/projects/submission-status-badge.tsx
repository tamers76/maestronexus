import { Badge } from "@/components/ui/badge";

const VARIANTS: Record<string, "default" | "secondary" | "success" | "warning" | "outline"> = {
  submitted: "warning",
  graded: "success",
  resubmitted: "secondary",
};

export function SubmissionStatusBadge({ status }: { status: string }) {
  const variant = VARIANTS[status] ?? "outline";
  return <Badge variant={variant}>{status}</Badge>;
}
