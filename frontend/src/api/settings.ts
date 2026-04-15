import { apiClient } from "./client";

export interface LLMSettings {
  LLM_PROVIDER: string;
  ANTHROPIC_API_KEY_masked: string;
  ANTHROPIC_API_KEY_set: boolean;
  CLAUDE_MODEL_AGENT: string;
  CLAUDE_MODEL_NODE: string;
  CLAUDE_CLI_PATH: string;
  GOOGLE_API_KEY_masked: string;
  GOOGLE_API_KEY_set: boolean;
  GEMINI_MODEL_AGENT: string;
  GEMINI_MODEL_NODE: string;
}

// All fields are optional. Empty string clears the override.
// Undefined / missing field means "leave alone".
export interface LLMSettingsUpdate {
  LLM_PROVIDER?: string;
  ANTHROPIC_API_KEY?: string;
  CLAUDE_MODEL_AGENT?: string;
  CLAUDE_MODEL_NODE?: string;
  CLAUDE_CLI_PATH?: string;
  GOOGLE_API_KEY?: string;
  GEMINI_MODEL_AGENT?: string;
  GEMINI_MODEL_NODE?: string;
}

export interface ProviderTestResult {
  name: string;
  display_name: string;
  available: boolean;
  reason: string;
}

export async function getLLMSettings(): Promise<LLMSettings> {
  const { data } = await apiClient.get<LLMSettings>("/settings/llm");
  return data;
}

export async function updateLLMSettings(payload: LLMSettingsUpdate): Promise<LLMSettings> {
  const { data } = await apiClient.put<LLMSettings>("/settings/llm", payload);
  return data;
}

export async function testProviders(): Promise<ProviderTestResult[]> {
  const { data } = await apiClient.post<ProviderTestResult[]>("/settings/llm/test");
  return data;
}
