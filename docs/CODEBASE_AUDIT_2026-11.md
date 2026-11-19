# Kiemaen AI repository audit — 10 November 2026

## Scope and method
Reviewed the recursive Git tree on `main` (109 tracked entries) and inspected the active FastAPI entry point, browser chat flow, AI provider adapter, authentication/database modules, specialist engines, code execution helpers, voice clients, experimental app package, and auto-evolution service. This is a source-code audit, not a live filesystem or production-database inspection. Render's connected integration exposes configuration, logs and deployment metadata but not an interactive shell or live file transfer.

## Runtime entry point
Render starts `uvicorn app.main:app`. `app/main.py` is a compatibility wrapper importing `main.app`. The production application is therefore root `main.py` plus its imported `core/*` and `tools/*` modules. Several other application paths are not mounted by this entry point.

## Confirmed findings
1. `core/brain.py` discards `user_key`, `user_id`, and `is_admin`; normal chat has no authenticated conversational memory. Quick/Deep routing exists and the Groq adapter has limited model fallback, but no independent provider abstraction or research retrieval pipeline is wired into this chat flow.
2. `core/memory.py` is a small global key/value SQLite store in `agent_framework.db`, not per-user semantic or full-text conversational memory. It is not imported by the active chat route.
3. `core/database.py` hard-codes `sqlite+aiosqlite:///auth.db`; it does not use the Aiven `DATABASE_URL`. Browser authentication, sessions, tasks and pins are separately stored in `kiemaen.db` through `core/auth.py`.
4. `main.py` advertises an FTS5 `memory.db` and capabilities not wired into the active chat path. Treat `/capabilities` as aspirational until verified.
5. `core/router.py` owns another SQLite `chat.db`, implements separate chat history and unsafe code execution, but is not included by `main.py`.
6. `tools/coder.py` can write arbitrary local paths and run scripts as a subprocess. `core/code_engine.py` uses Python `exec`; restricted builtins and a process timeout are not an OS sandbox.
7. `core/security.py` contains placeholder middleware and edit approval/rollback functions. Those functions do not implement an enforceable change-management workflow.
8. `core/math_engine.py` assumes a fixed pip value multiplier for trade sizing and does not validate physical units or instrument contract specifications. `core/market_engine.py` fetches daily Yahoo candles regardless of requested timeframe and generates percentage-based generic stop/target distances.
9. `core/life_engine.py` and `core/converter_engine.py` rely on keyword/number extraction and fixed assumptions; they are not general reasoning or unit-conversion systems.
10. `core/task_engine.py`, `core/doc_engine.py`, and `core/asset_engine.py` store data in local JSON files with no user isolation, concurrency control or durable hosted persistence.
11. Experimental `app/agents/kim.py`, `kit.py`, and `kat.py` are not imported by the active entry point. They contain broker-order, SMTP-outreach and Telegram-broadcast functionality that should not be part of Kiemaen's unified assistant surface.
12. Voice clients had inconsistent device-action handling. The Huawei client asked the model to emit shell commands even though the server safety helper blocks those markers; the older hands-free client executed alarm markers without confirmation.
13. `app/config.py` contains a weak hard-coded admin password default, while `app/database.py` has a separate hard-coded SQLite URL. These belong to an unused legacy app path and must not be reactivated as-is.
14. Upload handling previously read arbitrary file sizes and accepted broad content based mainly on filename/content type, creating resource-exhaustion and parser attack exposure.

## Changes in this commit
- Added bounded upload reads, an 8 MB image limit, a 12 MB document limit, image signature checks (JPEG/PNG/WebP), explicit document allow-list, UTF-8 checks, PDF signature checks, DOCX archive structure/expanded-size checks, and a 100-page PDF cap.
- Added unit tests for the upload boundary.
- Disabled automatic alarm execution in the legacy Termux voice client and removed shell-command solicitation from the Huawei voice prompt. Model output is treated as untrusted.
- Removed the three unused Kim/Kit/Kat agent modules from the Kiemaen app package, consistent with the unified-assistant design.

- Added salted PBKDF2 hashes for new email verification/login codes, SHA-256 hashes for newly issued browser session tokens, backward compatibility for unexpired legacy plaintext credentials, and a five-failure/10-minute process-local OTP throttle. A durable shared limiter remains part of the PostgreSQL migration.

- Updated the capabilities endpoint to distinguish working features from planned features, rather than advertising inactive FTS5 memory, autonomous execution or PostgreSQL support. Added baseline browser security headers. Disabled the unused legacy router's subprocess code execution path. The separate JWT API refresh-token store now hashes newly issued refresh tokens while accepting existing plaintext tokens for compatibility.

## Work still requiring a data-safety plan
- Do not switch browser authentication or task storage to PostgreSQL until a verified export/backup of live `kiemaen.db` has been obtained or it is established that the live file no longer exists.
- Consolidate account systems only after schema mapping, password-hash compatibility checks, duplicate identity handling, session revocation design and migration tests.
- Add Alembic migrations and use Aiven only after async-driver availability and TLS configuration are tested.
- Do not advertise memory, autonomous actions or self-learning until each capability has end-to-end tests.
