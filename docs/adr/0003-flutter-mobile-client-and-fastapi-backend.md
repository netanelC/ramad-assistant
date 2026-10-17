# 0003. Dedicated Flutter Android Client and FastAPI Unified Backend

## Status
Accepted

## Context
The initial implementation (Phase 1) relied on Telegram as the primary user interface. While Telegram provided zero-cost messaging, rich markdown, and audio messages without app store overhead, the section head (רמ"ד) required:
1. Fast, visual, and intuitive CRUD operations on soldiers, teams, and tasks rather than text-only chat commands.
2. Direct mobile push notifications for SLA breaches and briefings without relying on Telegram's messaging channel.
3. A unified agent interface that lives natively alongside structured data screens.
4. A transition path where both Telegram and the mobile app operate concurrently until the mobile client is mature enough to deprecate Telegram.

## Decision
1. Develop a dedicated Android mobile client using **Flutter** (Dart), compiling to a standalone APK with native RTL (Hebrew) support and Material 3 design.
2. Extend the existing FastAPI backend on Google Cloud Run to expose RESTful endpoints (`/api/v1/soldiers`, `/api/v1/tasks`, `/api/v1/agent/chat`, `/api/v1/notifications`) sharing the exact same SQLite/Postgres repository and LangGraph multi-agent orchestrator.
3. Implement push notifications via **Firebase Cloud Messaging (FCM)**.
4. Postpone client authentication to future iterations (no auth in initial MVP per user directive).
5. Architecture is online-first with local caching.

## Consequences
- **Positive**: Full visual control over people and task management; rich native Android experience with voice, push notifications, and chat; complete data consistency between Telegram and Mobile App.
- **Trade-off**: Requires maintaining both the FastAPI backend and a Flutter client codebase; offline capabilities are limited to read-cache in MVP.
