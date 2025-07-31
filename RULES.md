AI Instance Governance Rules
These RULES must be followed at all times.
<!-- this is from https://www.reddit.com/r/ClaudeAI/comments/1km9hhp/latest_rules_for_claude_code/ -->

This document defines mandatory operating principles for all AI instances. It ensures consistent behaviour, robust execution, and secure collaboration across tasks and services.

## Code Quality Standards
1. All scripts must implement structured error handling with specific failure modes.
1. Every function must include a concise, purpose-driven docstring.
1. Scripts must verify preconditions before executing critical or irreversible operations.
1. Long-running operations must implement timeout and cancellation mechanisms.
1. File and path operations must verify existence and permissions before granting access.

## Documentation Protocols
1. Documentation must be synchronised with code changes—no outdated references.
1. Markdown files must use consistent heading hierarchies and section formats.
1. Code snippets in documentation must be executable, tested, and reflect real use cases.
1. Example commands must be real and tested.
1. Each doc must clearly outline: purpose, usage, parameters, and examples.
1. Technical terms must be explained inline or linked to a canonical definition.
2. Dates used in file names, directories, or timestamps in changelogs, project history, etc, *must be todays actual date*.

## Task Management Rules
1. Tasks must be clear, specific, and actionable—avoid ambiguity.
1. Every task must be assigned a responsible agent, explicitly tagged.
1. Complex tasks must be broken into atomic, trackable subtasks.
1. No task may conflict with or bypass existing validated system behaviour.
1. Security-related tasks must undergo mandatory review by a designated reviewer agent.
1. Agents must update task status and outcomes in the shared task file.
1. Dependencies between tasks must be explicitly declared.
1. Agents must escalate ambiguous, contradictory, or unscoped tasks for clarification.

## Security Compliance Guidelines
1. Hardcoded credentials are strictly forbidden—use secure storage mechanisms.
1. All inputs must be validated, sanitised, and type-checked before processing.
1. Avoid using eval, unsanitised shell calls, or any form of command injection vectors.
1. File and process operations must follow the principle of least privilege.
1. All sensitive operations must be logged, excluding sensitive data values.
1. Agents must check system-level permissions before accessing protected services or paths.

## Process Execution Requirements
1. Agents must log all actions with appropriate severity (INFO, WARNING, ERROR, etc.).
1. Any failed task must include a clear, human-readable error report.
1. Agents must respect system resource limits, especially memory and CPU usage.
1. Long-running tasks must expose progress indicators or checkpoints.
1. Retry logic must include exponential backoff and failure limits.

## Core Operational Principles
1. Agents must never use mock, fallback, or synthetic data in production tasks.
1. Error handling logic must be designed using test-first principles.
1. Agents must always act based on verifiable evidence, not assumptions.
1. All preconditions must be explicitly validated before any destructive or high-impact operation.
1. All decisions must be traceable to logs, data, or configuration files.

## Design Philosophy Principles

### KISS (Keep It Simple, Stupid)
* Solutions must be straightforward and easy to understand.
* Avoid over-engineering or unnecessary abstraction.
* Prioritise code readability and maintainability.

### YAGNI (You Aren’t Gonna Need It)
* Do not add speculative features or future-proofing unless explicitly required.
* Focus only on immediate requirements and deliverables.
* Minimise code bloat and long-term technical debt.

### SOLID Principles
1. Single Responsibility Principle — each module or function should do one thing only.
1. Open-Closed Principle — software entities should be open for extension but closed for modification.
1. Liskov Substitution Principle — derived classes must be substitutable for their base types.
1. Interface Segregation Principle — prefer many specific interfaces over one general-purpose interface.
1. Dependency Inversion Principle — depend on abstractions, not concrete implementations.

## System Extension Guidelines
1. All new agents must conform to existing interface, logging, and task structures.
1. Utility functions must be unit tested and peer reviewed before shared use.
1. All configuration changes must be reflected in the system manifest with version stamps.
1. New features must maintain backward compatibility unless justified and documented.
1. All changes must include a performance impact assessment.

## Quality Assurance Procedures
1. A reviewer agent must review all changes involving security, system config, or agent roles.
1. Documentation must be proofread for clarity, consistency, and technical correctness.
1. User-facing output (logs, messages, errors) must be clear, non-technical, and actionable.
1. All error messages should suggest remediation paths or diagnostic steps.
1. All major updates must include a rollback plan or safe revert mechanism.

## Testing & Simulation Rules
1. All new logic must include unit and integration tests.
1. Simulated or test data must be clearly marked and never promoted to production.
1. All tests must pass in continuous integration pipelines before deployment.
1. Code coverage should exceed defined thresholds (e.g. 85%).
1. Regression tests must be defined and executed for all high-impact updates.
1. Agents must log test outcomes in separate test logs, not production logs.

## Change Tracking & Governance
1. All configuration or rule changes must be documented in the system manifest and changelog.
1. Agents must record the source, timestamp, and rationale when modifying shared assets.
1. All updates must increment the internal system version where applicable.
1. A rollback or undo plan must be defined for every major change.
1. Audit trails must be preserved for all task-modifying operations.
