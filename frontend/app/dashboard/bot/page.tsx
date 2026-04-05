"use client";

import { useState, useEffect } from "react";
import { Save, Upload, Trash2, FileText } from "lucide-react";
import { useBotProfile } from "@/hooks/use-bot-profile";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { personaPresets, voiceOptions, responseModeOptions } from "@/lib/constants";
import type { ResponseMode, VoiceOption } from "@/types";

const PERSONA_DESCRIPTIONS: Record<string, string> = {
  Professional: "Professional and strategic meeting copilot that answers crisply and drives decisions to closure.",
  Friendly: "Warm and approachable assistant that keeps meetings positive and ensures everyone feels heard.",
  Technical: "Technically precise assistant that provides detailed answers with data references and system context.",
  Strategic: "Strategic advisor that frames discussions around business goals, trade-offs, and key decisions.",
  "Research Assistant": "Thorough research-oriented assistant that surfaces relevant data during discussions."
};

export default function BotPage() {
  const { data: bot, isLoading, updateBotProfile, isSaving } = useBotProfile();
  const [name, setName] = useState("");
  const [persona, setPersona] = useState("");
  const [voice, setVoice] = useState<VoiceOption>("FEMALE");
  const [responseMode, setResponseMode] = useState<ResponseMode>("WAKE_WORD_ONLY");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (bot) {
      setName(bot.name);
      setPersona(bot.persona);
      setVoice(bot.voice);
      setResponseMode(bot.responseMode);
    }
  }, [bot]);

  async function handleSave() {
    await updateBotProfile({ name, persona, voice, responseMode });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  if (isLoading) {
    return (
      <div className="space-y-10">
        <Skeleton className="h-24 w-full rounded-3xl" />
        <div className="grid gap-8 lg:grid-cols-2">
          <Skeleton className="h-64 rounded-3xl" />
          <Skeleton className="h-64 rounded-3xl" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Configuration"
        title="My Bot"
        description="Customize your AI meeting copilot."
        actions={
          <Button onClick={handleSave} disabled={isSaving || name.length < 2}>
            <Save className="h-4 w-4" />
            {saved ? "Saved!" : isSaving ? "Saving..." : "Save changes"}
          </Button>
        }
      />

      <div className="grid gap-8 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Identity</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="bot-name">Bot name (wake word)</Label>
              <Input id="bot-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Nova" />
            </div>
            <Separator />
            <div className="space-y-3">
              <Label>Voice</Label>
              <RadioGroup value={voice} onValueChange={(v) => setVoice(v as VoiceOption)} className="flex gap-4">
                {voiceOptions.map((option) => (
                  <label
                    key={option.value}
                    className={`flex cursor-pointer items-center gap-2 rounded-xl border px-4 py-3 transition ${
                      voice === option.value ? "border-primary bg-primary/10" : "border-border"
                    }`}
                  >
                    <RadioGroupItem value={option.value} />
                    <span className="text-sm font-medium">{option.label}</span>
                  </label>
                ))}
              </RadioGroup>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Response Mode</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {responseModeOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setResponseMode(option.value as ResponseMode)}
                className={`w-full rounded-2xl border p-5 text-left transition ${
                  responseMode === option.value ? "border-primary bg-primary/10" : "border-border"
                }`}
              >
                <p className="font-medium">{option.label}</p>
                <p className="mt-1 text-sm text-muted-foreground">{option.description}</p>
              </button>
            ))}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Persona</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Textarea
              value={persona}
              onChange={(e) => setPersona(e.target.value)}
              placeholder="Describe how your bot should communicate..."
              rows={4}
            />
            <div className="flex flex-wrap gap-2">
              {personaPresets.map((preset) => (
                <Button
                  key={preset}
                  variant="outline"
                  size="sm"
                  onClick={() => setPersona(PERSONA_DESCRIPTIONS[preset] ?? preset)}
                >
                  {preset}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Global Documents</CardTitle>
              <Button variant="outline" size="sm">
                <Upload className="h-4 w-4" />
                Upload
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {bot?.documents && bot.documents.length > 0 ? (
              <div className="space-y-3">
                {bot.documents.map((doc) => (
                  <div key={doc.id} className="flex items-center justify-between rounded-xl border border-border p-4">
                    <div className="flex items-center gap-3">
                      <FileText className="h-5 w-5 text-muted-foreground" />
                      <div>
                        <p className="text-sm font-medium">{doc.name}</p>
                        <p className="text-xs text-muted-foreground">{(doc.fileSize / 1024).toFixed(0)} KB</p>
                      </div>
                    </div>
                    <Button variant="ghost" size="icon">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-border p-8 text-center">
                <p className="text-sm text-muted-foreground">
                  No documents uploaded. Upload PDFs or Word files to give your bot context in every meeting.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
