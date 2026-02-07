# AI Memory Bank Model (Super Brief)

## What it is
A **memory bank** is a small curated set of repo docs that acts as the AI’s **authoritative mental model** of the system.

Instead of the model inferring architecture by scanning thousands of files, you provide a compressed “map” of:
- domain vocabulary and invariants
- module boundaries and responsibilities
- key workflows and data flows
- integration points
- conventions and patterns
- known footguns

Think: **what a senior engineer knows after 6 months**, written down.

---

## Why it is useful
Without a memory bank, the model tends to:
- waste tokens rediscovering structure
- edit the wrong layer
- duplicate existing abstractions
- break conventions
- misread domain concepts

With a memory bank, the model:
- routes tasks to the correct code areas fast
- reasons consistently about the domain
- produces changes aligned with existing architecture
- reduces “clever but wrong” refactors

It upgrades AI from **autocomplete** to **engineer who understands the system**.

---

## Minimal setup (5 files)
Create a `/memory/` folder with:

### 1. `architecture.md`
Major subsystems, boundaries, ownership, data flows.

### 2. `domain.md`
Core entities, invariants, vocabulary, lifecycle rules.

### 3. `code-map.md`
Routing table:  
“If you need X, go to Y.”

### 4. `conventions.md`
Patterns, preferred libraries, style rules, test practices.

### 5. `gotchas.md`
Known landmines, legacy constraints, “do not touch” zones.

---

## How to use it
Before asking the model to implement anything:
- always include these memory files in context
- treat them as the source of truth
- update them whenever the AI gets confused

Keep it short, opinionated, and current.

========
