#!/bin/bash
# audit-supabase.sh — Inspect Supabase database schema, RPC functions, RLS policies, and triggers
# Usage: bash scripts/audit-supabase.sh
#
# Prerequisites: supabase CLI installed and project linked (supabase link)
# Falls back to local migration file inspection if CLI is unavailable or not linked.

set -euo pipefail

echo "=== Supabase Backend Audit ==="
echo ""

# --- Check CLI availability ---
if ! command -v supabase &> /dev/null; then
  echo "WARNING: supabase CLI not found. Falling back to local migration files."
  echo ""

  if [ -d "supabase/migrations" ]; then
    echo "--- Local Migration Files ---"
    ls -la supabase/migrations/*.sql 2>/dev/null
    echo ""
    echo "--- Migration Contents (concatenated) ---"
    cat supabase/migrations/*.sql 2>/dev/null
  else
    echo "SKIP: No supabase/migrations directory found."
    echo "Cannot audit backend without CLI access or local migration files."
  fi
  exit 1
fi

# --- Check if project is linked ---
STATUS_OUTPUT=$(supabase status 2>&1 || true)
if echo "$STATUS_OUTPUT" | grep -qi "not linked\|error\|no project"; then
  echo "WARNING: Supabase project not linked. Falling back to local migrations."
  if [ -d "supabase/migrations" ]; then
    echo ""
    echo "--- Local Migration Files ---"
    ls -la supabase/migrations/*.sql 2>/dev/null
    echo ""
    for f in supabase/migrations/*.sql; do
      echo "=== $(basename "$f") ==="
      cat "$f"
      echo ""
    done
  fi
  exit 1
fi

echo "--- Supabase Project Status ---"
echo "$STATUS_OUTPUT"
echo ""

# --- Table listing ---
echo "--- All Tables (public schema) ---"
supabase db execute "
  SELECT table_name, 
         (SELECT count(*) FROM information_schema.columns c WHERE c.table_name = t.table_name AND c.table_schema = 'public') as column_count
  FROM information_schema.tables t
  WHERE table_schema = 'public' 
    AND table_type = 'BASE TABLE'
  ORDER BY table_name;
" 2>&1 || echo "FAIL: Could not list tables"
echo ""

# --- Full column details ---
echo "--- Column Details (all public tables) ---"
supabase db execute "
  SELECT table_name, column_name, data_type, is_nullable, column_default
  FROM information_schema.columns
  WHERE table_schema = 'public'
  ORDER BY table_name, ordinal_position;
" 2>&1 || echo "FAIL: Could not get column details"
echo ""

# --- Primary keys ---
echo "--- Primary Keys ---"
supabase db execute "
  SELECT tc.table_name, kcu.column_name
  FROM information_schema.table_constraints tc
  JOIN information_schema.key_column_usage kcu 
    ON tc.constraint_name = kcu.constraint_name
  WHERE tc.table_schema = 'public' 
    AND tc.constraint_type = 'PRIMARY KEY'
  ORDER BY tc.table_name;
" 2>&1 || echo "FAIL: Could not get primary keys"
echo ""

# --- Foreign keys ---
echo "--- Foreign Keys ---"
supabase db execute "
  SELECT tc.table_name, kcu.column_name, 
         ccu.table_name AS referenced_table, ccu.column_name AS referenced_column
  FROM information_schema.table_constraints tc
  JOIN information_schema.key_column_usage kcu 
    ON tc.constraint_name = kcu.constraint_name
  JOIN information_schema.constraint_column_usage ccu 
    ON tc.constraint_name = ccu.constraint_name
  WHERE tc.table_schema = 'public' 
    AND tc.constraint_type = 'FOREIGN KEY'
  ORDER BY tc.table_name;
" 2>&1 || echo "FAIL: Could not get foreign keys"
echo ""

# --- Indexes ---
echo "--- Indexes ---"
supabase db execute "
  SELECT tablename, indexname, indexdef
  FROM pg_indexes
  WHERE schemaname = 'public'
  ORDER BY tablename, indexname;
" 2>&1 || echo "FAIL: Could not get indexes"
echo ""

# --- RLS status ---
echo "--- Row Level Security Status ---"
supabase db execute "
  SELECT schemaname, tablename, rowsecurity
  FROM pg_tables
  WHERE schemaname = 'public'
  ORDER BY tablename;
" 2>&1 || echo "FAIL: Could not check RLS status"
echo ""

# --- RLS policies ---
echo "--- RLS Policies ---"
supabase db execute "
  SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check
  FROM pg_policies
  WHERE schemaname = 'public'
  ORDER BY tablename, policyname;
" 2>&1 || echo "FAIL: Could not get RLS policies"
echo ""

# --- RPC functions ---
echo "--- RPC Functions (public schema) ---"
supabase db execute "
  SELECT p.proname AS function_name,
         pg_get_function_arguments(p.oid) AS arguments,
         pg_get_function_result(p.oid) AS return_type,
         CASE p.prosecdef WHEN true THEN 'SECURITY DEFINER' ELSE 'SECURITY INVOKER' END AS security,
         p.provolatile AS volatility,
         obj_description(p.oid) AS description
  FROM pg_proc p
  JOIN pg_namespace n ON p.pronamespace = n.oid
  WHERE n.nspname = 'public'
    AND p.prokind = 'f'
  ORDER BY p.proname;
" 2>&1 || echo "FAIL: Could not get RPC functions"
echo ""

# --- RPC function bodies ---
echo "--- RPC Function Bodies ---"
supabase db execute "
  SELECT p.proname AS function_name,
         pg_get_functiondef(p.oid) AS full_definition
  FROM pg_proc p
  JOIN pg_namespace n ON p.pronamespace = n.oid
  WHERE n.nspname = 'public'
    AND p.prokind = 'f'
  ORDER BY p.proname;
" 2>&1 || echo "FAIL: Could not get function bodies"
echo ""

# --- Triggers ---
echo "--- Triggers ---"
supabase db execute "
  SELECT trigger_name, event_manipulation, event_object_table, action_timing, action_statement
  FROM information_schema.triggers
  WHERE trigger_schema = 'public'
  ORDER BY event_object_table, trigger_name;
" 2>&1 || echo "FAIL: Could not get triggers"
echo ""

# --- Realtime enabled tables ---
echo "--- Realtime Configuration ---"
supabase db execute "
  SELECT * FROM realtime.subscription LIMIT 1;
" 2>&1 || echo "INFO: Could not query realtime subscriptions (may require elevated access)"

# Check publication
supabase db execute "
  SELECT tablename
  FROM pg_publication_tables
  WHERE pubname = 'supabase_realtime';
" 2>&1 || echo "INFO: Could not check realtime publication"
echo ""

# --- Storage buckets ---
echo "--- Storage Buckets ---"
supabase db execute "
  SELECT id, name, public, file_size_limit, allowed_mime_types
  FROM storage.buckets
  ORDER BY name;
" 2>&1 || echo "INFO: Could not query storage buckets (may not exist)"
echo ""

echo "=== Supabase Audit Complete ==="
