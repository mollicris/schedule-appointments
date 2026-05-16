# Infrastructure: AI

Concrete adapters for AI services. Each adapter implements a port (interface) defined in the domain or application layer.

## Adapters to implement

- `claude_client.py` — Anthropic SDK wrapper with prompt caching enabled
- `whisper_client.py` — Audio transcription (OpenAI Whisper API)
- `vision_service.py` — Image understanding via Claude Vision
- `voyage_embeddings.py` — Multilingual embeddings for RAG
- `sentiment_analyzer.py` — Fast classifier using Claude Haiku
- `agent_graph.py` — LangGraph state machine orchestrating the bot
- `entity_extractor.py` — Structured entity extraction with tool calling

## Design rules

- All clients implement an interface from `domain/conversation` or `application/conversation`
- Costs are tracked via Langfuse (decorator at the call boundary)
- Every call has a tenant context so we can attribute costs per tenant
