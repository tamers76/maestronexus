"use client";

import { CheckCircle2, KeyRound, Loader2, XCircle } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { type ProviderConfig, testConnection } from "@/lib/settings";

const PROVIDER_LABELS: Record<string, string> = {
  openai: "OpenAI",
  openrouter: "OpenRouter",
  anthropic: "Anthropic",
  azure_openai: "Azure OpenAI",
  google: "Google",
};

const LIVE_PROVIDERS = new Set(["openai", "openrouter"]);

// Per-provider hint shown in the optional Base URL field.
const BASE_URL_PLACEHOLDERS: Record<string, string> = {
  openai: "https://api.openai.com/v1",
  openrouter: "https://openrouter.ai/api/v1",
};

export function ProviderCard({
  provider,
  config,
  onChange,
}: {
  provider: string;
  config: ProviderConfig;
  onChange: (next: ProviderConfig) => void;
}) {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);

  const label = PROVIDER_LABELS[provider] ?? provider;
  const live = LIVE_PROVIDERS.has(provider);

  const onTest = async () => {
    setTesting(true);
    setResult(null);
    try {
      const r = await testConnection(provider, {
        api_key: config.api_key,
        base_url: config.base_url,
      });
      setResult({ ok: r.success, message: r.message });
    } catch (err) {
      setResult({
        ok: false,
        message: err instanceof ApiError ? err.message : "Test failed.",
      });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="rounded-lg border border-border p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <KeyRound className="size-4 text-muted-foreground" />
          <span className="text-sm font-medium">{label}</span>
          {config.configured ? (
            <Badge variant="success">key set</Badge>
          ) : (
            <Badge variant="secondary">not set</Badge>
          )}
        </div>
        {!live && <Badge variant="outline">stub</Badge>}
      </div>

      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={`${provider}-key`}>API key</Label>
          <Input
            id={`${provider}-key`}
            type="password"
            autoComplete="off"
            value={config.api_key ?? ""}
            placeholder={config.configured ? "•••• stored — type to replace" : "sk-…"}
            onChange={(e) => onChange({ ...config, api_key: e.target.value })}
          />
          <p className="text-xs text-muted-foreground">
            Stored securely and shown masked. Leave the masked value untouched to keep it.
          </p>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={`${provider}-url`}>Base URL (optional)</Label>
          <Input
            id={`${provider}-url`}
            value={config.base_url ?? ""}
            placeholder={BASE_URL_PLACEHOLDERS[provider] ?? "https://api.openai.com/v1"}
            onChange={(e) => onChange({ ...config, base_url: e.target.value })}
          />
        </div>

        <div className="flex items-center gap-3">
          <Button size="sm" variant="outline" onClick={onTest} disabled={testing || !live}>
            {testing ? <Loader2 className="animate-spin" /> : null}
            {testing ? "Testing…" : "Test connection"}
          </Button>
          {result && (
            <span
              className={
                "flex items-center gap-1 text-xs " +
                (result.ok ? "text-emerald-600 dark:text-emerald-400" : "text-destructive")
              }
            >
              {result.ok ? (
                <CheckCircle2 className="size-3.5" />
              ) : (
                <XCircle className="size-3.5" />
              )}
              {result.message}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
