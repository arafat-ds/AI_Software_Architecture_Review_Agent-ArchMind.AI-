# Layered Architecture Patterns and Anti-Patterns

## Overview

Layered architecture organises code into horizontal layers — each layer communicates
only with the layer directly below it. Strict layer boundaries enforce separation of
concerns, reduce coupling, and make individual layers testable in isolation.

Canonical layers: Presentation → Application/Service → Domain/Business Logic → Data/Infrastructure.

## Strengths

- Clear separation of concerns reduces cognitive load per layer.
- Individual layers can be tested and replaced independently.
- New developers can reason about one layer without understanding the full stack.
- Well-understood pattern with broad tooling support.

## Common Anti-Patterns and Weaknesses

### Skip-Layer Calls

Presentation code importing directly from the data/infrastructure layer bypasses
the domain and service layers. This creates tight coupling between UI concerns and
persistence concerns, making both layers harder to test and evolve independently.

Remediation: Route all cross-layer calls through the intermediate service layer.
Introduce service interfaces that the presentation layer depends on. Use dependency
injection to decouple layer implementations from their consumers.

### Anemic Domain Model

Business logic scattered across service and presentation layers instead of being
encapsulated in domain objects. Services become transaction scripts with no domain
behaviour. Domain objects become passive data containers (getters and setters only).

Remediation: Move behaviour to domain objects. Services should orchestrate domain
object interactions, not implement business rules directly. Apply Domain-Driven
Design tactical patterns: aggregates, value objects, domain services.

### God Service

A single service class that coordinates multiple unrelated domain concepts. God
services grow unbounded in line count and method count, accumulating responsibilities
from multiple domains. They become a maintenance bottleneck and create merge conflicts.

Remediation: Decompose by single responsibility. One service class per domain aggregate
or bounded context. Extract cross-cutting concerns (logging, validation) to decorators
or middleware rather than embedding them in service methods.

## Coupling Remediation

### High Fan-Out Files

Files that import many modules create fragile coupling webs. A change to any imported
module potentially breaks the importing file. High fan-out is a signal of missing
abstraction.

Remediation: Introduce a facade or service boundary. Group related imports behind a
single interface. Apply the interface segregation principle — depend on narrow interfaces
that match your usage pattern.

### High Fan-In Files

Files imported by many other modules become change-blocking hub files. Every change
requires broad regression testing across all consumers.

Remediation: Stabilise the hub file's public interface. Introduce a versioned interface
contract. Consider splitting the hub into multiple focused modules with stable interfaces.

### Circular Dependencies

Module A imports from B and B imports from A. Circular imports indicate a design
boundary violation. The two modules have entangled responsibilities.

Remediation: Extract the shared concern to a third module that both A and B depend on.
Apply the Dependency Inversion Principle — both modules depend on an abstraction rather
than on each other's concretions.

## Test Coverage for Layered Architecture

Each layer should have independent unit tests that mock the layer below.
Integration tests should verify cross-layer contracts.

Minimum test file presence ratio: 0.30 (one test file per three source files).
Test files co-located with the modules they test or in a parallel tests/ directory.
