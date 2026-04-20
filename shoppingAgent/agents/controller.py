"""
ShoppingAgentController — thin wrapper that delegates to ReActAgent.

The old fixed pipeline is kept as _run_pipeline() for CLI / fallback use.
"""

from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional

from agents.react_agent import ReActAgent

StepCallback = Callable[[str, str, Any], None]


def _noop(*_):
    pass


class ShoppingAgentController:
    """
    Public interface unchanged so existing callers (main.py, agent_graph.py)
    keep working without modification.
    """

    def __init__(self) -> None:
        self._agent = ReActAgent()

    def run(
        self,
        query: str,
        memory_context: str = "",
        callback: StepCallback = _noop,
        max_results: int = 15,
        enable_reflection: bool = True,
        filters: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        return self._agent.run(
            query          = query,
            memory_context = memory_context,
            callback       = callback,
            max_iterations = 10,
            filters        = filters or {},
        )
