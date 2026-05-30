"use client";

import type { ModelOption } from "@/lib/settings";
import { cn } from "@/lib/utils";

/** Single-model dropdown. Always includes the current value even if not listed. */
export function ModelSelect({
  value,
  options,
  onChange,
  placeholder = "Use default",
  id,
}: {
  value: string | undefined;
  options: ModelOption[];
  onChange: (v: string) => void;
  placeholder?: string;
  id?: string;
}) {
  const ids = new Set(options.map((o) => o.id));
  const extra = value && !ids.has(value) ? [{ id: value, name: value }] : [];
  return (
    <select
      id={id}
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value)}
      className={cn(
        "flex h-9 w-full rounded-lg border border-border bg-background px-3 py-1 text-sm shadow-sm",
        "focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
      )}
    >
      <option value="">{placeholder}</option>
      {[...extra, ...options].map((o) => (
        <option key={o.id} value={o.id}>
          {o.name}
        </option>
      ))}
    </select>
  );
}

/** Multi-model checkbox list, with any custom values rendered alongside. */
export function ModelMultiSelect({
  values,
  options,
  onChange,
}: {
  values: string[];
  options: ModelOption[];
  onChange: (v: string[]) => void;
}) {
  const all = new Map<string, string>();
  options.forEach((o) => all.set(o.id, o.name));
  values.forEach((v) => {
    if (!all.has(v)) all.set(v, v);
  });
  const toggle = (id: string) => {
    if (values.includes(id)) onChange(values.filter((v) => v !== id));
    else onChange([...values, id]);
  };
  const entries = [...all.entries()];
  if (entries.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No models available. Add an API key and Test Connection to load models.
      </p>
    );
  }
  return (
    <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
      {entries.map(([id, name]) => {
        const checked = values.includes(id);
        return (
          <label
            key={id}
            className={cn(
              "flex cursor-pointer items-center gap-2 rounded-lg border px-2.5 py-1.5 text-sm transition-colors",
              checked ? "border-ring bg-muted/50" : "border-border hover:bg-muted/40",
            )}
          >
            <input
              type="checkbox"
              checked={checked}
              onChange={() => toggle(id)}
              className="size-3.5 accent-[var(--primary)]"
            />
            <span className="truncate">{name}</span>
          </label>
        );
      })}
    </div>
  );
}
