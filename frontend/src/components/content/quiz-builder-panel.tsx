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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import {
  type Assessment,
  type AssessmentDetail,
  type Question,
  addQuestion,
  createAssessment,
  deleteQuestion,
  getAssessment,
  listAssessments,
} from "@/lib/content";

const OPTION_IDS = ["a", "b", "c", "d", "e", "f"];

function optionText(q: Question, id: string): string {
  const options = (q.prompt?.options as { id: string; text: string }[]) ?? [];
  return options.find((o) => o.id === id)?.text ?? id;
}

export function QuizBuilderPanel({ nodeId }: { nodeId: string }) {
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [selected, setSelected] = useState<AssessmentDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // New-assessment + new-question form state.
  const [newTitle, setNewTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [options, setOptions] = useState<string[]>(["", ""]);
  const [correct, setCorrect] = useState(0);
  const [busy, setBusy] = useState(false);

  const fetchAssessments = useCallback(async () => {
    try {
      const page = await listAssessments(nodeId);
      setAssessments(page.items);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load assessments");
    }
  }, [nodeId]);

  useEffect(() => {
    let active = true;
    (async () => {
      await fetchAssessments();
      if (active) setLoading(false);
    })();
    return () => {
      active = false;
    };
  }, [fetchAssessments]);

  const openAssessment = async (id: string) => {
    setError(null);
    try {
      setSelected(await getAssessment(id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to open assessment");
    }
  };

  const create = async () => {
    setBusy(true);
    setError(null);
    try {
      const created = await createAssessment({
        node_id: nodeId,
        type: "quiz",
        config: newTitle.trim() ? { title: newTitle.trim() } : {},
      });
      setNewTitle("");
      await fetchAssessments();
      await openAssessment(created.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create quiz");
    } finally {
      setBusy(false);
    }
  };

  const resetQuestion = () => {
    setPrompt("");
    setOptions(["", ""]);
    setCorrect(0);
  };

  const saveQuestion = async () => {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const cleaned = options.map((t, i) => ({ id: OPTION_IDS[i], text: t.trim() }));
      await addQuestion(selected.id, {
        type: "mcq",
        prompt: { text: prompt.trim(), options: cleaned },
        answer_key: { correct: OPTION_IDS[correct] },
        position: selected.questions.length,
      });
      resetQuestion();
      setSelected(await getAssessment(selected.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to add question");
    } finally {
      setBusy(false);
    }
  };

  const removeQuestion = async (id: string) => {
    if (!selected) return;
    setError(null);
    try {
      await deleteQuestion(id);
      setSelected(await getAssessment(selected.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete question");
    }
  };

  const canSaveQuestion =
    prompt.trim().length > 0 &&
    options.filter((o) => o.trim().length > 0).length >= 2 &&
    options[correct]?.trim().length > 0;

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle className="text-base">Quizzes</CardTitle>
          <CardDescription>Assessments attached to this node.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex items-end gap-2">
            <div className="flex flex-1 flex-col gap-1.5">
              <Label htmlFor="quiz-title">New quiz title</Label>
              <Input
                id="quiz-title"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="e.g. Chapter 1 check"
              />
            </div>
            <Button onClick={create} disabled={busy}>
              Add
            </Button>
          </div>

          {error && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}

          {loading ? (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
            </div>
          ) : assessments.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">No quizzes yet.</p>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {assessments.map((a) => {
                const title = (a.config?.title as string) ?? "Untitled quiz";
                const active = selected?.id === a.id;
                return (
                  <li key={a.id}>
                    <button
                      type="button"
                      onClick={() => openAssessment(a.id)}
                      className={`flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                        active
                          ? "border-ring bg-muted"
                          : "border-border hover:bg-muted/50"
                      }`}
                    >
                      <span className="font-medium">{title}</span>
                      <Badge variant="outline">{a.type}</Badge>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card className="lg:col-span-3">
        {selected ? (
          <>
            <CardHeader>
              <CardTitle className="text-base">
                {(selected.config?.title as string) ?? "Quiz"}
              </CardTitle>
              <CardDescription>
                {selected.questions.length} question
                {selected.questions.length === 1 ? "" : "s"} · multiple choice, auto-graded
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-6">
              {selected.questions.length > 0 && (
                <ol className="flex flex-col gap-3">
                  {selected.questions.map((q, i) => {
                    const correctId = q.answer_key?.correct as string | undefined;
                    return (
                      <li key={q.id} className="rounded-lg border border-border p-3">
                        <div className="flex items-start justify-between gap-3">
                          <p className="text-sm font-medium">
                            {i + 1}. {(q.prompt?.text as string) ?? "(no prompt)"}
                          </p>
                          <Button
                            size="xs"
                            variant="destructive"
                            onClick={() => removeQuestion(q.id)}
                          >
                            Remove
                          </Button>
                        </div>
                        <ul className="mt-2 flex flex-col gap-1">
                          {((q.prompt?.options as { id: string; text: string }[]) ?? []).map(
                            (o) => (
                              <li
                                key={o.id}
                                className={`text-sm ${
                                  o.id === correctId
                                    ? "font-medium text-emerald-600 dark:text-emerald-400"
                                    : "text-muted-foreground"
                                }`}
                              >
                                {o.id === correctId ? "✓ " : "• "}
                                {o.text || optionText(q, o.id)}
                              </li>
                            ),
                          )}
                        </ul>
                      </li>
                    );
                  })}
                </ol>
              )}

              <div className="flex flex-col gap-4 rounded-lg border border-dashed border-border p-4">
                <p className="text-sm font-medium">Add a multiple-choice question</p>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="q-prompt">Question</Label>
                  <Input
                    id="q-prompt"
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="What is 2 + 2?"
                  />
                </div>
                <div className="flex flex-col gap-2">
                  <Label>Options (select the correct one)</Label>
                  {options.map((opt, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="correct-option"
                        checked={correct === i}
                        onChange={() => setCorrect(i)}
                        className="size-4"
                        aria-label={`Mark option ${OPTION_IDS[i]} correct`}
                      />
                      <Input
                        value={opt}
                        onChange={(e) =>
                          setOptions((prev) =>
                            prev.map((o, idx) => (idx === i ? e.target.value : o)),
                          )
                        }
                        placeholder={`Option ${OPTION_IDS[i]}`}
                      />
                      {options.length > 2 && (
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          onClick={() => {
                            setOptions((prev) => prev.filter((_, idx) => idx !== i));
                            setCorrect((c) => (c >= i && c > 0 ? c - 1 : c));
                          }}
                          aria-label="Remove option"
                        >
                          ✕
                        </Button>
                      )}
                    </div>
                  ))}
                  {options.length < OPTION_IDS.length && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setOptions((prev) => [...prev, ""])}
                      className="self-start"
                    >
                      Add option
                    </Button>
                  )}
                </div>
                <Button onClick={saveQuestion} disabled={busy || !canSaveQuestion}>
                  {busy ? "Saving…" : "Add question"}
                </Button>
              </div>
            </CardContent>
          </>
        ) : (
          <CardContent className="flex min-h-64 items-center justify-center">
            <p className="text-sm text-muted-foreground">
              Select or create a quiz to build questions.
            </p>
          </CardContent>
        )}
      </Card>
    </div>
  );
}
