# Isolated Thread ID for Bi-weekly Reflection Sessions

We decided to execute bi-weekly reflection sessions in dedicated LangGraph threads (`thread_reflection_{YYYY-MM-DD}`) isolated from the default daily user thread (`thread_user_{user_id}`). A single unified conversation thread causes context leakage when an ad-hoc command (e.g. task creation or soldier lookup) is sent while a multi-turn philosophical debrief is active. Isolating threads preserves the multi-turn state of the reflection dialogue while allowing immediate, uncorrupted routing for daily operational tasks.
