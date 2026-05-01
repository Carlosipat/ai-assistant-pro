-- ============================================
-- AI Assistant Pro — Supabase Database Setup
-- Run this in: Supabase Dashboard → SQL Editor
-- ============================================

-- Sessions table (stores all conversation history)
CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY,
  messages   TEXT NOT NULL DEFAULT '[]',
  created_at FLOAT,
  updated_at FLOAT
);

-- Index for faster sorting by last updated
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions (updated_at DESC);

-- Enable Row Level Security (optional but recommended)
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

-- Allow all operations via service role / anon key (for personal use)
CREATE POLICY "Allow all" ON sessions FOR ALL USING (true);

-- ============================================
-- Done! Copy your project URL and anon key
-- from: Supabase Dashboard → Settings → API
-- ============================================
