"""Stages module: the docx's 12-stage Maestro process as independent features.

Each stage is an independently runnable, re-runnable feature on a course — not a
locked sequential pipeline. A stage reads whatever upstream artifacts already
exist and proceeds, flagging gaps rather than blocking (see ``service.run_stage``).

Submodules are imported lazily by callers to avoid eager import cycles; keep this
package ``__init__`` free of heavy imports.
"""
