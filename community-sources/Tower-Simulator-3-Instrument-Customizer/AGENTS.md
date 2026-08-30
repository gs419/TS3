# Repository Guidelines

## Project Structure & Module Organization
This repository is a Laravel 12 application for Tower! Simulator 3 tooling. Core application code lives in `app/`, including controllers, models, support services, and console commands. Blade views are in `resources/views`, frontend assets in `resources/js` and `resources/css`, and route definitions in `routes/web.php`. Database schema and seeders live under `database/migrations`, `database/seeders`, and `database/factories`. Feature and unit tests are in `tests/Feature` and `tests/Unit`.

## Build, Test, and Development Commands
- `php artisan serve`: run the local Laravel server.
- `npm run dev`: run Vite for live frontend asset rebuilding.
- `npm run build`: build production frontend assets into `public/build`.
- `php artisan test`: run PHPUnit feature and unit tests.
- `php artisan migrate --seed`: apply schema changes and seed the baseline database.

## Coding Style & Naming Conventions
Follow Laravel conventions and existing project patterns. Use 4-space indentation in PHP and keep Blade markup readable with one attribute per line when forms grow. Class names use `StudlyCase`; methods and variables use `camelCase`; database columns use `snake_case`. Keep new internal paths space-free. Prefer small controllers, Form Request validation, and focused support classes. Use `php artisan test` and `npm run build` as the practical validation baseline.

## Testing Guidelines
Tests use PHPUnit with Laravel’s testing helpers. Put integration and HTTP coverage in `tests/Feature`; keep isolated logic in `tests/Unit`. Name tests descriptively, for example `test_admin_can_create_a_database_variant_with_upload`. When adding CRUD or permission changes, cover both allowed and forbidden paths. Use `RefreshDatabase` for DB-backed tests.

## Commit & Pull Request Guidelines
There is no strong commit history convention established in this workspace yet. Use short imperative commit messages such as `Add admin airport source CRUD` or `Refactor ADIRS data loading`. For pull requests, include: scope summary, affected routes/files, migration impact, test results, and screenshots for UI changes.

## Security & Configuration Tips
Do not hardcode game install paths into app logic. Store local source data on Laravel storage and keep environment-specific settings in `.env`.

## Current Next Steps
- Continue rebuilding from the reset baseline with Fortify auth and signed-in workspace management as the current foundation.
- Keep the base airport, database variant, and instrument set catalog file-based from `storage/app/tower_data`; persist only user workspaces and per-screen changes in the database.
- Treat instrument folders as shared instrument sets instead of per-screen look variants.
- The ADIRS sidebar editor now loads from workspace base files and stores overrides in `WorkspaceScreen`; build out area editing depth, multiwindow mode, and the remaining screen editors next.
- Use `docs/tower-data-and-rendering-notes.md` as the reference for tower data layout and recovered rendering behavior.
