"""SuperKalam Voice Tutor — Pipecat pipeline.

  Browser demo :  python bot.py                                  -> open http://localhost:7860
  Phone (Twilio):  python bot.py -t twilio -x <your-ngrok-host>    -> point Twilio number webhook to https://<host>/

Pipeline:  mic/phone -> Silero VAD -> Sarvam STT (codemix) -> GPT (tools + RAG) -> Sarvam TTS (bulbul:v3) -> speaker
Barge-in, turn-taking and audio resampling (8 kHz Twilio <-> 16/24 kHz) are handled by Pipecat.
"""
import json
import os
import random
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import LLMRunFrame, TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair, LLMUserAggregatorParams
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.sarvam.stt import SarvamSTTService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.transcriptions.language import Language
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams
from pipecat.workers.runner import WorkerRunner

from tutor.prompts import GREETING_INSTRUCTION, SYSTEM_PROMPT
from tutor.rag import kb
from tutor.tools import build_tools

load_dotenv(override=True)
kb.load()  # load Chroma + build BM25 once at startup (not on the first call)

SESSIONS = Path(__file__).parent / "sessions"
FILLERS = ["एक second, मैं book में देखती हूँ।", "Hmm, चलो NCERT में check करते हैं।", "अच्छा सवाल है, एक second।"]

transport_params = {
    "webrtc": lambda: TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    "twilio": lambda: FastAPIWebsocketParams(audio_in_enabled=True, audio_out_enabled=True),
}


async def bot(runner_args: RunnerArguments):
    transport = await create_transport(runner_args, transport_params)
    call = runner_args.call_data
    student_id = (call.from_number if call else None) or "web-demo"
    logger.info(f"New session for {student_id}")

    stt = SarvamSTTService(api_key=os.environ["SARVAM_API_KEY"], mode="codemix")  # Hinglish -> mixed script text
    tts = SarvamTTSService(
        api_key=os.environ["SARVAM_API_KEY"],
        settings=SarvamTTSService.Settings(
            model="bulbul:v3", voice=os.getenv("SARVAM_VOICE", "priya"), language=Language.HI_IN,
            pace=float(os.getenv("SARVAM_PACE", "1.0")),
        ),
    )
    llm = OpenAILLMService(
        api_key=os.environ["OPENAI_API_KEY"],
        settings=OpenAILLMService.Settings(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"), system_instruction=SYSTEM_PROMPT, temperature=0.5
        ),
    )

    # Hide RAG latency: speak a short filler while the knowledge-base search runs.
    @llm.event_handler("on_function_calls_started")
    async def on_function_calls_started(service, function_calls):
        if any(fc.function_name in ("search_knowledge_base", "generate_quiz_question") for fc in function_calls):
            await tts.queue_frame(TTSSpeakFrame(random.choice(FILLERS)))

    context = LLMContext(tools=build_tools(student_id))
    user_agg, assistant_agg = LLMContextAggregatorPair(
        context,
        # stop_secs: how long a pause means "student finished speaking" (lower = snappier, higher = fewer cut-offs)
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.4))),
    )

    pipeline = Pipeline([transport.input(), stt, user_agg, llm, tts, transport.output(), assistant_agg])
    worker = PipelineWorker(pipeline, params=PipelineParams(enable_metrics=True, enable_usage_metrics=True))
    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    await runner.add_workers(worker)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        context.add_message({"role": "developer", "content": GREETING_INSTRUCTION})
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        # Session analytics: full transcript incl. tool calls -> sessions/*.json
        path = SESSIONS / f"{datetime.now():%Y%m%d_%H%M%S}_{student_id.strip('+')}.json"
        path.write_text(json.dumps(context.get_messages(), ensure_ascii=False, indent=2, default=str))
        logger.info(f"Transcript saved -> {path}")
        await runner.cancel()

    await runner.run()


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
