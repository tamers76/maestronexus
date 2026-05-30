"use client";

import { ArrowRight, FileStack } from "lucide-react";

import { Badge } from "@/components/ui/badge";

/**
 * Structured viewers for the 18-stage Blueprint artifacts.
 *
 * Stage artifacts are free-form JSON whose shape varies per `output_kind`, so we
 * render them with a resilient recursive structured view (objects → labelled
 * sections, arrays → lists/cards, primitives inline) rather than a brittle
 * per-field form. `ApprovalImpact` previews what approving the run will promote
 * into the course (driven by the stage's `promotes_to`).
 */

// ── output_kind metadata (the 18 Blueprint stages) ────────────────────────────

export const OUTPUT_KIND_META: Record<string, { label: string }> = {
  course_contract: { label: "Course intake contract" },
  clo_review: { label: "CLO quality review" },
  assessment_blueprints: { label: "Assessment redesign" },
  rubrics: { label: "Rubric & weighting matrix" },
  integrity_checklist: { label: "AI integrity checklist" },
  subtopics: { label: "Subtopic architecture" },
  mastery_nodes: { label: "Mastery node design" },
  evidence_logic: { label: "Node evidence & readiness rules" },
  node_edges: { label: "Node relationship map" },
  companion_config: { label: "AI Companion configuration" },
  readiness_gates: { label: "Assessment readiness gates" },
  submission_template: { label: "Submission & evaluation template" },
  grading_template: { label: "Feedback & grading template" },
  contribution_template: { label: "Contribution preparation template" },
  verification_template: { label: "Verified contribution pathway" },
  credits_template: { label: "Mastery Credits design" },
  effort_map: { label: "Learning hours & effort map" },
  analytics_config: { label: "Analytics & continuous improvement" },
  artifact: { label: "Artifact" },
};

// ── promotes_to metadata (what approval writes into the domain) ────────────────

export const PROMOTES_TO_META: Record<string, { label: string; detail: string }> = {
  course_contract: {
    label: "Course contract",
    detail: "Course metadata, official CLOs, assessment evidence, and credit hours.",
  },
  learning_outcome: {
    label: "Course Learning Outcomes",
    detail: "Refined CLO statements and attributes (official wording preserved).",
  },
  contribution_assessment: {
    label: "Contribution assessments",
    detail: "Creates/updates formal contribution-assessment blueprints.",
  },
  course_subtopic: {
    label: "Course subtopics",
    detail: "Self-paced learning territories for the course version.",
  },
  learning_node: {
    label: "Learning nodes",
    detail: "Draft Mastery Nodes with mastery/completion (evidence) rules.",
  },
  node_dependency: {
    label: "Node relationships",
    detail: "Prerequisite, bridge, and dependency edges between nodes.",
  },
  course_config: {
    label: "Course configuration",
    detail: "Runtime configuration (AI Companion / analytics) for the version.",
  },
  workflow_template: {
    label: "Workflow template",
    detail: "Approved runtime workflow template for the learner/faculty surface.",
  },
  effort_map: {
    label: "Learning-hours effort map",
    detail: "Per-CLO/subtopic/node/assessment effort & accreditation equivalency.",
  },
};

function titleCase(key: string): string {
  return key
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

// ── Recursive structured renderer ─────────────────────────────────────────────

function Primitive({ value }: { value: unknown }) {
  if (value === null || value === undefined)
    return <span className="text-muted-foreground">—</span>;
  if (typeof value === "boolean")
    return <Badge variant={value ? "success" : "outline"}>{value ? "yes" : "no"}</Badge>;
  return <span className="break-words">{String(value)}</span>;
}

function ValueView({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-muted-foreground">none</span>;
    const allPrimitive = value.every(
      (v) => v === null || (typeof v !== "object" && typeof v !== "function"),
    );
    if (allPrimitive) {
      return (
        <ul className="flex flex-wrap gap-1.5">
          {value.map((v, i) => (
            <li key={i}>
              <Badge variant="secondary">{String(v)}</Badge>
            </li>
          ))}
        </ul>
      );
    }
    return (
      <ol className="flex flex-col gap-2">
        {value.map((v, i) => (
          <li
            key={i}
            className="rounded-lg border border-border/70 bg-muted/30 p-2.5 text-xs"
          >
            <span className="mb-1 block text-[11px] font-medium text-muted-foreground">
              #{i + 1}
            </span>
            <ValueView value={v} depth={depth + 1} />
          </li>
        ))}
      </ol>
    );
  }

  if (isPlainObject(value)) {
    return <ObjectView obj={value} depth={depth + 1} />;
  }

  return <Primitive value={value} />;
}

function ObjectView({
  obj,
  depth = 0,
}: {
  obj: Record<string, unknown>;
  depth?: number;
}) {
  const entries = Object.entries(obj);
  if (entries.length === 0)
    return <span className="text-muted-foreground">empty</span>;

  return (
    <dl className="flex flex-col gap-2.5">
      {entries.map(([key, value]) => {
        const nested = isPlainObject(value) || Array.isArray(value);
        return (
          <div
            key={key}
            className={nested ? "flex flex-col gap-1" : "grid grid-cols-[minmax(120px,0.5fr)_1fr] gap-2"}
          >
            <dt className="text-xs font-medium text-muted-foreground">{titleCase(key)}</dt>
            <dd className="min-w-0 text-sm">
              <ValueView value={value} depth={depth} />
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

/** Renders a stage artifact in a structured, human-readable layout. */
export function StageArtifactView({
  artifact,
  outputKind,
}: {
  artifact: unknown;
  outputKind?: string;
}) {
  const meta = outputKind ? OUTPUT_KIND_META[outputKind] : undefined;

  if (artifact === null || artifact === undefined) {
    return (
      <p className="text-xs text-muted-foreground">
        No structured artifact produced by this run.
      </p>
    );
  }

  return (
    <div className="rounded-lg border border-border p-3">
      <p className="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <FileStack className="size-3.5" />
        {meta?.label ?? "Structured artifact"}
        {outputKind && (
          <Badge variant="outline" className="font-mono">
            {outputKind}
          </Badge>
        )}
      </p>
      <div className="max-h-96 overflow-auto">
        <ValueView value={artifact} />
      </div>
    </div>
  );
}

/**
 * Preview of what approving a stage run will promote into the course. Driven by
 * the stage's `promotes_to` target + the structured artifact.
 */
export function ApprovalImpact({
  promotesTo,
  artifact,
}: {
  promotesTo: string | null;
  artifact: unknown;
}) {
  if (!promotesTo) {
    return (
      <div className="rounded-lg border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
        Approving records SME sign-off for this run. It does not promote into
        course domain state.
      </div>
    );
  }

  const meta = PROMOTES_TO_META[promotesTo] ?? {
    label: titleCase(promotesTo),
    detail: "Promotes this run's approved artifact into course domain state.",
  };

  // Best-effort count of the primary collection in the artifact for the preview.
  let summary: string | null = null;
  if (isPlainObject(artifact)) {
    const arrayEntry = Object.entries(artifact).find(([, v]) => Array.isArray(v));
    if (arrayEntry) {
      const [k, v] = arrayEntry as [string, unknown[]];
      summary = `${v.length} ${titleCase(k).toLowerCase()}`;
    }
  } else if (Array.isArray(artifact)) {
    summary = `${artifact.length} item(s)`;
  }

  return (
    <div className="rounded-lg border border-primary/30 bg-primary/5 p-3">
      <p className="mb-1 flex items-center gap-1.5 text-sm font-medium">
        <ArrowRight className="size-4 text-primary" />
        On approval, promotes to{" "}
        <Badge variant="default">{meta.label}</Badge>
      </p>
      <p className="text-xs text-muted-foreground">{meta.detail}</p>
      {summary && (
        <p className="mt-1.5 text-xs">
          <span className="font-medium">Preview:</span>{" "}
          <span className="text-muted-foreground">{summary} will be written.</span>
        </p>
      )}
    </div>
  );
}
