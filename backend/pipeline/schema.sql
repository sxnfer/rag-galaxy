-- RAG Galaxy schema. Safe to run again: every statement is "if not exists".
create extension if not exists vector;

-- M1: one row per document we know about. A row exists before the file does
-- (from the scraped project page); sha256 and local_path are filled in when
-- the PDF is registered. The unique keys make re-runs idempotent.
create table if not exists manifest (
    id           bigserial primary key,
    project_id   text not null,          -- CDM reference, e.g. TUEV-RHEIN1317024781.22
    project_title text,
    doc_type     text not null,          -- pdd | validation_report | monitoring_report | other
    link_text    text,
    source_url   text not null,
    sha256       text unique,            -- fingerprint of the file's bytes, null until registered
    local_path   text,
    page_fetched_at timestamptz,         -- when we read the project page
    fetched_at   timestamptz,            -- when the file was registered
    unique (project_id, source_url)
);

-- M2: one row per parsed page, plus a per-document quality report.
create table if not exists pages (
    doc_sha256   text not null references manifest(sha256),
    page_no      int  not null,          -- 1-based, as printed in a PDF viewer
    text         text not null,
    headings     text[] not null default '{}',
    n_tables     int  not null default 0,
    tables_md    text[] not null default '{}',
    is_scanned   boolean not null default false,
    flags        text[] not null default '{}',   -- from the quality checks
    primary key (doc_sha256, page_no)
);

create table if not exists quality_reports (
    doc_sha256   text primary key references manifest(sha256),
    report       jsonb not null,
    created_at   timestamptz not null default now()
);

-- M3: chunks and their embeddings. model + model_version on every row
-- (the same-model rule): questions must be embedded with the same pair.
create table if not exists chunks (
    id           bigserial primary key,
    doc_sha256   text not null references manifest(sha256),
    chunker      text not null,          -- fixed | structure
    chunk_size   int  not null,
    ord          int  not null,          -- order within the document
    page_start   int  not null,
    page_end     int  not null,
    breadcrumb   text not null,
    text         text not null,
    model        text not null,
    model_version text not null,
    embedding    vector(384) not null,
    unique (doc_sha256, chunker, chunk_size, ord)
);
create index if not exists chunks_run on chunks (chunker, chunk_size, model);

-- M4: every question the app answers, for the feedback loop.
create table if not exists traces (
    id           uuid primary key,
    question     text not null,
    trace        jsonb not null,
    created_at   timestamptz not null default now()
);

-- Libraries (2026-11-09): separate document collections, searched one at a time.
-- Everything that existed before belongs to the original "carbon" library.
alter table manifest add column if not exists library text not null default 'carbon';
alter table chunks   add column if not exists library text not null default 'carbon';
alter table traces   add column if not exists library text not null default 'carbon';
create index if not exists chunks_library_run on chunks (library, chunker, chunk_size, model);
-- HNSW indexes are now one per library and run (chunks_hnsw_<library>_<chunker>_<size>).
-- The old per-run ones would mix libraries, so they go; `pipeline hnsw` rebuilds them.
drop index if exists chunks_hnsw_fixed_300;
drop index if exists chunks_hnsw_structure_300;

-- Table libraries (2026-11-11): a chunk made from a table row keeps the row's raw numbers
-- next to its words, e.g. {"item": "Kia Niro Electric", "facet": "range", "stats": {...}}.
-- The rank stage sorts by them. Chunks cut from PDFs leave it null.
alter table chunks add column if not exists meta jsonb;
