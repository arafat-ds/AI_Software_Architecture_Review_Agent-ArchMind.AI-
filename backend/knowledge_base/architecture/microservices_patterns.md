# Microservices Architecture Patterns

## Overview

Microservices decompose a system into small, independently deployable services.
Each service owns its data, exposes a well-defined API, and can be deployed and
scaled independently. The pattern trades operational complexity for deployment
flexibility and bounded scalability.

## Service Decomposition Principles

### Bounded Context Alignment

Services should align with Domain-Driven Design bounded contexts. Each service
encapsulates one coherent domain concept with its own ubiquitous language.

Decomposition heuristics:
- One database schema per service (database-per-service pattern).
- Service boundaries aligned with team ownership (Conway's Law).
- Services communicate via well-defined contracts (API-first design).

### Single Responsibility

A microservice that accumulates multiple unrelated capabilities becomes a
distributed monolith. Each service should have exactly one reason to change.

Remediation: Split services by capability. Introduce an API gateway for cross-cutting
concerns like authentication and rate limiting rather than embedding them in each service.

## Communication Patterns

### Synchronous Communication Anti-Patterns

Deep synchronous call chains create cascading failure: if service D fails,
services A, B, C that chain through it all fail. Response time compounds
across the chain.

Remediation:
- Apply the Circuit Breaker pattern to stop propagating failures downstream.
- Set explicit timeouts on all inter-service calls.
- Use bulkheads to isolate failure domains.
- Prefer asynchronous messaging for non-time-critical operations.

### Event-Driven Architecture

Services communicate through domain events on a message bus. Producers publish
events without knowledge of consumers. Consumers process events independently.

Benefits: temporal decoupling, independent scalability, natural audit trail.
Risks: eventual consistency, complex debugging, event schema evolution.

Remediation for tight coupling: introduce an event bus (Kafka, RabbitMQ, SQS).
Define stable event contracts. Use event versioning strategies.

## Data Management

### Shared Database Anti-Pattern

Multiple services sharing a single database schema creates invisible coupling.
Schema changes require coordinating all consuming services simultaneously.

Remediation: Migrate to database-per-service. Use the Strangler Fig pattern to
incrementally extract service databases. Implement the CQRS pattern where read
and write models diverge across service boundaries.

### Saga Pattern for Distributed Transactions

Replace distributed transactions with a sequence of local transactions coordinated
by either choreography (event-driven) or orchestration (explicit saga coordinator).

Choreography saga: each service publishes events that trigger the next step.
Orchestration saga: a dedicated orchestrator calls each service in sequence.

## Observability

Microservices require distributed tracing to debug cross-service flows.
Instrument all services with a correlation ID propagated through all requests.
Centralise logs and metrics. Implement health check endpoints per service.

Minimum required: structured logging, correlation IDs, service health endpoints.
Recommended: distributed tracing (OpenTelemetry), circuit breaker dashboards.
