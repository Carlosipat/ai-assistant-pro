"use client"

import { useState, useRef, useEffect } from "react"
import { cn } from "@/lib/utils"
import type { Message, AIModel } from "@/lib/types"
import { AI_MODELS } from "@/lib/types"
import {
  Send,
  Paperclip,
  Mic,
  StopCircle,
  ChevronDown,
  Check,
  Loader2,
  Bot,
  User,
  Copy,
  ThumbsUp,
  ThumbsDown,
  RotateCcw,
  Sparkles,
} from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import rehypeHighlight from "rehype-highlight"

interface ChatAreaProps {
  messages: Message[]
  isLoading: boolean
  currentModel: string
  onModelChange: (model: string) => void
  onSendMessage: (content: string) => void
  onStopGeneration: () => void
  onRegenerateResponse: () => void
}

export function ChatArea({
  messages,
  isLoading,
  currentModel,
  onModelChange,
  onSendMessage,
  onStopGeneration,
  onRegenerateResponse,
}: ChatAreaProps) {
  const [input, setInput] = useState("")
  const [showModelPicker, setShowModelPicker] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const selectedModel = AI_MODELS.find((m) => m.id === currentModel) || AI_MODELS[0]

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`
    }
  }, [input])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return
    onSendMessage(input.trim())
    setInput("")
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-background">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <WelcomeScreen selectedModel={selectedModel} onModelChange={onModelChange} />
        ) : (
          <div className="max-w-3xl mx-auto py-6 px-4">
            {messages.map((message, index) => (
              <MessageBubble
                key={message.id}
                message={message}
                isLast={index === messages.length - 1}
                onRegenerate={
                  message.role === "assistant" && index === messages.length - 1
                    ? onRegenerateResponse
                    : undefined
                }
              />
            ))}
            {isLoading && messages[messages.length - 1]?.role === "user" && (
              <div className="flex gap-4 py-4">
                <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
                <div className="flex-1 flex items-center gap-2 text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="text-sm">Thinking...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t border-border bg-background">
        <div className="max-w-3xl mx-auto p-4">
          {/* Model Picker (for non-empty chats) */}
          {messages.length > 0 && (
            <div className="flex items-center gap-2 mb-3">
              <ModelPickerButton
                selectedModel={selectedModel}
                onClick={() => setShowModelPicker(!showModelPicker)}
                isOpen={showModelPicker}
              />
              {showModelPicker && (
                <ModelPickerDropdown
                  models={AI_MODELS}
                  selectedModel={currentModel}
                  onSelect={(id) => {
                    onModelChange(id)
                    setShowModelPicker(false)
                  }}
                  onClose={() => setShowModelPicker(false)}
                />
              )}
            </div>
          )}

          {/* Input Form */}
          <form onSubmit={handleSubmit} className="relative">
            <div className="relative bg-secondary border border-border rounded-xl overflow-hidden focus-within:ring-2 focus-within:ring-ring focus-within:border-transparent transition-all">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Message Retrai..."
                rows={1}
                className="w-full px-4 py-3 pr-24 bg-transparent text-foreground placeholder:text-muted-foreground resize-none focus:outline-none"
                disabled={isLoading}
              />
              <div className="absolute right-2 bottom-2 flex items-center gap-1">
                {isLoading ? (
                  <button
                    type="button"
                    onClick={onStopGeneration}
                    className="p-2 rounded-lg bg-destructive text-destructive-foreground hover:bg-destructive/90 transition-colors"
                  >
                    <StopCircle className="h-4 w-4" />
                  </button>
                ) : (
                  <button
                    type="submit"
                    disabled={!input.trim()}
                    className="p-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    <Send className="h-4 w-4" />
                  </button>
                )}
              </div>
            </div>
          </form>

          {/* Disclaimer */}
          <p className="text-xs text-muted-foreground text-center mt-3">
            Retrai can make mistakes. Consider verifying important information.
          </p>
        </div>
      </div>
    </div>
  )
}

interface WelcomeScreenProps {
  selectedModel: AIModel
  onModelChange: (model: string) => void
}

function WelcomeScreen({ selectedModel, onModelChange }: WelcomeScreenProps) {
  const [showModelPicker, setShowModelPicker] = useState(false)

  return (
    <div className="h-full flex flex-col items-center justify-center p-8">
      <div className="max-w-2xl w-full text-center">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-6">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center border border-border">
            <Sparkles className="h-8 w-8 text-primary" />
          </div>
        </div>

        <h1 className="text-3xl font-bold text-foreground mb-2">Welcome to Retrai</h1>
        <p className="text-lg text-muted-foreground mb-8">
          Your intelligent AI assistant. Ask me anything.
        </p>

        {/* Model Picker */}
        <div className="relative inline-block mb-8">
          <ModelPickerButton
            selectedModel={selectedModel}
            onClick={() => setShowModelPicker(!showModelPicker)}
            isOpen={showModelPicker}
          />
          {showModelPicker && (
            <ModelPickerDropdown
              models={AI_MODELS}
              selectedModel={selectedModel.id}
              onSelect={(id) => {
                onModelChange(id)
                setShowModelPicker(false)
              }}
              onClose={() => setShowModelPicker(false)}
            />
          )}
        </div>

        {/* Suggestion Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-left">
          {[
            "Explain quantum computing in simple terms",
            "Help me write a professional email",
            "What are the best practices for React?",
            "Create a weekly meal plan for me",
          ].map((suggestion, i) => (
            <button
              key={i}
              className="p-4 bg-secondary border border-border rounded-xl text-left hover:bg-accent transition-colors group"
            >
              <span className="text-sm text-foreground group-hover:text-foreground">
                {suggestion}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

interface MessageBubbleProps {
  message: Message
  isLast: boolean
  onRegenerate?: () => void
}

function MessageBubble({ message, isLast, onRegenerate }: MessageBubbleProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const isUser = message.role === "user"

  return (
    <div className={cn("flex gap-4 py-4", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "w-8 h-8 rounded-lg flex items-center justify-center shrink-0",
          isUser ? "bg-accent" : "bg-primary/10"
        )}
      >
        {isUser ? (
          <User className="h-4 w-4 text-foreground" />
        ) : (
          <Bot className="h-4 w-4 text-primary" />
        )}
      </div>

      <div className={cn("flex-1 min-w-0", isUser && "text-right")}>
        <div
          className={cn(
            "inline-block max-w-full text-left",
            isUser && "bg-chat-user px-4 py-3 rounded-2xl rounded-tr-sm"
          )}
        >
          {isUser ? (
            <p className="text-foreground whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="prose-chat">
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Actions for assistant messages */}
        {!isUser && (
          <div className="flex items-center gap-1 mt-2">
            <button
              onClick={handleCopy}
              className="p-1.5 rounded-lg hover:bg-accent transition-colors text-muted-foreground hover:text-foreground"
              title="Copy"
            >
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            </button>
            {onRegenerate && (
              <button
                onClick={onRegenerate}
                className="p-1.5 rounded-lg hover:bg-accent transition-colors text-muted-foreground hover:text-foreground"
                title="Regenerate"
              >
                <RotateCcw className="h-4 w-4" />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

interface ModelPickerButtonProps {
  selectedModel: AIModel
  onClick: () => void
  isOpen: boolean
}

function ModelPickerButton({ selectedModel, onClick, isOpen }: ModelPickerButtonProps) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 px-3 py-1.5 bg-secondary border border-border rounded-lg hover:bg-accent transition-colors"
    >
      <span className="text-sm font-medium text-foreground">{selectedModel.name}</span>
      <span className="text-xs text-muted-foreground">{selectedModel.provider}</span>
      <ChevronDown
        className={cn("h-4 w-4 text-muted-foreground transition-transform", isOpen && "rotate-180")}
      />
    </button>
  )
}

interface ModelPickerDropdownProps {
  models: AIModel[]
  selectedModel: string
  onSelect: (id: string) => void
  onClose: () => void
}

function ModelPickerDropdown({ models, selectedModel, onSelect, onClose }: ModelPickerDropdownProps) {
  return (
    <>
      <div className="fixed inset-0 z-40" onClick={onClose} />
      <div className="absolute left-0 top-full mt-2 w-72 bg-popover border border-border rounded-xl shadow-lg z-50 py-2 max-h-80 overflow-y-auto">
        {models.map((model) => (
          <button
            key={model.id}
            onClick={() => onSelect(model.id)}
            className={cn(
              "w-full flex items-start gap-3 px-3 py-2 hover:bg-accent transition-colors text-left",
              selectedModel === model.id && "bg-accent"
            )}
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-foreground">{model.name}</span>
                <span className="text-xs px-1.5 py-0.5 bg-secondary rounded text-muted-foreground">
                  {model.provider}
                </span>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">{model.description}</p>
            </div>
            {selectedModel === model.id && <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />}
          </button>
        ))}
      </div>
    </>
  )
}
