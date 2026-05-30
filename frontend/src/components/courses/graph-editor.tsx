"use client";

import {
  Background,
  Controls,
  type Edge,
  type EdgeChange,
  MarkerType,
  MiniMap,
  type Node,
  type NodeChange,
  type OnConnect,
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  AlertTriangle,
  CheckCircle2,
  Lock,
  Plus,
  Rocket,
  Workflow,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { LearningNodeCard } from "@/components/courses/learning-node";
import { NodeInspector, type InspectorValues } from "@/components/courses/node-inspector";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import {
  type CourseVersion,
  type DependencyType,
  type GraphEdge as ApiGraphEdge,
  type GraphNode as ApiGraphNode,
  createDependency,
  createNode,
  deleteDependency,
  deleteNode,
  getGraph,
  publishVersion,
  updateNode,
} from "@/lib/courses";

type FlowNode = Node<{ label: string; nodeType: string; estimatedDuration: number | null }>;

const EDGE_COLORS: Record<DependencyType, string> = {
  requires: "#0ea5e9",
  mastery_gate: "#f59e0b",
};

function toFlowNode(n: ApiGraphNode): FlowNode {
  return {
    id: n.id,
    type: "learning",
    position: n.position,
    data: {
      label: n.data.label,
      nodeType: n.data.nodeType,
      estimatedDuration: n.data.estimatedDuration,
    },
  };
}

function styledEdge(
  id: string,
  source: string,
  target: string,
  dependencyType: DependencyType,
): Edge {
  const color = EDGE_COLORS[dependencyType];
  const isGate = dependencyType === "mastery_gate";
  return {
    id,
    source,
    target,
    type: "smoothstep",
    label: dependencyType.replace(/_/g, " "),
    animated: isGate,
    style: { stroke: color, strokeWidth: 2, strokeDasharray: isGate ? "6 4" : undefined },
    labelBgPadding: [4, 2],
    labelBgBorderRadius: 4,
    labelStyle: { fontSize: 10, fontWeight: 600, fill: color },
    markerEnd: { type: MarkerType.ArrowClosed, color },
    data: { dependencyType },
  };
}

function toFlowEdge(e: ApiGraphEdge): Edge {
  return styledEdge(e.id, e.source, e.target, e.data.dependencyType);
}

async function ignore404(p: Promise<unknown>): Promise<void> {
  try {
    await p;
  } catch (err) {
    if (!(err instanceof ApiError) || err.status !== 404) throw err;
  }
}

function GraphEditorInner({
  versionId,
  courseTitle,
}: {
  versionId: string;
  courseTitle?: string;
}) {
  const [nodes, setNodes] = useState<FlowNode[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [version, setVersion] = useState<CourseVersion | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [edgeType, setEdgeType] = useState<DependencyType>("requires");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const readOnly = version?.state === "published";

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const graph = await getGraph(versionId);
        if (active) {
          setVersion(graph.version);
          setNodes(graph.nodes.map(toFlowNode));
          setEdges(graph.edges.map(toFlowEdge));
          setSelectedId(null);
          setError(null);
        }
      } catch (err) {
        if (active)
          setError(err instanceof ApiError ? err.message : "Failed to load the graph.");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [versionId]);

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => setNodes((nds) => applyNodeChanges(changes, nds) as FlowNode[]),
    [],
  );
  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    [],
  );

  const onConnect = useCallback<OnConnect>(
    (connection) => {
      if (!connection.source || !connection.target) return;
      const type = edgeType;
      setError(null);
      void (async () => {
        try {
          const dep = await createDependency(versionId, {
            source_node_id: connection.source!,
            target_node_id: connection.target!,
            dependency_type: type,
          });
          setEdges((eds) =>
            addEdge(styledEdge(dep.id, dep.source_node_id, dep.target_node_id, type), eds),
          );
        } catch (err) {
          setError(
            err instanceof ApiError ? err.message : "Could not create that dependency.",
          );
        }
      })();
    },
    [versionId, edgeType],
  );

  const onEdgesDelete = useCallback((deleted: Edge[]) => {
    void (async () => {
      try {
        await Promise.all(deleted.map((e) => ignore404(deleteDependency(e.id))));
      } catch {
        /* keep canvas responsive; reload on next action if needed */
      }
    })();
  }, []);

  const onNodesDelete = useCallback(
    (deleted: Node[]) => {
      if (selectedId && deleted.some((n) => n.id === selectedId)) setSelectedId(null);
      void (async () => {
        try {
          await Promise.all(deleted.map((n) => ignore404(deleteNode(n.id))));
        } catch {
          /* node row may already be gone */
        }
      })();
    },
    [selectedId],
  );

  const onNodeDragStop = useCallback(
    (_: unknown, node: Node) => {
      void updateNode(node.id, { position: node.position }).catch(() => {
        /* best-effort position persistence */
      });
    },
    [],
  );

  const addNode = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const count = nodes.length;
      const position = {
        x: 120 + ((count * 56) % 520),
        y: 120 + Math.floor((count * 56) / 520) * 120,
      };
      const created = await createNode(versionId, {
        title: "New node",
        type: "lesson",
        position,
      });
      setNodes((nds) => [
        ...nds,
        {
          id: created.id,
          type: "learning",
          position: created.position,
          data: { label: created.title, nodeType: created.type, estimatedDuration: null },
        },
      ]);
      setSelectedId(created.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add the node.");
    } finally {
      setBusy(false);
    }
  }, [nodes.length, versionId]);

  const saveNode = useCallback(
    async (values: InspectorValues) => {
      if (!selectedId) return;
      setBusy(true);
      setError(null);
      try {
        const updated = await updateNode(selectedId, {
          title: values.title,
          type: values.type,
          estimated_duration: values.estimated_duration,
        });
        setNodes((nds) =>
          nds.map((n) =>
            n.id === selectedId
              ? {
                  ...n,
                  data: {
                    label: updated.title,
                    nodeType: updated.type,
                    estimatedDuration: updated.estimated_duration,
                  },
                }
              : n,
          ),
        );
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Could not save the node.");
      } finally {
        setBusy(false);
      }
    },
    [selectedId],
  );

  const deleteSelected = useCallback(async () => {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      await ignore404(deleteNode(selectedId));
      setNodes((nds) => nds.filter((n) => n.id !== selectedId));
      setEdges((eds) =>
        eds.filter((e) => e.source !== selectedId && e.target !== selectedId),
      );
      setSelectedId(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete the node.");
    } finally {
      setBusy(false);
    }
  }, [selectedId]);

  const publish = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const updated = await publishVersion(versionId);
      setVersion(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not publish this version.");
    } finally {
      setBusy(false);
    }
  }, [versionId]);

  const nodeTypes = useMemo(() => ({ learning: LearningNodeCard }), []);
  const selectedNode = nodes.find((n) => n.id === selectedId) ?? null;

  if (loading) {
    return (
      <div className="flex h-full flex-col gap-3 p-4">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="flex-1" />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2 border-b border-border bg-card px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Workflow className="size-4 text-muted-foreground" />
          <span className="text-sm font-semibold">
            {courseTitle ?? "Learning graph"}
          </span>
          {version && (
            <Badge variant={readOnly ? "success" : "secondary"}>
              v{version.version} · {version.state}
            </Badge>
          )}
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-2">
          {!readOnly && (
            <>
              <div className="flex items-center rounded-lg border border-border p-0.5">
                <button
                  type="button"
                  onClick={() => setEdgeType("requires")}
                  className={
                    "rounded-md px-2 py-1 text-xs font-medium transition-colors " +
                    (edgeType === "requires"
                      ? "bg-sky-500/15 text-sky-600 dark:text-sky-400"
                      : "text-muted-foreground hover:text-foreground")
                  }
                >
                  requires
                </button>
                <button
                  type="button"
                  onClick={() => setEdgeType("mastery_gate")}
                  className={
                    "rounded-md px-2 py-1 text-xs font-medium transition-colors " +
                    (edgeType === "mastery_gate"
                      ? "bg-amber-500/15 text-amber-600 dark:text-amber-400"
                      : "text-muted-foreground hover:text-foreground")
                  }
                >
                  mastery gate
                </button>
              </div>
              <Button size="sm" variant="outline" onClick={addNode} disabled={busy}>
                <Plus /> Add node
              </Button>
              <Button size="sm" onClick={publish} disabled={busy || nodes.length === 0}>
                <Rocket /> Publish
              </Button>
            </>
          )}
          {readOnly && (
            <Badge variant="outline">
              <Lock className="size-3" /> Published · read-only
            </Badge>
          )}
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 border-b border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <span className="flex-1">{error}</span>
          <button type="button" onClick={() => setError(null)} aria-label="Dismiss">
            <X className="size-4" />
          </button>
        </div>
      )}

      {/* Canvas + inspector */}
      <div className="relative flex min-h-0 flex-1">
        <div className="min-h-0 flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onEdgesDelete={onEdgesDelete}
            onNodesDelete={onNodesDelete}
            onNodeDragStop={onNodeDragStop}
            onNodeClick={(_, node) => setSelectedId(node.id)}
            onPaneClick={() => setSelectedId(null)}
            nodesDraggable={!readOnly}
            nodesConnectable={!readOnly}
            elementsSelectable
            deleteKeyCode={readOnly ? null : ["Backspace", "Delete"]}
            fitView
            proOptions={{ hideAttribution: true }}
            className="bg-muted/20"
          >
            <Background gap={16} />
            <Controls showInteractive={false} />
            <MiniMap pannable zoomable className="!bg-card" />
          </ReactFlow>

          {nodes.length === 0 && (
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
              <div className="rounded-lg border border-dashed border-border bg-card/80 px-6 py-4 text-center text-sm text-muted-foreground">
                {readOnly
                  ? "This published version has no nodes."
                  : "Empty canvas — click \u201cAdd node\u201d to begin building the graph."}
              </div>
            </div>
          )}
        </div>

        {/* Inspector */}
        <aside className="hidden w-72 shrink-0 overflow-y-auto border-l border-border bg-card p-4 lg:block">
          {selectedNode && !readOnly ? (
            <>
              <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Node properties
              </p>
              <NodeInspector
                key={selectedNode.id}
                initial={{
                  title: selectedNode.data.label,
                  type: selectedNode.data.nodeType,
                  estimated_duration: selectedNode.data.estimatedDuration,
                }}
                disabled={readOnly}
                saving={busy}
                onSave={saveNode}
                onDelete={deleteSelected}
              />
            </>
          ) : (
            <div className="space-y-3 text-sm text-muted-foreground">
              <p className="flex items-center gap-2 font-medium text-foreground">
                <CheckCircle2 className="size-4" /> How to build
              </p>
              <ul className="list-disc space-y-1.5 pl-4">
                <li>Add nodes, then drag from a node&apos;s right handle to another&apos;s left to connect.</li>
                <li>Pick <span className="font-medium">requires</span> or <span className="font-medium">mastery gate</span> before drawing an edge.</li>
                <li>Cycles are rejected automatically.</li>
                <li>Click a node to edit it here; positions save as you drag.</li>
                <li>Publish to lock this version for enrollment.</li>
              </ul>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

export function GraphEditor(props: { versionId: string; courseTitle?: string }) {
  return (
    <ReactFlowProvider>
      <GraphEditorInner {...props} />
    </ReactFlowProvider>
  );
}
