"""Application services — process orchestration layer.

Distinct from domain/: domain/ holds pure business rules and knowledge (LLM client
wrapper, borrowing capacity formula, budget gap thresholds, UserNeeds assembly).
services/ holds the process flow that sequences domain/ calls, conversation/ state
transitions, and repository/session-store reads and writes for one HTTP operation.
"""
