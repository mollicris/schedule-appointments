# Bounded Context: Conversation

**Responsibility**: Live conversations with clients across channels (WhatsApp, Instagram, web widget). Owns state machine, message history, sentiment, and human-handover triggers.

## Aggregates

- **`Conversation`** (root) — Active or recent dialogue between a Client and the bot. Holds the state machine cursor, collected entities, and message log.

## Entities

- `Message` — A single inbound or outbound message (text, audio, image, button)
- `EntityExtraction` — Parsed result from one Claude call (intent, entities, confidence)
- `HumanHandoff` — Escalation record with reason and notified staff

## Value Objects

- `ConversationState` — Enum of states (see specs: IDLE, EXTRACTING_ENTITIES, SELECTING_DATE, ...)
- `Channel` — WHATSAPP, INSTAGRAM, WEB_WIDGET
- `Sentiment` — POSITIVE, NEUTRAL, FRUSTRATED, ANGRY (+ confidence)

## Events

- `MessageReceived`, `MessageSent`
- `StateTransitioned` — Drives analytics on funnel
- `HandoffRequested` — Triggers Slack/email to staff
- `ConversationStalled` — Inactive >30 min, reset state

## Notes

The state machine logic itself lives in **`infrastructure/ai/agent_graph.py`** (LangGraph), but the *state* is part of the Conversation aggregate. Domain remains pure: it knows what states exist and which transitions are valid, but not *how* the AI decides.
