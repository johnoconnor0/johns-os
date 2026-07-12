# Supabase Backend Audit Guide

This reference document provides the detailed checklist for Phase 10 (Supabase Backend Audit) and Phase 11 (Frontend ↔ Backend Alignment). Read this before starting those phases.

## Table of Contents

1. [Accessing the Database](#1-accessing-the-database)
2. [Schema Audit Checklist](#2-schema-audit-checklist)
3. [RPC Function Audit](#3-rpc-function-audit)
4. [RLS Policy Audit](#4-rls-policy-audit)
5. [Trigger & Realtime Audit](#5-trigger--realtime-audit)
6. [Storage Audit](#6-storage-audit)
7. [Frontend–Backend Alignment](#7-frontendbackend-alignment)
8. [Common Supabase Anti-Patterns](#8-common-supabase-anti-patterns)
9. [Useful SQL Queries](#9-useful-sql-queries)

---

## 1. Accessing the Database

Use the first available method. Do not mix methods within a single audit — pick one and stick with it for consistency.

### Option A: Supabase CLI (preferred)

```bash
# Check availability
supabase --version

# Check project link status
supabase status

# Execute SQL
supabase db execute "SELECT ..."

# Generate TypeScript types (for alignment checks)
supabase gen types typescript --local > /tmp/supabase-types.ts
# or for linked remote project:
supabase gen types typescript --linked > /tmp/supabase-types.ts

# List migrations
supabase migration list

# Diff local vs remote schema
supabase db diff
```

### Option B: Supabase MCP

If a Supabase MCP server is available in the environment, use it to execute SQL queries. The MCP provides `execute_sql` and related tools. Query syntax is identical — just use the MCP tool instead of CLI.

### Option C: Management API

As a last resort, use the Supabase Management API. This requires a service role key or management token. Use only for schema inspection, not for data queries.

### Option D: Local files only

If no live access is available, audit using:
- `supabase/migrations/*.sql` — all migration files
- `supabase/seed.sql` — seed data
- Generated type files (e.g., `database.types.ts`, `src/types/supabase.ts`)
- Supabase client usage in frontend code

Note this approach cannot verify the live database state — only what the migrations define.

---

## 2. Schema Audit Checklist

For every table in the `public` schema:

### Columns
- [ ] Column names use consistent casing (`snake_case` is standard for Postgres)
- [ ] Data types are appropriate (don't use `text` where `uuid`, `timestamptz`, `integer`, `boolean`, `jsonb`, or an enum would be more correct)
- [ ] `NOT NULL` constraints exist on required fields
- [ ] Default values are set where appropriate (`gen_random_uuid()` for UUIDs, `now()` for timestamps)
- [ ] `created_at` column exists with `DEFAULT now()` and type `timestamptz`
- [ ] `updated_at` column exists where rows can be modified, with a trigger to auto-update it

### Keys & References
- [ ] Primary key is defined (usually `id uuid DEFAULT gen_random_uuid()`)
- [ ] Foreign keys reference the correct parent table and column
- [ ] Foreign key `ON DELETE` behaviour is intentional (`CASCADE`, `SET NULL`, `RESTRICT`)
- [ ] No orphaned foreign key references (pointing to tables that no longer exist)

### Indexes
- [ ] Primary key columns are indexed (automatic in Postgres)
- [ ] Foreign key columns have indexes (NOT automatic — must be created manually)
- [ ] Columns used in frequent `WHERE` clauses have indexes
- [ ] Columns used in `ORDER BY` have indexes if the table is large
- [ ] Composite indexes exist where multi-column filters are common
- [ ] No duplicate or redundant indexes

### Constraints
- [ ] `CHECK` constraints for value validation where appropriate (e.g., `status IN ('active', 'inactive')`)
- [ ] `UNIQUE` constraints where business logic requires uniqueness (e.g., email per org)

---

## 3. RPC Function Audit

For every function in the `public` schema:

### Signature
- [ ] Parameter names are clear and correctly typed
- [ ] Return type matches what the frontend expects
- [ ] `RETURNS SETOF` vs single-row return is correct for the use case
- [ ] Default parameter values are set where appropriate

### Security
- [ ] `SECURITY DEFINER` is only used when the function genuinely needs to bypass RLS (e.g., admin operations)
- [ ] If `SECURITY DEFINER`, the function includes `SET search_path = public, extensions` to prevent search path injection
- [ ] `SECURITY INVOKER` is used for standard user-context operations
- [ ] Functions validate their inputs — don't blindly trust parameters from the client

### Implementation
- [ ] SQL is correct and efficient — no unnecessary subqueries, CTEs where appropriate
- [ ] Error handling exists for edge cases (e.g., row not found, permission denied)
- [ ] Functions that modify data use transactions or are inherently atomic
- [ ] `VOLATILE` / `STABLE` / `IMMUTABLE` is correctly declared

### Exposure
- [ ] Functions intended for client use are in the `public` schema (or exposed via PostgREST)
- [ ] Internal helper functions are in a private schema (e.g., `private` or `internal`) and not exposed to the API
- [ ] Functions are granted `EXECUTE` to the appropriate roles (`anon`, `authenticated`, `service_role`)

---

## 4. RLS Policy Audit

### Enablement
- [ ] RLS is enabled on **every** table that stores user data
- [ ] Tables that are genuinely public (e.g., static lookup data) can have RLS disabled, but this must be an intentional decision

### Policy Coverage
For each user-facing table, verify policies exist for:
- [ ] `SELECT` — users can only read rows they're authorised to see
- [ ] `INSERT` — users can only create rows in their own scope (e.g., their org)
- [ ] `UPDATE` — users can only modify rows they own or are authorised to edit
- [ ] `DELETE` — users can only delete rows they're authorised to remove

### Policy Quality
- [ ] No policy uses `USING (true)` on sensitive tables — this effectively disables RLS
- [ ] Policies reference `auth.uid()` to scope access to the authenticated user
- [ ] Org-scoped access correctly checks org membership, not just `auth.uid()`
- [ ] `WITH CHECK` expressions are set on INSERT/UPDATE policies to prevent users injecting data they shouldn't
- [ ] Policies are `PERMISSIVE` by default — `RESTRICTIVE` only when intentionally layering restrictions

### Common RLS Mistakes
- Forgetting to add RLS to junction/join tables
- Using `auth.uid()` directly in a policy when the user ID comes from a related table (need a subquery)
- Not testing RLS with the `anon` role — unauthenticated users shouldn't access protected data
- Allowing users to UPDATE their own `role` or `org_id` columns without restriction

---

## 5. Trigger & Realtime Audit

### Triggers
- [ ] `updated_at` trigger exists on all mutable tables:
  ```sql
  CREATE TRIGGER set_updated_at BEFORE UPDATE ON table_name
  FOR EACH ROW EXECUTE FUNCTION moddatetime('updated_at');
  ```
  (Or a custom function if `moddatetime` extension is not enabled)
- [ ] Triggers fire on the correct events (`INSERT`, `UPDATE`, `DELETE`)
- [ ] Trigger functions don't have performance-impacting side effects (e.g., calling external APIs synchronously)
- [ ] No orphaned triggers referencing dropped functions

### Realtime
- [ ] Tables that the frontend subscribes to are added to the `supabase_realtime` publication
- [ ] Tables with sensitive data that use realtime have RLS policies that filter appropriately
- [ ] Frontend realtime subscriptions include proper cleanup (unsubscribe on unmount)
- [ ] Realtime is not enabled on high-write-volume tables unless genuinely needed

---

## 6. Storage Audit

### Buckets
- [ ] Bucket `public` flag is intentional — public buckets are accessible without auth
- [ ] `file_size_limit` is set to prevent abuse
- [ ] `allowed_mime_types` restricts uploads to expected file types

### Storage Policies
- [ ] RLS-style policies exist on storage objects
- [ ] Upload policies restrict who can upload and to which paths
- [ ] Download policies match the intended access model
- [ ] Delete policies prevent users from removing others' files

---

## 7. Frontend–Backend Alignment

### Type Generation
Run `supabase gen types typescript` and compare the output against the project's type definitions. Common locations for Supabase types:
- `src/types/supabase.ts`
- `src/lib/database.types.ts`
- `types/database.ts`
- `database.types.ts` (project root)

### What to Compare

**Table types:**
```typescript
// Generated type
Database['public']['Tables']['users']['Row']
// Frontend usage
interface User { ... }
```
Every field in the generated type should exist in the frontend type. Extra frontend fields (computed/derived) are fine, but missing database fields suggest stale types.

**RPC types:**
```typescript
// Generated
Database['public']['Functions']['get_user_stats']['Args']
Database['public']['Functions']['get_user_stats']['Returns']
// Frontend call
supabase.rpc('get_user_stats', { user_id: '...' })
```
The args object must match the function's parameter names and types.

**Enum types:**
```typescript
// Database enum
Database['public']['Enums']['user_role'] // 'admin' | 'member' | 'viewer'
// Frontend
type UserRole = 'admin' | 'member' | 'viewer'
```
Values must be identical. A mismatch here causes runtime errors.

### Query Audit Methodology

Search for all Supabase client calls:
```bash
grep -rn "\.from(\|\.rpc(\|supabase\." --include="*.ts" --include="*.tsx" . | grep -v node_modules | grep -v .git | grep -v dist
```

For each call, verify:
1. The table/function name exists in the database
2. `.select()` column names exist on the table
3. `.eq()`, `.in()`, `.match()` filter columns exist and are the correct type
4. `.insert()` / `.update()` payloads include all required columns
5. `.order()` columns exist
6. The TypeScript type used for the result matches the actual return shape

### Regenerating Types

If types are stale, the fix is:
```bash
supabase gen types typescript --linked > src/types/supabase.ts
# or for local development:
supabase gen types typescript --local > src/types/supabase.ts
```

---

## 8. Common Supabase Anti-Patterns

Flag these if found:

1. **Using service role key in client-side code** — the service role key bypasses RLS and should only be used server-side
2. **N+1 queries** — fetching a list and then querying details for each item individually instead of using joins or `.select('*, related_table(*)')`
3. **No error handling on Supabase calls** — every `.from()` / `.rpc()` call should check `error` before using `data`
4. **String-interpolated SQL in RPC functions** — use parameterised queries to prevent injection
5. **Missing `.single()` / `.maybeSingle()`** — fetching a single row without `.single()` returns an array, causing type confusion
6. **Stale generated types** — types were generated once and never updated after schema changes
7. **Using `.select('*')` everywhere** — fetches unnecessary columns, increases payload size, and can leak sensitive fields
8. **No pagination** — `.from('table').select('*')` without `.range()` or `.limit()` on large tables
9. **Hardcoded schema assumptions** — code that breaks if a column is renamed or removed, rather than failing gracefully
10. **Auth state race conditions** — calling Supabase before the auth session is initialised

---

## 9. Useful SQL Queries

These can be run via `supabase db execute` or through the MCP.

### Tables without RLS
```sql
SELECT schemaname, tablename
FROM pg_tables
WHERE schemaname = 'public' AND rowsecurity = false;
```

### Tables without updated_at triggers
```sql
SELECT t.tablename
FROM pg_tables t
WHERE t.schemaname = 'public'
  AND NOT EXISTS (
    SELECT 1 FROM information_schema.triggers tr
    WHERE tr.event_object_table = t.tablename
      AND tr.trigger_name LIKE '%updated_at%'
  );
```

### Foreign keys without indexes
```sql
SELECT tc.table_name, kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
WHERE tc.table_schema = 'public' AND tc.constraint_type = 'FOREIGN KEY'
  AND NOT EXISTS (
    SELECT 1 FROM pg_indexes pi
    WHERE pi.schemaname = 'public'
      AND pi.tablename = tc.table_name
      AND pi.indexdef LIKE '%' || kcu.column_name || '%'
  );
```

### Functions with SECURITY DEFINER but no search_path set
```sql
SELECT p.proname, pg_get_functiondef(p.oid)
FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
WHERE n.nspname = 'public'
  AND p.prosecdef = true
  AND pg_get_functiondef(p.oid) NOT LIKE '%search_path%';
```

### Overly permissive RLS policies (USING true)
```sql
SELECT tablename, policyname, cmd, qual
FROM pg_policies
WHERE schemaname = 'public'
  AND qual = 'true';
```

### Unused functions (defined but no dependencies)
```sql
SELECT p.proname
FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
WHERE n.nspname = 'public'
  AND p.prokind = 'f'
  AND NOT EXISTS (
    SELECT 1 FROM pg_depend d
    WHERE d.refobjid = p.oid AND d.deptype = 'n'
  );
```
