# Telegram as Primary Messaging Channel for Phase 1

We decided to implement Telegram Bot API as the primary messaging interface for Phase 1, while preserving the `IMessengerAdapter` interface for future WhatsApp integration. WhatsApp Cloud API enforces a rigid 24-hour service window that prohibits sending unapproved dynamic messages (e.g. daily briefings, SLA alerts, bi-weekly reflections) without pre-registered paid templates. Telegram allows unconstrained 24/7 proactive messaging, rich Markdown formatting, and seamless audio message streaming at zero cost.
