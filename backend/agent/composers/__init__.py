"""Composer layer — orchestrates multiple ToolResults into structured assessments.

Composers are stateless functions (or callables) that take one or more ToolResults
and produce a structured Pydantic DTO (e.g. TransportAssessment). They live in
dedicated sub-packages under this directory (e.g. agent/composers/transport/).

Not yet implemented — placeholder for Subtask 5.
"""
