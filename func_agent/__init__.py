"""Functional test agent domain.

Unifies concrete execution backends (AutoGLM and Midscene) under one
business-facing package.
"""

from func_agent.orchestrator import run_func_agent_dispatch

__all__ = ["run_func_agent_dispatch"]
