# Current Functionality Contract Inventory

Use this checklist before simplifying a repository. Mark each surface as
current, absent, obsolete, unknown, or verified.

## Authority and forward-only filter

- Binding repository instructions
- Current product, architecture, API, schema, and operational documentation
- Current build, package, deployment, and configuration manifests
- Active supported callers, integrations, and deployment paths
- Tests, examples, and fixtures confirmed to match the current contract
- Deprecated or legacy paths explicitly classified as obsolete
- Fallbacks, aliases, adapters, dual paths, and old persisted shapes explicitly
  classified as obsolete
- No backward compatibility or downgrade requirement
- Any explicitly authorized one-off migration is bounded and removes its bridge

## Product and user functionality

- Current user-visible workflows
- Current input acceptance and validation
- Current output content and formatting
- Current error presentation
- Accessibility and localization
- Current documented behavior

## APIs and integrations

- Current exported functions, methods, types, and constants
- Current HTTP or RPC endpoints
- Status codes, headers, payload schemas, streaming, and pagination
- Authentication and authorization
- Current webhooks, callbacks, events, and queues
- Current SDK and plugin extension points
- Current version contract
- Rate limits, retries, idempotency, and timeout behavior

## CLI functionality

- Current commands
- Current flags, defaults, environment variables, and config precedence
- Stdout/stderr separation
- Exit codes
- Interactive prompts
- Machine-readable output
- Shell completion and help text

## Data and persistence

- Canonical database schemas and constraints
- Canonical serialization formats
- Canonical file formats and paths
- Current transaction boundaries
- Ordering, uniqueness, and consistency guarantees
- Data integrity, retention, privacy, and deletion behavior
- Historical migrations required to construct the canonical current schema
- Old-shape readers, writers, and transitional bridges classified as obsolete

## Runtime semantics

- Side-effect order
- Concurrency and synchronization
- Cancellation and cleanup
- Resource ownership
- Failure atomicity
- Retry behavior for current supported operations
- Determinism and randomness
- Clock and timezone behavior
- Performance and resource ceilings

## Operations

- Current logs and stable log fields
- Current metrics and labels
- Tracing
- Health and readiness checks
- Alerting hooks
- Current feature flags
- Deployment configuration
- Supported platforms and architectures

## Supply chain and build

- Current build targets
- Generated code
- Package metadata
- Lockfiles
- Reproducibility
- Licensing
- Supported dependency and platform versions
- CI/CD behavior

## Evidence sources

Record the evidence supporting each claimed current invariant:

- Binding repository instructions
- Current API specifications
- Current schemas and manifests
- Current documentation
- Active downstream callers and integrations
- Current production or deployment configuration
- Tests confirmed to exercise the current contract
- Focused characterization tests
- Differential or golden-output tests

Also record evidence that a path is obsolete:

- Explicit deprecation or removal instruction
- Replacement by the canonical current implementation
- Absence from current build and deployment manifests
- No active supported caller or integration
- Old schema, config, API, or version markers
- Tests, examples, or fixtures whose assertions conflict with the current
  canonical contract
