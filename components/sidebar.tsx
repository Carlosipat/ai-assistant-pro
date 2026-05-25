"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { createClient } from "@/lib/supabase/client"
import { cn, formatDate } from "@/lib/utils"
import type { Session } from "@/lib/types"
import {
  Plus,
  Search,
  Star,
  MoreHorizontal,
  Trash2,
  Edit3,
  FolderOpen,
  Settings,
  LogOut,
  ChevronLeft,
  ChevronRight,
  MessageSquare,
  User,
} from "lucide-react"

interface SidebarProps {
  sessions: Session[]
  currentSessionId: string | null
  onNewChat: () => void
  onSelectSession: (id: string) => void
  onDeleteSession: (id: string) => void
  onToggleStar: (id: string) => void
  user: { email?: string; id?: string } | null
  collapsed: boolean
  onToggleCollapse: () => void
}

export function Sidebar({
  sessions,
  currentSessionId,
  onNewChat,
  onSelectSession,
  onDeleteSession,
  onToggleStar,
  user,
  collapsed,
  onToggleCollapse,
}: SidebarProps) {
  const [searchQuery, setSearchQuery] = useState("")
  const [openMenuId, setOpenMenuId] = useState<string | null>(null)
  const router = useRouter()
  const supabase = createClient()

  const filteredSessions = sessions.filter((session) =>
    session.title.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const starredSessions = filteredSessions.filter((s) => s.starred)
  const recentSessions = filteredSessions.filter((s) => !s.starred)

  const handleSignOut = async () => {
    await supabase.auth.signOut()
    router.push("/auth/login")
    router.refresh()
  }

  if (collapsed) {
    return (
      <div className="w-16 h-full bg-sidebar border-r border-sidebar-border flex flex-col items-center py-4 gap-4">
        <button
          onClick={onToggleCollapse}
          className="p-2 rounded-lg hover:bg-accent transition-colors"
          title="Expand sidebar"
        >
          <ChevronRight className="h-5 w-5 text-muted-foreground" />
        </button>
        <button
          onClick={onNewChat}
          className="p-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
          title="New chat"
        >
          <Plus className="h-5 w-5" />
        </button>
        <div className="flex-1" />
        {user && (
          <div className="p-2 rounded-lg bg-accent" title={user.email || "User"}>
            <User className="h-5 w-5 text-foreground" />
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="w-72 h-full bg-sidebar border-r border-sidebar-border flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-sidebar-border">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center border border-border">
              <span className="text-lg font-bold text-primary">R</span>
            </div>
            <span className="font-semibold text-foreground">Retrai</span>
          </div>
          <button
            onClick={onToggleCollapse}
            className="p-1.5 rounded-lg hover:bg-accent transition-colors"
            title="Collapse sidebar"
          >
            <ChevronLeft className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>

        {/* New Chat Button */}
        <button
          onClick={onNewChat}
          className="w-full flex items-center gap-2 px-3 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors font-medium text-sm"
        >
          <Plus className="h-4 w-4" />
          New Chat
        </button>

        {/* Search */}
        <div className="relative mt-3">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search chats..."
            className="w-full pl-9 pr-3 py-2 bg-secondary border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring transition-all"
          />
        </div>
      </div>

      {/* Sessions List */}
      <div className="flex-1 overflow-y-auto p-2">
        {/* Starred Section */}
        {starredSessions.length > 0 && (
          <div className="mb-4">
            <div className="flex items-center gap-2 px-2 py-1 text-xs font-medium text-muted-foreground uppercase tracking-wide">
              <Star className="h-3 w-3" />
              Starred
            </div>
            {starredSessions.map((session) => (
              <SessionItem
                key={session.id}
                session={session}
                isActive={session.id === currentSessionId}
                onSelect={() => onSelectSession(session.id)}
                onDelete={() => onDeleteSession(session.id)}
                onToggleStar={() => onToggleStar(session.id)}
                isMenuOpen={openMenuId === session.id}
                onToggleMenu={() => setOpenMenuId(openMenuId === session.id ? null : session.id)}
              />
            ))}
          </div>
        )}

        {/* Recent Section */}
        {recentSessions.length > 0 && (
          <div>
            <div className="flex items-center gap-2 px-2 py-1 text-xs font-medium text-muted-foreground uppercase tracking-wide">
              <MessageSquare className="h-3 w-3" />
              Recent
            </div>
            {recentSessions.map((session) => (
              <SessionItem
                key={session.id}
                session={session}
                isActive={session.id === currentSessionId}
                onSelect={() => onSelectSession(session.id)}
                onDelete={() => onDeleteSession(session.id)}
                onToggleStar={() => onToggleStar(session.id)}
                isMenuOpen={openMenuId === session.id}
                onToggleMenu={() => setOpenMenuId(openMenuId === session.id ? null : session.id)}
              />
            ))}
          </div>
        )}

        {filteredSessions.length === 0 && (
          <div className="text-center py-8 text-muted-foreground text-sm">
            {searchQuery ? "No chats found" : "No chats yet"}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-sidebar-border">
        {user ? (
          <div className="flex items-center gap-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-accent transition-colors cursor-pointer">
                <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center">
                  <User className="h-4 w-4 text-foreground" />
                </div>
                <span className="text-sm text-foreground truncate">{user.email}</span>
              </div>
            </div>
            <button
              onClick={handleSignOut}
              className="p-2 rounded-lg hover:bg-accent transition-colors"
              title="Sign out"
            >
              <LogOut className="h-4 w-4 text-muted-foreground" />
            </button>
          </div>
        ) : (
          <Link
            href="/auth/login"
            className="flex items-center justify-center gap-2 w-full px-3 py-2 bg-secondary border border-border rounded-lg text-sm text-foreground hover:bg-accent transition-colors"
          >
            <User className="h-4 w-4" />
            Sign in
          </Link>
        )}
      </div>
    </div>
  )
}

interface SessionItemProps {
  session: Session
  isActive: boolean
  onSelect: () => void
  onDelete: () => void
  onToggleStar: () => void
  isMenuOpen: boolean
  onToggleMenu: () => void
}

function SessionItem({
  session,
  isActive,
  onSelect,
  onDelete,
  onToggleStar,
  isMenuOpen,
  onToggleMenu,
}: SessionItemProps) {
  return (
    <div className="relative group">
      <button
        onClick={onSelect}
        className={cn(
          "w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-colors",
          isActive
            ? "bg-accent text-foreground"
            : "text-muted-foreground hover:bg-accent hover:text-foreground"
        )}
      >
        <MessageSquare className="h-4 w-4 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="text-sm truncate">{session.title}</div>
          <div className="text-xs text-muted-foreground">{formatDate(session.updated_at)}</div>
        </div>
        {session.starred && <Star className="h-3 w-3 fill-yellow-500 text-yellow-500 shrink-0" />}
      </button>

      {/* Menu Button */}
      <button
        onClick={(e) => {
          e.stopPropagation()
          onToggleMenu()
        }}
        className={cn(
          "absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded hover:bg-secondary transition-opacity",
          isMenuOpen || isActive ? "opacity-100" : "opacity-0 group-hover:opacity-100"
        )}
      >
        <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
      </button>

      {/* Dropdown Menu */}
      {isMenuOpen && (
        <div className="absolute right-0 top-full mt-1 w-40 bg-popover border border-border rounded-lg shadow-lg z-50 py-1">
          <button
            onClick={(e) => {
              e.stopPropagation()
              onToggleStar()
              onToggleMenu()
            }}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-accent transition-colors"
          >
            <Star className={cn("h-4 w-4", session.starred && "fill-yellow-500 text-yellow-500")} />
            {session.starred ? "Unstar" : "Star"}
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              onDelete()
              onToggleMenu()
            }}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-destructive hover:bg-accent transition-colors"
          >
            <Trash2 className="h-4 w-4" />
            Delete
          </button>
        </div>
      )}
    </div>
  )
}
