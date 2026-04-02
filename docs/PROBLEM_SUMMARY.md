# Problem Summary

## The Challenge

Software architects face a persistent and costly problem: architectural documentation is almost always out of date. As codebases evolve through sprints, hotfixes, and refactors, the diagrams and decision records created months or years ago drift further from reality. Manually auditing a codebase to reconcile what the code actually does with what the documentation says it does is tedious, error-prone, and rarely prioritized.

This gap creates real consequences:

- New team members onboard slowly because the "source of truth" documentation doesn't match the running system.
- Architectural reviews rely on tribal knowledge instead of verifiable artifacts.
- Enterprise architecture tools like LeanIX contain stale mappings that undermine portfolio-level decisions.
- Circular dependencies, undocumented service interactions, and orphaned components go unnoticed until they cause incidents.

## What This Tool Does

The Architectural Reverse Engineer solves this by automating the analysis. You point it at a codebase (local folder or GitHub URL) and optionally feed it existing documentation (PDFs, Word files, architecture diagrams), and it produces a comprehensive, up-to-date set of architectural artifacts:

- Dependency graphs with circular dependency detection
- Component diagrams labeled with LeanIX object types
- UML class and sequence diagrams
- Lower-level design diagrams showing internal component structure
- Architectural Decision Records (ADRs) derived from detected patterns
- LeanIX mapping reports for enterprise architecture integration
- A complete Markdown documentation package with table of contents, embedded diagrams, and interface catalogs

The tool uses GPT-4 to understand code structure and reconcile it against existing documentation, flagging discrepancies between what the code does and what the docs say.

## Who It's For

- Software architects maintaining documentation for evolving systems
- Engineering leads preparing for architectural reviews or audits
- Enterprise architecture teams keeping LeanIX or similar tools current
- Teams onboarding new members who need accurate system overviews

## Key Differentiators

- Combines code analysis with existing document analysis, reconciling the two
- Produces multiple output formats (images, JSON, Markdown, PlantUML) for different audiences
- Maps discovered elements to LeanIX object types with confidence scores
- Detects and highlights circular dependencies automatically
- Generates ADRs only for decisions not already documented (deduplication)
- All structured outputs are JSON Schema-validated with round-trip serialization guarantees
