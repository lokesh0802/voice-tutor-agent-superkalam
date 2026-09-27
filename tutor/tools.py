"""Agent tools. Pipecat reads each function's signature + docstring to build the LLM tool schema."""
import asyncio
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from pipecat.frames.frames import EndTaskFrame, TTSSpeakFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.llm_service import FunctionCallParams, FunctionCallResultProperties

from tutor.rag import kb

DB = Path(__file__).resolve().parent.parent / "tutor_progress.db"


def _db():
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS progress (student TEXT, ts TEXT, topics TEXT, notes TEXT)")
    return con


def build_tools(student_id: str) -> list:
    """Tools are closures so they know which student (caller number) they're serving."""

    async def search_knowledge_base(params: FunctionCallParams, query: str, subject: str = "any"):
        """Search the NCERT Class 10 textbooks for facts, definitions, formulas and examples.

        Args:
            query: Short search query in English with the key concept, e.g. "photosynthesis chlorophyll role".
            subject: One of "science", "maths" or "any".
        """
        hits = await asyncio.to_thread(kb.search, query, subject)  # don't block the audio loop
        await params.result_callback(
            [{"source": f"NCERT {h['subject']} - {h['chapter']} (page {h['page']})", "text": h["text"]} for h in hits]
            or "No relevant NCERT content found."
        )

    async def generate_quiz_question(params: FunctionCallParams, topic: str, difficulty: str = "easy"):
        """Get NCERT material to build ONE quiz question for the student on a topic.

        Args:
            topic: The concept to quiz on, e.g. "photosynthesis".
            difficulty: One of "easy", "medium", "hard".
        """
        hits = await asyncio.to_thread(kb.search, f"{topic} important questions", None, 2)
        style = {"easy": "a one-word or yes/no recall question",
                 "medium": "a 'why' or 'what happens if' reasoning question",
                 "hard": "an application or numerical question"}.get(difficulty, "a recall question")
        await params.result_callback({
            "instruction": f"Ask exactly ONE {style} about '{topic}', grounded in this text. Do not reveal the answer.",
            "material": [h["text"] for h in hits],
        })

    async def save_learning_progress(params: FunctionCallParams, topics: list[str], notes: str = ""):
        """Save what the student learned in this session (call at wrap-up).

        Args:
            topics: Topics covered, e.g. ["photosynthesis", "chlorophyll"].
            notes: Short note on strengths/weak areas and quiz performance.
        """
        with _db() as con:
            con.execute("INSERT INTO progress VALUES (?,?,?,?)",
                        (student_id, datetime.now().isoformat(timespec="seconds"), json.dumps(topics), notes))
        await params.result_callback({"saved": True})

    async def get_learning_history(params: FunctionCallParams):
        """Get the topics this student studied in previous sessions, to personalise the greeting."""
        with _db() as con:
            rows = con.execute("SELECT ts, topics, notes FROM progress WHERE student=? ORDER BY ts DESC LIMIT 3",
                               (student_id,)).fetchall()
        await params.result_callback(
            [{"date": r[0], "topics": json.loads(r[1]), "notes": r[2]} for r in rows] or "New student, no history."
        )

    async def end_session(params: FunctionCallParams, goodbye_message: str):
        """Say goodbye and hang up. Use only after the wrap-up summary when the student is done.

        Args:
            goodbye_message: Short warm goodbye to speak, e.g. "All the best for your exam! Bye!"
        """
        await params.result_callback({"ended": True}, properties=FunctionCallResultProperties(run_llm=False))
        if params.llm:  # None in the text CLI
            await params.llm.push_frame(TTSSpeakFrame(goodbye_message))
            await params.llm.push_frame(EndTaskFrame(), FrameDirection.UPSTREAM)

    return [search_knowledge_base, generate_quiz_question, save_learning_progress, get_learning_history, end_session]
