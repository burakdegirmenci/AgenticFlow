import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Eye, EyeOff, Key, RotateCw, Save, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

import {
  getLLMSettings,
  type LLMSettings,
  type LLMSettingsUpdate,
  testProviders,
  updateLLMSettings,
} from "@/api/settings";

interface FormState {
  LLM_PROVIDER: string;
  ANTHROPIC_API_KEY: string; // Plain string the user types; "" → clear
  ANTHROPIC_API_KEY_dirty: boolean;
  CLAUDE_MODEL_AGENT: string;
  CLAUDE_MODEL_NODE: string;
  CLAUDE_CLI_PATH: string;
  GOOGLE_API_KEY: string;
  GOOGLE_API_KEY_dirty: boolean;
  GEMINI_MODEL_AGENT: string;
  GEMINI_MODEL_NODE: string;
}

function fromSettings(s: LLMSettings): FormState {
  return {
    LLM_PROVIDER: s.LLM_PROVIDER,
    ANTHROPIC_API_KEY: "",
    ANTHROPIC_API_KEY_dirty: false,
    CLAUDE_MODEL_AGENT: s.CLAUDE_MODEL_AGENT,
    CLAUDE_MODEL_NODE: s.CLAUDE_MODEL_NODE,
    CLAUDE_CLI_PATH: s.CLAUDE_CLI_PATH,
    GOOGLE_API_KEY: "",
    GOOGLE_API_KEY_dirty: false,
    GEMINI_MODEL_AGENT: s.GEMINI_MODEL_AGENT,
    GEMINI_MODEL_NODE: s.GEMINI_MODEL_NODE,
  };
}

function buildPayload(form: FormState, initial: LLMSettings): LLMSettingsUpdate {
  const out: LLMSettingsUpdate = {};
  if (form.LLM_PROVIDER !== initial.LLM_PROVIDER) out.LLM_PROVIDER = form.LLM_PROVIDER;
  if (form.CLAUDE_MODEL_AGENT !== initial.CLAUDE_MODEL_AGENT)
    out.CLAUDE_MODEL_AGENT = form.CLAUDE_MODEL_AGENT;
  if (form.CLAUDE_MODEL_NODE !== initial.CLAUDE_MODEL_NODE)
    out.CLAUDE_MODEL_NODE = form.CLAUDE_MODEL_NODE;
  if (form.CLAUDE_CLI_PATH !== initial.CLAUDE_CLI_PATH) out.CLAUDE_CLI_PATH = form.CLAUDE_CLI_PATH;
  if (form.GEMINI_MODEL_AGENT !== initial.GEMINI_MODEL_AGENT)
    out.GEMINI_MODEL_AGENT = form.GEMINI_MODEL_AGENT;
  if (form.GEMINI_MODEL_NODE !== initial.GEMINI_MODEL_NODE)
    out.GEMINI_MODEL_NODE = form.GEMINI_MODEL_NODE;
  if (form.ANTHROPIC_API_KEY_dirty) out.ANTHROPIC_API_KEY = form.ANTHROPIC_API_KEY;
  if (form.GOOGLE_API_KEY_dirty) out.GOOGLE_API_KEY = form.GOOGLE_API_KEY;
  return out;
}

export default function Settings() {
  const qc = useQueryClient();
  const [form, setForm] = useState<FormState | null>(null);

  const settingsQuery = useQuery({
    queryKey: ["settings", "llm"],
    queryFn: getLLMSettings,
  });

  useEffect(() => {
    if (settingsQuery.data && form === null) {
      setForm(fromSettings(settingsQuery.data));
    }
  }, [settingsQuery.data, form]);

  const testQuery = useQuery({
    queryKey: ["settings", "llm", "test"],
    queryFn: testProviders,
    refetchOnWindowFocus: false,
    enabled: !!settingsQuery.data,
  });

  const saveMut = useMutation({
    mutationFn: (payload: LLMSettingsUpdate) => updateLLMSettings(payload),
    onSuccess: (data) => {
      qc.setQueryData(["settings", "llm"], data);
      setForm(fromSettings(data));
      qc.invalidateQueries({ queryKey: ["settings", "llm", "test"] });
      qc.invalidateQueries({ queryKey: ["agent", "providers"] });
    },
  });

  if (settingsQuery.isLoading || !form || !settingsQuery.data) {
    return (
      <div className="flex h-full items-center justify-center text-[13px] text-neutral-500">
        Yükleniyor…
      </div>
    );
  }

  const initial = settingsQuery.data;
  const payload = buildPayload(form, initial);
  const hasChanges = Object.keys(payload).length > 0;

  const handleSave = () => {
    if (!hasChanges) return;
    saveMut.mutate(payload);
  };

  const handleReset = () => {
    setForm(fromSettings(initial));
  };

  return (
    <div className="h-full overflow-y-auto">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-neutral-200 bg-white px-6">
        <h1 className="text-[15px] font-semibold tracking-tight">Ayarlar</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={handleReset}
            disabled={!hasChanges || saveMut.isPending}
            className="flex items-center gap-1 border border-neutral-300 bg-white px-3 py-1.5 text-[12px] font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-40"
          >
            Sıfırla
          </button>
          <button
            onClick={handleSave}
            disabled={!hasChanges || saveMut.isPending}
            className="flex items-center gap-1 border border-accent bg-accent px-3 py-1.5 text-[12px] font-medium text-white hover:bg-accent-hover disabled:opacity-40"
          >
            <Save className="h-3.5 w-3.5" strokeWidth={2} />
            {saveMut.isPending ? "Kaydediliyor…" : "Kaydet"}
          </button>
        </div>
      </header>

      <div className="mx-0 max-w-[920px] px-6 py-5">
        {saveMut.isSuccess && !hasChanges && (
          <div className="mb-4 border border-emerald-200 bg-emerald-50 px-3 py-2 text-[12px] text-emerald-700">
            Kaydedildi.
          </div>
        )}
        {saveMut.isError && (
          <div className="mb-4 border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
            Kaydedilemedi: {saveMut.error?.message}
          </div>
        )}

        {/* Provider seçimi */}
        <Section title="LLM Provider" subtitle="Varsayılan agent provider'ı">
          <Field label="Aktif Provider">
            <select
              value={form.LLM_PROVIDER}
              onChange={(e) => setForm({ ...form, LLM_PROVIDER: e.target.value })}
              className="w-full border border-neutral-300 bg-white px-2 py-1.5 text-[12.5px] outline-none focus:border-accent"
            >
              <option value="anthropic_api">Anthropic API (API Key)</option>
              <option value="anthropic_cli">Anthropic CLI — Claude Code (Subscription)</option>
              <option value="google_genai">Google Gemini (API Key)</option>
            </select>
            <FieldHint>
              Agent panelinde override edilebilir. Boş bırakılırsa burası kullanılır.
            </FieldHint>
          </Field>
        </Section>

        {/* Anthropic API */}
        <Section title="Anthropic API" subtitle="Claude API key — tam tool_use desteği">
          <SecretField
            label="ANTHROPIC_API_KEY"
            placeholder={
              initial.ANTHROPIC_API_KEY_set
                ? `Kayıtlı: ${initial.ANTHROPIC_API_KEY_masked}`
                : "sk-ant-..."
            }
            isSet={initial.ANTHROPIC_API_KEY_set}
            value={form.ANTHROPIC_API_KEY}
            onChange={(v) =>
              setForm({
                ...form,
                ANTHROPIC_API_KEY: v,
                ANTHROPIC_API_KEY_dirty: true,
              })
            }
            onClear={() =>
              setForm({
                ...form,
                ANTHROPIC_API_KEY: "",
                ANTHROPIC_API_KEY_dirty: true,
              })
            }
          />
          <Field label="Agent Modeli">
            <input
              type="text"
              value={form.CLAUDE_MODEL_AGENT}
              onChange={(e) => setForm({ ...form, CLAUDE_MODEL_AGENT: e.target.value })}
              placeholder="claude-opus-4-6"
              className="w-full border border-neutral-300 bg-white px-2 py-1.5 font-mono text-[12px] outline-none focus:border-accent"
            />
          </Field>
          <Field label="Node Modeli (in-workflow ai.* node'lar için)">
            <input
              type="text"
              value={form.CLAUDE_MODEL_NODE}
              onChange={(e) => setForm({ ...form, CLAUDE_MODEL_NODE: e.target.value })}
              placeholder="claude-sonnet-4-5-20250929"
              className="w-full border border-neutral-300 bg-white px-2 py-1.5 font-mono text-[12px] outline-none focus:border-accent"
            />
          </Field>
        </Section>

        {/* Anthropic CLI */}
        <Section
          title="Anthropic CLI (Subscription)"
          subtitle="Claude Code CLI subprocess — Pro/Max aboneliği. tool_use yok, text-only."
        >
          <Field label="CLAUDE_CLI_PATH">
            <input
              type="text"
              value={form.CLAUDE_CLI_PATH}
              onChange={(e) => setForm({ ...form, CLAUDE_CLI_PATH: e.target.value })}
              placeholder="claude"
              className="w-full border border-neutral-300 bg-white px-2 py-1.5 font-mono text-[12px] outline-none focus:border-accent"
            />
            <FieldHint>
              Boş bırakılırsa sistem PATH'inden <code className="font-mono">claude</code> aranır.
              <code className="font-mono"> claude login</code> ile giriş yapılmış olmalı.
            </FieldHint>
          </Field>
        </Section>

        {/* Google Gemini */}
        <Section title="Google Gemini" subtitle="google-genai SDK ile API erişimi">
          <SecretField
            label="GOOGLE_API_KEY"
            placeholder={
              initial.GOOGLE_API_KEY_set ? `Kayıtlı: ${initial.GOOGLE_API_KEY_masked}` : "AIza..."
            }
            isSet={initial.GOOGLE_API_KEY_set}
            value={form.GOOGLE_API_KEY}
            onChange={(v) =>
              setForm({
                ...form,
                GOOGLE_API_KEY: v,
                GOOGLE_API_KEY_dirty: true,
              })
            }
            onClear={() =>
              setForm({
                ...form,
                GOOGLE_API_KEY: "",
                GOOGLE_API_KEY_dirty: true,
              })
            }
          />
          <Field label="Agent Modeli">
            <input
              type="text"
              value={form.GEMINI_MODEL_AGENT}
              onChange={(e) => setForm({ ...form, GEMINI_MODEL_AGENT: e.target.value })}
              placeholder="gemini-2.5-pro"
              className="w-full border border-neutral-300 bg-white px-2 py-1.5 font-mono text-[12px] outline-none focus:border-accent"
            />
          </Field>
          <Field label="Node Modeli">
            <input
              type="text"
              value={form.GEMINI_MODEL_NODE}
              onChange={(e) => setForm({ ...form, GEMINI_MODEL_NODE: e.target.value })}
              placeholder="gemini-2.5-flash"
              className="w-full border border-neutral-300 bg-white px-2 py-1.5 font-mono text-[12px] outline-none focus:border-accent"
            />
          </Field>
        </Section>

        {/* Provider testleri */}
        <Section
          title="Provider Durumu"
          subtitle="Mevcut ayarlarla bağlantı testi"
          right={
            <button
              onClick={() => testQuery.refetch()}
              disabled={testQuery.isFetching}
              className="flex items-center gap-1 border border-neutral-300 bg-white px-2 py-1 text-[11px] font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-40"
            >
              <RotateCw
                className={["h-3 w-3", testQuery.isFetching ? "animate-spin" : ""].join(" ")}
                strokeWidth={2}
              />
              {testQuery.isFetching ? "Test ediliyor…" : "Tekrar test et"}
            </button>
          }
        >
          {testQuery.data?.map((p) => (
            <div
              key={p.name}
              className="flex items-start justify-between border border-neutral-200 bg-white px-3 py-2"
            >
              <div className="flex min-w-0 items-start gap-2">
                {p.available ? (
                  <CheckCircle2
                    className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600"
                    strokeWidth={2}
                  />
                ) : (
                  <XCircle
                    className="mt-0.5 h-3.5 w-3.5 shrink-0 text-neutral-400"
                    strokeWidth={2}
                  />
                )}
                <div className="min-w-0">
                  <div className="text-[12.5px] font-medium text-ink">{p.display_name}</div>
                  <div className="font-mono text-[11px] text-neutral-500">{p.name}</div>
                </div>
              </div>
              <div className="ml-3 max-w-[60%] text-right text-[11px] text-neutral-600">
                {p.reason}
              </div>
            </div>
          ))}
          {testQuery.isLoading && <div className="text-[12px] text-neutral-500">Yükleniyor…</div>}
          {testQuery.isError && (
            <div className="border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
              Test başarısız: {testQuery.error?.message}
            </div>
          )}
        </Section>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Reusable bits
// ---------------------------------------------------------------------------
function Section({
  title,
  subtitle,
  right,
  children,
}: {
  title: string;
  subtitle?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-5 border border-neutral-200 bg-white">
      <header className="flex items-start justify-between border-b border-neutral-100 bg-neutral-50 px-4 py-2.5">
        <div className="min-w-0">
          <h2 className="text-[12.5px] font-semibold uppercase tracking-wider text-neutral-700">
            {title}
          </h2>
          {subtitle && <p className="mt-0.5 text-[11px] text-neutral-500">{subtitle}</p>}
        </div>
        {right}
      </header>
      <div className="space-y-3 px-4 py-4">{children}</div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
        {label}
      </label>
      {children}
    </div>
  );
}

function FieldHint({ children }: { children: React.ReactNode }) {
  return <p className="mt-1 text-[11px] leading-relaxed text-neutral-500">{children}</p>;
}

function SecretField({
  label,
  placeholder,
  value,
  isSet,
  onChange,
  onClear,
}: {
  label: string;
  placeholder?: string;
  value: string;
  isSet: boolean;
  onChange: (v: string) => void;
  onClear: () => void;
}) {
  const [reveal, setReveal] = useState(false);
  return (
    <Field label={label}>
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Key
            className="pointer-events-none absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-neutral-400"
            strokeWidth={2}
          />
          <input
            type={reveal ? "text" : "password"}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            className="w-full border border-neutral-300 bg-white py-1.5 pl-7 pr-8 font-mono text-[12px] outline-none focus:border-accent"
            autoComplete="off"
          />
          <button
            type="button"
            onClick={() => setReveal((r) => !r)}
            className="absolute right-1 top-1/2 -translate-y-1/2 p-1 text-neutral-500 hover:text-ink"
            tabIndex={-1}
          >
            {reveal ? (
              <EyeOff className="h-3 w-3" strokeWidth={2} />
            ) : (
              <Eye className="h-3 w-3" strokeWidth={2} />
            )}
          </button>
        </div>
        {isSet && (
          <button
            type="button"
            onClick={onClear}
            className="border border-neutral-300 bg-white px-2 py-1.5 text-[11px] font-medium text-neutral-700 hover:bg-neutral-50"
            title="Temizle (env değerine geri dön)"
          >
            Temizle
          </button>
        )}
      </div>
      <FieldHint>
        {isSet
          ? "Bir değer kaydedildi. Yenisini yazıp Kaydet'e basarak güncelleyin veya Temizle ile env defaults'a dönün."
          : "Henüz değer kaydedilmedi. Boş bırakılırsa .env dosyasındaki değer kullanılır."}
      </FieldHint>
    </Field>
  );
}
