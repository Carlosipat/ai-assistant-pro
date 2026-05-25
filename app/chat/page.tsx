"use client"

import { useState, useEffect, useCallback } from "react"
import { useRouter } from "next/navigation"
import { createClient } from "@/lib/supabase/client"
import { Sidebar } from "@/components/sidebar"
import { ChatArea } from "@/components/chat-area"
import { useSessions, useChat } from "@/hooks/use-chat"
import type { Session } from "@/lib/types"
import type { User } from "@supabase/supabase-js"

export default function ChatPage() {
  const [user, setUser] = useState<User | null>(null)
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [isInitializing, setIsInitializing] = useState(true)
  const router = useRouter()
  const supabase = createClient()

  const { sessions, createSession, updateSession, deleteSession } = useSessions()
  const {
    messages,
    isLoading,
    currentModel,
    setCurrentModel,
    loadMessages,
    sendMessage,
    stopGeneration,
    regenerateResponse,
    clearMessages,
  } = useChat(currentSessionId, user?.id || null)

  // Initialize auth state
  useEffect(() => {
    const initAuth = async () => {
      const { data: { user } } = await supabase.auth.getUser()
      setUser(user)
      setIsInitializing(false)
    }
    initAuth()

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user || null)
    })

    return () => subscription.unsubscribe()
  }, [supabase.auth])

  // Load session messages when session changes
  useEffect(() => {
    if (currentSessionId && sessions.length > 0) {
      const session = sessions.find((s) => s.id === currentSessionId)
      if (session) {
        loadMessages(session.messages || [])
      }
    }
  }, [currentSessionId, sessions, loadMessages])

  const handleNewChat = useCallback(async () => {
    clearMessages()
    if (user) {
      const newSession = await createSession()
      if (newSession) {
        setCurrentSessionId(newSession.id)
      }
    } else {
      setCurrentSessionId(null)
    }
  }, [user, createSession, clearMessages])

  const handleSelectSession = useCallback((id: string) => {
    setCurrentSessionId(id)
  }, [])

  const handleDeleteSession = useCallback(async (id: string) => {
    await deleteSession(id)
    if (currentSessionId === id) {
      setCurrentSessionId(null)
      clearMessages()
    }
  }, [deleteSession, currentSessionId, clearMessages])

  const handleToggleStar = useCallback(async (id: string) => {
    const session = sessions.find((s) => s.id === id)
    if (session) {
      await updateSession(id, { starred: !session.starred })
    }
  }, [sessions, updateSession])

  const handleSendMessage = useCallback(async (content: string) => {
    // If user is logged in and no session, create one first
    if (user && !currentSessionId) {
      const newSession = await createSession(content.slice(0, 50))
      if (newSession) {
        setCurrentSessionId(newSession.id)
      }
    }
    await sendMessage(content)
  }, [user, currentSessionId, createSession, sendMessage])

  if (isInitializing) {
    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center border border-border animate-pulse">
            <span className="text-lg font-bold text-primary">R</span>
          </div>
          <span className="text-foreground font-medium">Loading...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen flex bg-background">
      {/* Sidebar */}
      <Sidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        onNewChat={handleNewChat}
        onSelectSession={handleSelectSession}
        onDeleteSession={handleDeleteSession}
        onToggleStar={handleToggleStar}
        user={user ? { email: user.email, id: user.id } : null}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main Chat Area */}
      <ChatArea
        messages={messages}
        isLoading={isLoading}
        currentModel={currentModel}
        onModelChange={setCurrentModel}
        onSendMessage={handleSendMessage}
        onStopGeneration={stopGeneration}
        onRegenerateResponse={regenerateResponse}
      />
    </div>
  )
}
