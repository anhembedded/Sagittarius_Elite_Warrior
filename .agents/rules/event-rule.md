---
name: Event Placement Rule
description: Internal signal/callback or event bus — decided by "who owns this truth", never by counting signals; and separating thread marshalling from coupling.
trigger: on_demand
---

# EVENT PLACEMENT — internal signal or event bus?

The question is **not** "signal or bus". The right question is: **who owns this
truth?**

> **A truth private to ONE screen/module** → internal signal/callback.
> **A truth of the SYSTEM, or one that ≥2 places need** → event bus plus
> exactly **one** normalising subscriber.

## 1. Two problems that keep getting conflated

| | Problem | Correct mechanism |
| :-: | :--- | :--- |
| **A** | Getting data from a background thread/context back to the main thread **safely** | The framework's queued-signal / marshalling mechanism — **working as designed** |
| **B** | **Who is allowed to know about whom**; one truth being handled repeatedly in several places | Bus + exactly one normalising subscriber, many places merely *displaying* |

The mechanism in (A) is **not** technical debt, not a workaround, and **not**
something to remove. A signal bridging worker → main thread is **correct**
code; don't "clean it up". Removing it pushes UI updates onto a background
thread — exactly the class of defect that mechanism exists to prevent.

## 2. Classification — ask exactly one question

*"If another module wanted to know about this, would that be absurd?"*

- **Absurd** → a private truth (`loading finished`, `my stream started`). Use an
  internal signal. Putting it on the bus is a **leak**: everything can now
  listen, the coupling surface balloons, and reading the code no longer tells
  you who depends on whom.
- **Reasonable** → a system truth (`health changed`, `background task died`,
  `sync progress`, `logs`). Put it on the bus, with **exactly one** listener
  normalising it and many places displaying it.

## 3. Promote when the second consumer actually appears — not before

- **Promoting late is cheap:** the worker already emits *something*; changing
  where it emits to is a local edit.
- **Putting everything on the bus up front is expensive and near-irreversible**
  — after that nobody dares delete a subscriber, because nobody knows who is
  still listening.

> **Real evidence:** counted across 3 modules — **48 signals, 46 of them with
> exactly one listener**. The single fan-out one was a genuine system truth.
> The code had already classified itself correctly; nobody had named the rule.
> A task once set the target "delete 48 bridge signals" by conflating (A) with
> (B); measured for real, **47 of 48 existed because of (A)** and roughly 1
> could go. **Never set a target by counting signals.** With the boundary wrong,
> the number only leads you to break correct code.
