"""FastAPI application exposing retrieval pipeline responses."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from functools import lru_cache
import json
import logging
import os
import time
from typing import Any, Dict, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .. import configure_logging
from ..ingestion.pipeline import Chunk
from ..logging_utils import log_event
from ..metrics import latency_summary, record_latency
from ..orchestrator import RetrievalPipeline, serialize_retrieval_output
from .patients import router as patients_router
from .sessions import router as sessions_router


class RetrieveRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Counselor question or patient prompt.")
    context: str | None = Field(
        default=None,
        description="Optional counselor context such as patient highlights or prior answer references.",
    )
    mode: Literal["preparation", "live"] = Field(
        default="live",
        description="Execution mode: 'preparation' allows longer processing (20-30s), 'live' requires <5s response.",
    )


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(title="Metabolic Counselor Backend", version="0.1.0")

    # Add CORS middleware to allow frontend requests
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    disable_ingestion = os.getenv("METABOLIC_DISABLE_INGESTION") is not None

    @lru_cache(maxsize=1)
    def get_pipeline() -> RetrievalPipeline:
        if disable_ingestion:
            fallback_chunk = Chunk(
                chunk_id="fallback:0000",
                document_id="fallback",
                section_path=["advice"],
                source_path="fallback.md",
                text="일반적인 생활습관 가이드를 참고하세요. 담당 의사와 상담을 권장합니다.",
                token_count=12,
            )
            return RetrievalPipeline(chunks=[fallback_chunk])
        try:
            return RetrievalPipeline()
        except FileNotFoundError:
            fallback_chunk = Chunk(
                chunk_id="fallback:0000",
                document_id="fallback",
                section_path=["advice"],
                source_path="fallback.md",
                text="일반적인 생활습관 가이드를 참고하세요. 담당 의사와 상담을 권장합니다.",
                token_count=12,
            )
            return RetrievalPipeline(chunks=[fallback_chunk])

    @app.get("/healthz", tags=["system"])
    def healthcheck() -> Dict[str, Any]:
        return {"status": "ok"}

    @app.post("/v1/retrieve", tags=["retrieval"])
    def retrieve(payload: RetrieveRequest) -> Dict[str, Any]:
        question = payload.question.strip()
        if not question:
            raise HTTPException(status_code=422, detail="Question cannot be blank.")

        mode = payload.mode
        pipeline = get_pipeline()
        start = time.perf_counter()
        output = pipeline.run(question, context=payload.context, mode=mode)
        total_duration = time.perf_counter() - start

        record_latency("analysis", output.timings.get("analysis", 0.0))
        record_latency("rewrite", output.timings.get("rewrite", 0.0))
        record_latency("retrieval_vector", output.timings.get("retrieval_vector", 0.0))
        record_latency("retrieval_graph", output.timings.get("retrieval_graph", 0.0))
        record_latency("retrieval", output.timings.get("retrieval", 0.0))
        record_latency("synthesis", output.timings.get("synthesis", 0.0))
        record_latency("total", total_duration)

        # Mode-specific SLA warnings
        if mode == "live":
            if output.timings.get("analysis", 0.0) > 2.0:
                logging.warning("Safety analysis exceeded 2s SLA: %.3f s", output.timings["analysis"])
            if total_duration > 5.0:
                logging.warning("Retrieval pipeline exceeded 5s live SLA: %.3f s", total_duration)
        elif mode == "preparation":
            if total_duration > 30.0:
                logging.warning("Preparation mode exceeded 30s SLA: %.3f s", total_duration)

        log_event(
            "latency_recorded",
            {
                "mode": mode,
                "question_length": len(question),
                "analysis_ms": output.timings.get("analysis", 0.0) * 1000,
                "safety_ms": output.timings.get("safety", 0.0) * 1000,
                "rewrite_ms": output.timings.get("rewrite", 0.0) * 1000,
                "retrieval_vector_ms": output.timings.get("retrieval_vector", 0.0) * 1000,
                "retrieval_graph_ms": output.timings.get("retrieval_graph", 0.0) * 1000,
                "retrieval_ms": output.timings.get("retrieval", 0.0) * 1000,
                "synthesis_ms": output.timings.get("synthesis", 0.0) * 1000,
                "total_ms": total_duration * 1000,
                "safety": output.analysis.safety.value,
            },
        )

        return serialize_retrieval_output(output)

    def make_json_serializable(obj: Any) -> Any:
        """Recursively convert dataclasses and enums to JSON-serializable types."""
        if obj is None:
            return None
        if isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, Enum):
            return obj.value
        if is_dataclass(obj):
            return {k: make_json_serializable(v) for k, v in asdict(obj).items()}
        if isinstance(obj, dict):
            return {k: make_json_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [make_json_serializable(item) for item in obj]
        if isinstance(obj, set):
            return [make_json_serializable(item) for item in obj]
        # Fallback for other objects - try to convert to dict or string
        if hasattr(obj, '__dict__'):
            return make_json_serializable(obj.__dict__)
        return str(obj)

    @app.post("/v1/retrieve/stream", tags=["retrieval"])
    def retrieve_stream(payload: RetrieveRequest):
        """Stream LangGraph node updates in real-time using Server-Sent Events."""
        question = payload.question.strip()
        if not question:
            raise HTTPException(status_code=422, detail="Question cannot be blank.")

        mode = payload.mode
        pipeline = get_pipeline()

        async def event_generator():
            """Generate SSE events from LangGraph stream."""
            try:
                start_total = time.perf_counter()

                # Stream each node update from LangGraph
                for chunk in pipeline.stream(question, context=payload.context, mode=mode):
                    # chunk format: {node_name: node_output}
                    for node_name, node_output in chunk.items():
                        # Make node_output JSON-serializable
                        serializable_output = make_json_serializable(node_output)

                        event_data = {
                            "type": "node_update",
                            "node": node_name,
                            "data": serializable_output
                        }
                        yield f"data: {json.dumps(event_data)}\n\n"

                # Send final completion event
                total_duration = time.perf_counter() - start_total
                completion_data = {
                    "type": "complete",
                    "total_duration": total_duration
                }
                yield f"data: {json.dumps(completion_data)}\n\n"

            except Exception as e:
                logging.exception("Stream error: %s", e)
                error_data = {
                    "type": "error",
                    "message": str(e)
                }
                yield f"data: {json.dumps(error_data)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    @app.get("/metrics/latency", tags=["metrics"])
    def latency_metrics() -> Dict[str, Any]:
        return {"latency": latency_summary()}

    # Include patient data endpoints
    app.include_router(patients_router)

    # Include session management endpoints
    app.include_router(sessions_router)

    return app


app = create_app()
