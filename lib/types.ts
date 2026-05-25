export interface Message {
  id: string
  role: "user" | "assistant" | "system"
  content: string
  timestamp: string
  model?: string
}

export interface Session {
  id: string
  user_id: string | null
  title: string
  messages: Message[]
  project_id: string | null
  starred: boolean
  created_at: string
  updated_at: string
}

export interface Project {
  id: string
  user_id: string
  name: string
  description: string
  system_prompt: string
  sources: ProjectSource[]
  created_at: string
  updated_at: string
}

export interface ProjectSource {
  type: "url" | "file" | "text"
  content: string
  name: string
}

export interface UserSettings {
  user_id: string
  display_name: string
  theme: "dark" | "light"
  font_size: "small" | "medium" | "large"
  default_model: string
  response_style: "concise" | "balanced" | "detailed"
  updated_at: string
}

export interface AIModel {
  id: string
  name: string
  provider: string
  description: string
  maxTokens: number
  free: boolean
}

export const AI_MODELS: AIModel[] = [
  {
    id: "groq/llama-3.3-70b-versatile",
    name: "Llama 3.3 70B",
    provider: "Groq",
    description: "Fast and capable open-source model",
    maxTokens: 8192,
    free: true,
  },
  {
    id: "groq/llama-3.1-8b-instant",
    name: "Llama 3.1 8B",
    provider: "Groq",
    description: "Ultra-fast lightweight model",
    maxTokens: 8192,
    free: true,
  },
  {
    id: "google/gemini-2.0-flash",
    name: "Gemini 2.0 Flash",
    provider: "Google",
    description: "Google's fast multimodal model",
    maxTokens: 8192,
    free: true,
  },
  {
    id: "openai/gpt-4o-mini",
    name: "GPT-4o Mini",
    provider: "OpenAI",
    description: "Efficient and affordable GPT-4 variant",
    maxTokens: 16384,
    free: true,
  },
  {
    id: "anthropic/claude-3-5-haiku-latest",
    name: "Claude 3.5 Haiku",
    provider: "Anthropic",
    description: "Fast and intelligent",
    maxTokens: 8192,
    free: true,
  },
]
