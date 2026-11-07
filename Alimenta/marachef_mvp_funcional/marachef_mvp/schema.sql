CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS dishes (
    id uuid PRIMARY KEY,
    name text NOT NULL,
    key text NOT NULL UNIQUE,
    aliases text[] NOT NULL DEFAULT '{}'
);

ALTER TABLE dishes ADD COLUMN IF NOT EXISTS cover_photo bytea;

CREATE TABLE IF NOT EXISTS sources (
    id uuid PRIMARY KEY,
    dish_id uuid REFERENCES dishes,
    title text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('documento', 'video', 'comentario')),
    scope text NOT NULL CHECK (scope IN ('oficial', 'demo', 'institucional')),
    actor text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    blob text,
    mime text,
    details jsonb NOT NULL DEFAULT '{}',
    active_revision bigint,
    parent_revision bigint,
    CHECK ((scope = 'institucional') = (dish_id IS NULL)),
    CHECK ((kind = 'comentario') = (parent_revision IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS revisions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id uuid NOT NULL REFERENCES sources,
    version integer NOT NULL,
    status text NOT NULL CHECK (status IN ('pendente', 'aprovado', 'rejeitado')),
    data jsonb NOT NULL,
    actor text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_id, version)
);

CREATE INDEX IF NOT EXISTS sources_scope_dish ON sources(scope, dish_id);
CREATE INDEX IF NOT EXISTS sources_parent ON sources(parent_revision);

CREATE TABLE IF NOT EXISTS chunks (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    revision_id bigint NOT NULL REFERENCES revisions,
    body text NOT NULL,
    page integer,
    step text,
    step_index integer,
    start_seconds double precision,
    end_seconds double precision,
    embedding vector(768) NOT NULL,
    keywords tsvector GENERATED ALWAYS AS (to_tsvector('portuguese', body)) STORED
);

ALTER TABLE chunks ADD COLUMN IF NOT EXISTS step_index integer;
CREATE INDEX IF NOT EXISTS chunks_revision ON chunks(revision_id);
