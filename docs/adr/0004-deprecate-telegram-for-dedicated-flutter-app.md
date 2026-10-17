# 0004. Deprecate Telegram in Favor of Dedicated Flutter Mobile App

## Status
Accepted (Supersedes ADR 0001)

## Context
In ADR 0001, Telegram was selected as the Phase 1 interface to quickly deliver conversational text and voice capabilities without app store distribution overhead. However, real-world command usage revealed clear limitations:
1. Managing 39 soldiers across 6 teams, mentorship contracts, 1-on-1 meeting records, and secondary duties (נע"ת) purely via conversational text is cognitively heavy and prone to command fatigue.
2. Managing operational tasks and strict deadlines (תג"ב) requires visual sorting, urgency grouping (overdue, due today, priority tiers), and one-touch swipe actions rather than chat commands.
3. The commander decided to drop Telegram entirely and consolidate all interactions (People CRUD, Task CRUD, LLM Agent chat, Voice-In / Text-Out, and FCM push notifications) into a dedicated Flutter Android mobile application.

## Decision
1. Fully deprecate Telegram as a user-facing client.
2. The dedicated Flutter Android application (`mobile/`) becomes the single, primary client for the Ramad Assistant system.
3. The FastAPI backend on Google Cloud Run will serve as the mobile app's REST/WebSocket API, retaining the LangGraph multi-agent orchestrator, SQLite/Postgres repository, and Gemini Multimodal voice processor.
4. Push notifications (Daily Briefings, Overdue SLA alerts, Bi-weekly debrief triggers) will be routed exclusively via Firebase Cloud Messaging (FCM) to the mobile app.

## Consequences
- **Positive**: Single clean architecture; superior UX tailored exactly to the commander's mental model; eliminates Telegram bot maintenance, webhook complexities, and external chat app dependencies.
- **Trade-off**: Requires maintaining a Flutter codebase and deploying release APKs directly to the Android device.
