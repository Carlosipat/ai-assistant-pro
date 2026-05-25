"use client"

import { useState, useCallback } from "react"
import useSWR, { mutate } from "swr"
import type { Session, Message } from "@/lib/types"
import { generateId } from "@/lib/utils"

const fetcher = (url: string) => fetch(url).then((res) => res.json())

export function useSessions() {
  const { data, error, isLoading } = useSWR<{ sessions: Session[] }>(
    "/api/sessions",
    fetcher
  )

  const createSession = useCallback(async (title?: string) => {
    const res = await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title || "New Chat" }),
    })
    const data = await res.json()
    mutate("/api/sessions")
    return data.session as Session | undefined
  }, [])

  const updateSession = useCallback(async (id: string, updates: Partial<Session>) => {
    await fetch(`/api/sessions/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    })
    mutate("/api/sessions")
  }, [])

  const deleteSession = useCallback(async (id: string) => {
    await fetch(`/api/sessions/${id}`, {
      method: "DELETE",
    })
    mutate("/api/sessions")
  }, [])

  return {
    sessions: data?.sessions || [],
    isLoading,
    error,
    createSession,
    updateSession,
    deleteSession,
  }
}

export function useChat(sessionId: string | null, userId: string | null) {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [currentModel, setCurrentModel] = useState("groq/llama-3.3-70b-versatile")
  const [abortController, setAbortController] = useState<AbortController | null>(null)

  const { updateSession, createSession } = useSessions()

  const loadMessages = useCallback((sessionMessages: Message[]) => {
    setMessages(sessionMessages)
  }, [])

  const sendMessage = useCallback(
    async (content: string) => {
      const userMessage: Message = {
        id: generateId(),
        role: "user",
        content,
        timestamp: new Date().toISOString(),
      }

      const newMessages = [...messages, userMessage]
      setMessages(newMessages)
      setIsLoading(true)

      const controller = new AbortController()
      setAbortController(controller)

      try {
        const response = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            messages: newMessages.map((m) => ({
              role: m.role,
              content: m.content,
            })),
            model: currentModel,
          }),
          signal: controller.signal,
        })

        if (!response.ok) {
          throw new Error("Failed to generate response")
        }

        const reader = response.body?.getReader()
        if (!reader) throw new Error("No reader available")

        const assistantMessage: Message = {
          id: generateId(),
          role: "assistant",
          content: "",
          timestamp: new Date().toISOString(),
          model: currentModel,
        }

        setMessages((prev) => [...prev, assistantMessage])

        const decoder = new TextDecoder()
        let fullContent = ""

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const chunk = decoder.decode(value)
          const lines = chunk.split("\n")

          for (const line of lines) {
            if (line.startsWith("0:")) {
              try {
                const text = JSON.parse(line.slice(2))
                fullContent += text
                setMessages((prev) => {
                  const updated = [...prev]
                  const lastIndex = updated.length - 1
                  if (updated[lastIndex]?.role === "assistant") {
                    updated[lastIndex] = {
                      ...updated[lastIndex],
                      content: fullContent,
                    }
                  }
                  return updated
                })
              } catch {
                // Skip malformed lines
              }
            }
          }
        }

        // Save to database if user is logged in
        if (userId && sessionId) {
          const finalMessages = [...newMessages, { ...assistantMessage, content: fullContent }]
          
          // Generate title from first message if it's a new chat
          let title = "New Chat"
          if (newMessages.length === 1) {
            title = content.slice(0, 50) + (content.length > 50 ? "..." : "")
          }

          await updateSession(sessionId, { messages: finalMessages, title })
        }
      } catch (error) {
        if ((error as Error).name !== "AbortError") {
          console.error("Error sending message:", error)
          // Remove the loading state but keep the user message
          setMessages(newMessages)
        }
      } finally {
        setIsLoading(false)
        setAbortController(null)
      }
    },
    [messages, currentModel, sessionId, userId, updateSession]
  )

  const stopGeneration = useCallback(() => {
    if (abortController) {
      abortController.abort()
      setIsLoading(false)
    }
  }, [abortController])

  const regenerateResponse = useCallback(async () => {
    if (messages.length < 2) return
    
    // Remove the last assistant message and resend
    const lastUserMessageIndex = messages.length - 2
    if (messages[lastUserMessageIndex]?.role === "user") {
      const userContent = messages[lastUserMessageIndex].content
      setMessages(messages.slice(0, -1))
      await sendMessage(userContent)
    }
  }, [messages, sendMessage])

  const clearMessages = useCallback(() => {
    setMessages([])
  }, [])

  return {
    messages,
    isLoading,
    currentModel,
    setCurrentModel,
    loadMessages,
    sendMessage,
    stopGeneration,
    regenerateResponse,
    clearMessages,
  }
}
