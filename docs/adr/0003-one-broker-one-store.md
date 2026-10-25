# ADR 0003: one broker, one store

Status: accepted. Service Bus covers jobs and events at this scale; Postgres with pgvector covers state and vectors. Adding a log-streaming platform or a search cluster doubles operations for no measured benefit here.
