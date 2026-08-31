---
name: Design Intent Rule
description: Deferred work and accepted trade-offs must exist in the code as a type or a test — never in documentation alone; and a class is a contract, not a lump of implementation.
trigger: always_on
---

# CODE MUST SPEAK FOR ITSELF

> **If something is to be built later, or is a price you have deliberately
> accepted, the code must contain an interface / type / test standing for it.
> It may not live only in documentation.**

The reason: documentation is something an agent must **go looking for**; a type
is something that **hits them in the face while reading the code**. A decision
recorded only in `.agents/` or in a task file will be violated next time — not
out of carelessness, but because the code gave no hint at all.

> **Real evidence:** a task set the target "delete 48 bridge signals"
> ([`event-rule.md`](event-rule.md) §3). Whoever wrote it **had all the rules
> available**. They still got it wrong, because the place those signals were
> declared **said nothing** about being thread bridges or about what breaks if
> they go. A correct rule with mute code is a useless rule.

## 1. Two shapes, two ways of expressing them

| Shape | What the code must contain |
| :--- | :--- |
| **To be built later** (a known extension point) | A **type/interface/base class** acting as the landing site, with a docstring stating the extension recipe. The next agent can `grep` for it and imitate it |
| **A price deliberately accepted** (an intentional trade-off) | A **test locking the current behaviour**, plus a docstring stating what was lost, why it was accepted, and under what conditions it would be restored. Not merely a note |

> **Real evidence (trade-off):** a change had to drop immutability on several
> types in order to inherit a shared base class. The correct handling: **don't
> delete the immutability test — turn it into a test locking the new
> behaviour**, with the reason and the restoration condition. The loss lives in
> the test suite, not in a note everyone scrolls past.

## 2. Always favour abstraction — a class is a **contract**

When writing a class, **evaluate its extensibility and its API first**, then
write the body. The default is **to have an abstraction**: a class must be a
**contract** with other classes, not a block of implementation whose innards
callers must know to use it.

When adding a new class, ask in this order:

1. **Who will call it, and what do they need to see?** That is the API — design
   it first, don't extract it after the body is written.
2. **Where is extension likely?** (swapping a backend, a data source, adding a
   variant). That point must be an interface, so the next person can replace it
   without editing consumers.
3. **Must the consumer know internal details?** If so the contract is
   insufficient — tighten it.

Abstraction here does **not** mean "add an intermediate layer for its own sake".
It means: **a class's public surface must be something other people can program
against**.

> **The counter-lesson, still valid:** 4 stub classes were once generated from
> speculation, with 0 real instances. They were wrong **not** for lacking
> abstraction, but for **guessing the shape** of something that did not yet
> exist. Favouring abstraction means **designing the API of what you are
> writing**, not guessing at what nobody needs yet.

## 3. No escaping via docstrings

Docstrings and comments are **additive**, not a substitute. A comment explains
*why*; a type and a test are what **force** the next person down the right path,
and what **breaks** when reality changes. A decision that lives only in prose
has nothing to detect it when it stops being true.
