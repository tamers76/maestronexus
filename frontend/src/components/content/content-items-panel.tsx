"use client";

import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  type ApprovalStatus,
  type ContentItem,
  approveContentItem,
  createContentItem,
  listContentItems,
  updateContentItem,
} from "@/lib/content";

const MODALITIES = [
  "text",
  "video",
  "audio",
  "interactive",
  "simulation",
  "image",
  "slides",
  "external",
];

function statusVariant(status: ApprovalStatus) {
  if (status === "approved") return "success" as const;
  if (status === "in_review") return "warning" as const;
  if (status === "archived") return "secondary" as const;
  return "outline" as const;
}

function bodyToText(body: Record<string, unknown>): string {
  const md = body?.markdown;
  return typeof md === "string" ? md : "";
}

export function ContentItemsPanel({ nodeId }: { nodeId: string }) {
  const { hasPermission } = useAuth();
  const canApprove = hasPermission("content.ai_approve");

  const [items, setItems] = useState<ContentItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Editor state — `editingId === null` means "create new".
  const [editingId, setEditingId] = useState<string | null>(null);
  const [modality, setModality] = useState("text");
  const [bodyText, setBodyText] = useState("");
  const [saving, setSaving] = useState(false);

  // Fetch helper — only mutates state *after* an await so it's safe to call
  // from an effect (mirrors the foundation auth.tsx pattern).
  const fetchItems = useCallback(async () => {
    try {
      const page = await listContentItems(nodeId);
      setItems(page.items);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load content items");
    }
  }, [nodeId]);

  useEffect(() => {
    let active = true;
    (async () => {
      await fetchItems();
      if (active) setLoading(false);
    })();
    return () => {
      active = false;
    };
  }, [fetchItems]);

  const resetEditor = () => {
    setEditingId(null);
    setModality("text");
    setBodyText("");
  };

  const startEdit = (item: ContentItem) => {
    setEditingId(item.id);
    setModality(item.modality);
    setBodyText(bodyToText(item.body));
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const body = { markdown: bodyText };
      if (editingId) {
        await updateContentItem(editingId, { modality, body });
      } else {
        await createContentItem({ node_id: nodeId, modality, body });
      }
      resetEditor();
      await fetchItems();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save content item");
    } finally {
      setSaving(false);
    }
  };

  const approve = async (id: string) => {
    setError(null);
    try {
      await approveContentItem(id);
      await fetchItems();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to approve");
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle className="text-base">
            {editingId ? "Edit content item" : "New content item"}
          </CardTitle>
          <CardDescription>
            {editingId
              ? "Editing an approved item bumps its version and returns it to draft."
              : "Authored items start as a draft until approved."}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ci-modality">Modality</Label>
            <select
              id="ci-modality"
              value={modality}
              onChange={(e) => setModality(e.target.value)}
              className="flex h-9 w-full rounded-lg border border-border bg-background px-3 text-sm shadow-sm focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
            >
              {MODALITIES.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ci-body">Body (markdown)</Label>
            <Textarea
              id="ci-body"
              value={bodyText}
              onChange={(e) => setBodyText(e.target.value)}
              placeholder="# Lesson title&#10;&#10;Write the lesson content in markdown…"
              className="min-h-48 font-mono"
            />
          </div>
          <div className="flex items-center gap-2">
            <Button onClick={save} disabled={saving || !bodyText.trim()}>
              {saving ? "Saving…" : editingId ? "Save changes" : "Create draft"}
            </Button>
            {editingId && (
              <Button variant="ghost" onClick={resetEditor} disabled={saving}>
                Cancel
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="lg:col-span-3">
        <CardHeader>
          <CardTitle className="text-base">Content items</CardTitle>
          <CardDescription>Versioned items attached to this node.</CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <p className="mb-3 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}
          {loading ? (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
            </div>
          ) : items.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No content items yet for this node.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Modality</TableHead>
                  <TableHead>Version</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="font-medium">{item.modality}</TableCell>
                    <TableCell>v{item.version}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(item.approval_status)}>
                        {item.approval_status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1.5">
                        <Button size="xs" variant="outline" onClick={() => startEdit(item)}>
                          Edit
                        </Button>
                        {canApprove && item.approval_status !== "approved" && (
                          <Button size="xs" onClick={() => approve(item.id)}>
                            Approve
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
