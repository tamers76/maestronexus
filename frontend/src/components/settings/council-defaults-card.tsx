"use client";

import { Users } from "lucide-react";

import { ModelMultiSelect, ModelSelect } from "@/components/settings/model-pickers";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { CouncilDefaults, ModelOption } from "@/lib/settings";

export function CouncilDefaultsCard({
  council,
  models,
  onChange,
}: {
  council: CouncilDefaults;
  models: ModelOption[];
  onChange: (next: CouncilDefaults) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Users className="size-4 text-primary" />
          <CardTitle className="text-base">Council defaults</CardTitle>
        </div>
        <CardDescription>
          Used by any stage running in council mode that doesn&apos;t set its own
          members, chairman, or prompts.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label>Council members</Label>
          <ModelMultiSelect
            values={council.members ?? []}
            options={models}
            onChange={(members) => onChange({ ...council, members })}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="council-chairman">Chairman model</Label>
          <ModelSelect
            id="council-chairman"
            value={council.chairman}
            options={models}
            onChange={(chairman) => onChange({ ...council, chairman })}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="council-member-prompt">Default member system prompt</Label>
          <Textarea
            id="council-member-prompt"
            rows={4}
            value={council.member_system_prompt ?? ""}
            placeholder="Falls back to each stage's recommended member prompt."
            onChange={(e) => onChange({ ...council, member_system_prompt: e.target.value })}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="council-chairman-prompt">Default chairman system prompt</Label>
          <Textarea
            id="council-chairman-prompt"
            rows={4}
            value={council.chairman_system_prompt ?? ""}
            placeholder="Falls back to each stage's recommended chairman prompt."
            onChange={(e) =>
              onChange({ ...council, chairman_system_prompt: e.target.value })
            }
          />
        </div>
      </CardContent>
    </Card>
  );
}
