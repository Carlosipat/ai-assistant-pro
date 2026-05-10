-- ============================================================
-- AI Assistant Pro — Supabase Database Setup (FIXED)
-- Run this in: Supabase Dashboard → SQL Editor
-- Safe to re-run — uses IF NOT EXISTS / ADD COLUMN IF NOT EXISTS
-- ============================================================

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT        NOT NULL,
  user_id    TEXT        NOT NULL DEFAULT 'guest',
  title      TEXT        NOT NULL DEFAULT 'New Chat',
  messages   TEXT        NOT NULL DEFAULT '[]',
  created_at FLOAT,
  updated_at FLOAT,
  PRIMARY KEY (session_id, user_id)
);

-- Add missing columns if upgrading from the old schema (single-column PK)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='sessions' AND column_name='user_id'
  ) THEN
    ALTER TABLE sessions ADD COLUMN user_id TEXT NOT NULL DEFAULT 'guest';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='sessions' AND column_name='title'
  ) THEN
    ALTER TABLE sessions ADD COLUMN title TEXT NOT NULL DEFAULT 'New Chat';
  END IF;
END $$;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sessions_user    ON sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions (updated_at DESC);

-- Row Level Security
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow all" ON sessions;
CREATE POLICY "Allow all" ON sessions FOR ALL USING (true);

-- ============================================================
-- User settings table (was missing from original schema)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_settings (
  user_id       TEXT PRIMARY KEY,
  display_name  TEXT    DEFAULT '',
  theme         TEXT    DEFAULT 'dark',
  font_size     TEXT    DEFAULT 'medium',
  language      TEXT    DEFAULT 'en',
  ai_persona    TEXT    DEFAULT 'retrai',
  ai_tone       TEXT    DEFAULT 'balanced',
  max_tokens    INTEGER DEFAULT 1024,
  send_on_enter BOOLEAN DEFAULT true,
  show_avatars  BOOLEAN DEFAULT true,
  compact_mode  BOOLEAN DEFAULT false,
  notifications BOOLEAN DEFAULT true,
  updated_at    FLOAT
);

ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow all" ON user_settings;
CREATE POLICY "Allow all" ON user_settings FOR ALL USING (true);

-- ============================================================
-- Done! Copy your project URL and anon key from:
-- Supabase Dashboard → Settings → API
-- ============================================================
