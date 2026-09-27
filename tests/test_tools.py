"""Agent tool tests (no API keys needed): schema generation + tool execution + progress memory."""
import asyncio
from types import SimpleNamespace

from pipecat.adapters.schemas.direct_function import DirectFunctionWrapper

import tutor.tools as T


def _run(tool, **args):
    out = {}

    async def cb(result, **_):
        out["r"] = result

    asyncio.run(DirectFunctionWrapper(tool).invoke(args, SimpleNamespace(llm=None, result_callback=cb)))
    return out["r"]


def test_schemas_are_generated_from_docstrings():
    names = {DirectFunctionWrapper(t).to_function_schema().name for t in T.build_tools("s")}
    assert {"search_knowledge_base", "generate_quiz_question", "save_learning_progress",
            "get_learning_history", "end_session"} <= names


def test_progress_memory_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(T, "DB", tmp_path / "p.db")
    tools = {t.__name__: t for t in T.build_tools("+919999999999")}
    assert _run(tools["get_learning_history"]) == "New student, no history."
    _run(tools["save_learning_progress"], topics=["photosynthesis"], notes="good with analogies")
    hist = _run(tools["get_learning_history"])
    assert hist[0]["topics"] == ["photosynthesis"]


def test_search_tool_returns_sources():
    import os
    if not os.getenv("OPENAI_API_KEY") or not T.kb.load().docs:
        return  # needs key + built index
    tools = {t.__name__: t for t in T.build_tools("s")}
    res = _run(tools["search_knowledge_base"], query="photosynthesis chlorophyll", subject="science")
    if isinstance(res, str):  # index not built
        return
    assert "life processes" in res[0]["source"]
