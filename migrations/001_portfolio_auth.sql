-- Creator accounts and access registry. Demo artifacts and graph state stay on disk.
CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY,
  email text NOT NULL,
  password_hash text NOT NULL,
  name text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_unique ON users(lower(email));
CREATE TABLE IF NOT EXISTS auth_sessions (
  token_hash text PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS auth_sessions_expiry ON auth_sessions(expires_at);
CREATE TABLE IF NOT EXISTS demo_owners (
  demo_id text PRIMARY KEY CHECK (demo_id ~ '^dm_[a-z0-9]{8}$'),
  owner_user_id uuid NOT NULL REFERENCES users(id),
  state text NOT NULL DEFAULT 'creating' CHECK (state IN ('creating','active','deleted')),
  published_version integer,
  snapshot_id text,
  created_at timestamptz NOT NULL DEFAULT now(),
  published_at timestamptz
);
CREATE INDEX IF NOT EXISTS demo_owners_owner ON demo_owners(owner_user_id, state);
CREATE TABLE IF NOT EXISTS published_media (
  demo_id text NOT NULL REFERENCES demo_owners(demo_id),
  version integer NOT NULL,
  path text NOT NULL,
  PRIMARY KEY (demo_id, version, path)
);
CREATE TABLE IF NOT EXISTS public_visits (
  session_id text PRIMARY KEY,
  demo_id text NOT NULL REFERENCES demo_owners(demo_id),
  visitor_hash text NOT NULL,
  published_version integer NOT NULL,
  snapshot_id text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS public_visits_actor ON public_visits(visitor_hash, demo_id);
CREATE TABLE IF NOT EXISTS visit_media (
  session_id text NOT NULL REFERENCES public_visits(session_id) ON DELETE CASCADE,
  demo_id text NOT NULL REFERENCES demo_owners(demo_id),
  path text NOT NULL,
  PRIMARY KEY (session_id, path)
);
CREATE TABLE IF NOT EXISTS auth_rates (
  key text PRIMARY KEY,
  window_start timestamptz NOT NULL,
  count integer NOT NULL
);
CREATE TABLE IF NOT EXISTS media_objects (
  demo_id text NOT NULL REFERENCES demo_owners(demo_id),
  path text NOT NULL,
  version integer NOT NULL DEFAULT 0,
  sha256 text NOT NULL,
  byte_size bigint NOT NULL,
  content_type text NOT NULL,
  object_key text,
  object_version text,
  PRIMARY KEY(demo_id,path,version)
);
