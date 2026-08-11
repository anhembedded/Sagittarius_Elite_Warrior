# Development Guidelines

- **No Hardcoding**: Avoid magic strings, magic numbers, or hardcoded configurations. Always refer to existing related implementations, established enums, or central configuration files (`config_keys.py`, `user_config.json`, etc.).
- **Strictly Follow SOLID Principles**: Ensure any new features, refactors, or code additions adhere strictly to SOLID principles:
  - **S**ingle Responsibility Principle (SRP)
  - **O**pen/Closed Principle (OCP)
  - **L**iskov Substitution Principle (LSP)
  - **I**nterface Segregation Principle (ISP)
  - **D**ependency Inversion Principle (DIP)
