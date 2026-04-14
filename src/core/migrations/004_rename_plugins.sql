-- 004_rename_plugins.sql
-- Rename plugin entries in schema_versions to match new directory names.
-- Safe to re-run: UPDATE WHERE ... only affects rows that exist.
UPDATE schema_versions SET plugin_name = 'memo' WHERE plugin_name = 'recorder';
UPDATE schema_versions SET plugin_name = 'reflect' WHERE plugin_name = 'journal';
UPDATE schema_versions SET plugin_name = 'track' WHERE plugin_name = 'planner';
