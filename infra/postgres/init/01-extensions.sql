-- V1 needs pg_trgm for fuzzy/dedup search (see NON_NEGOTIABLES #1).
-- Schema itself lands in T03; this only prepares extensions on a fresh db.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
