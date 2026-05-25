import type { Metadata, Viewport } from "next"
import { Inter } from "next/font/google"
import "./globals.css"

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" })

export const metadata: Metadata = {
  title: "Retrai - AI Assistant",
  description: "A powerful AI assistant with multi-model support, chat history, and custom projects",
  keywords: ["AI", "assistant", "chat", "GPT", "Claude", "Llama"],
}

export const viewport: Viewport = {
  themeColor: "#0a0a0b",
  width: "device-width",
  initialScale: 1,
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark bg-background">
      <body className={`${inter.variable} font-sans`}>{children}</body>
    </html>
  )
}
