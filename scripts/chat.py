"""Text-mode tutor (same prompt + same tools, no voice) — fast way to test the agent logic.

    python scripts/chat.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402
from pipecat.adapters.schemas.direct_function import DirectFunctionWrapper  # noqa: E402

from tutor.prompts import GREETING_INSTRUCTION, SYSTEM_PROMPT  # noqa: E402
from tutor.tools import build_tools  # noqa: E402

load_dotenv(override=True)


async def main():
    client = AsyncOpenAI()
    tools = {w.name: w for w in map(DirectFunctionWrapper, build_tools("cli-student"))}
    schemas = [{"type": "function", "function": w.to_function_schema().to_default_dict()} for w in tools.values()]
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "developer", "content": GREETING_INSTRUCTION}]

    while True:
        r = await client.chat.completions.create(model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                                                 messages=msgs, tools=schemas)
        m = r.choices[0].message
        msgs.append(m.model_dump(exclude_none=True))
        if m.tool_calls:  # run tools, feed results back, loop
            for tc in m.tool_calls:
                out = {}
                params = SimpleNamespace(llm=None, result_callback=_cb(out))
                args = json.loads(tc.function.arguments or "{}")
                print(f"  🔧 {tc.function.name}({args})")
                await tools[tc.function.name].invoke(args, params)
                msgs.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(out.get("r"), ensure_ascii=False)})
                if tc.function.name == "end_session":
                    print(f"\nTUTOR: {args.get('goodbye_message')}")
                    return
            continue
        print(f"\nTUTOR: {m.content}")
        msgs.append({"role": "user", "content": input("\nYOU: ")})


def _cb(out):
    async def cb(result, **_):
        out["r"] = result
    return cb


if __name__ == "__main__":
    asyncio.run(main())
