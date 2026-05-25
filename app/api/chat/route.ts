import { streamText } from "ai"
import { gateway } from "@ai-sdk/gateway"

export const maxDuration = 60

export async function POST(req: Request) {
  try {
    const { messages, model = "groq/llama-3.3-70b-versatile", systemPrompt } = await req.json()

    const systemMessage = systemPrompt || `You are Retrai, a helpful, intelligent, and friendly AI assistant. 
You provide accurate, thoughtful, and well-structured responses.
You can help with a wide variety of tasks including coding, writing, analysis, math, and general questions.
Format your responses using Markdown when appropriate for better readability.
Be concise but thorough. If you don't know something, say so honestly.`

    const result = streamText({
      model: gateway(model),
      system: systemMessage,
      messages,
    })

    return result.toDataStreamResponse()
  } catch (error) {
    console.error("Chat API error:", error)
    return new Response(
      JSON.stringify({ error: "Failed to generate response" }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    )
  }
}
