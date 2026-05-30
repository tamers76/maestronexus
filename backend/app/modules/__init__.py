"""Bounded-context modules (per docs/11_system_architecture.md).

Each module is a self-contained package exposing a public ``router`` and, later,
a service interface. Cross-module access must go through service interfaces, never
by importing another module's models or tables directly.
"""
