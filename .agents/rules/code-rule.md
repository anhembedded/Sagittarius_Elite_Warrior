---
trigger: always_on
---

# Development Guidelines

- **No Hardcoding**: Avoid magic strings, magic numbers, or hardcoded configurations. Always refer to existing related implementations, established enums, or central configuration files (`config_keys.py`, `user_config.json`, etc.).
- **Strictly Follow SOLID Principles**: Ensure any new features, refactors, or code additions adhere strictly to SOLID principles:
  - **S**ingle Responsibility Principle (SRP)
  - **O**pen/Closed Principle (OCP)
  - **L**iskov Substitution Principle (LSP)
  - **I**nterface Segregation Principle (ISP)
  - **D**ependency Inversion Principle (DIP)
- **No Lazy Code**: Don't take the shortcut that's easiest to type over the one that's easiest to read/maintain.
  - Split by responsibility into separate files/modules instead of piling unrelated logic into one file or one function.
  - Model data with proper structures — dataclasses, value objects, `Enum` — instead of loose primitives, dicts, or magic strings/tuples standing in for a real type.
  - Do not use `lambda`. Write a named function/method instead — it gets a real name, can carry a docstring, and shows up properly in stack traces/coverage/debuggers.
