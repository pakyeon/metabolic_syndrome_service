"""LangGraph-based retrieval pipeline for counselor prompts."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, List, Sequence

from langgraph.graph import END, StateGraph

from ..analysis import QuestionAnalyzer, QuestionAnalysisResult, SafetyLevel
from ..cache import FAQCache
from ..ingestion import Chunk, IngestionPipeline, iter_chunks
from ..ingestion.embedding import EmbeddingConfig, EmbeddingProvider, resolve_embedding_config
from ..providers import get_main_llm, get_small_llm
from langchain_core.messages import HumanMessage
from .guardrails import (
    SafetyEnvelope,
    append_caution_guidance,
    build_safety_envelope,
    scrub_observations,
    scrub_text,
)
from ..retrievers import GraphRetriever, VectorRetriever

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class PatientStateAnalysis:
    """Step 1: Patient state analysis."""

    summary: str  # "55세 남성, BMI 28.5(과체중)..."
    key_metrics: Dict[str, str]  # {"BMI": "28.5", "혈압": "140/90"...}
    concerns: List[str]  # ["혈압 경계", "체중 관리 필요"]


@dataclass(slots=True)
class ConsultationPattern:
    """Step 2: Previous consultation pattern."""

    previous_topics: List[str]  # ["걷기 운동", "식단 조절"]
    adherence_notes: List[str]  # ["운동 실천율 50%"]
    difficulties: List[str]  # ["시간 부족으로 운동 어려움"]


@dataclass(slots=True)
class ExpectedQuestion:
    """Step 3: Expected question with recommended answer."""

    question: str
    recommended_answer: str
    evidence_chunks: List[Chunk]
    citations: List[str]


@dataclass(slots=True)
class DeliveryExample:
    """Step 5: Delivery method example."""

    topic: str
    technical_version: str  # Medical terminology
    patient_friendly_version: str  # Simple language
    framing_notes: str  # "긍정적으로 프레이밍"


@dataclass(slots=True)
class PreparationAnalysis:
    """Complete 5-step preparation analysis."""

    patient_state: PatientStateAnalysis
    consultation_pattern: ConsultationPattern | None  # May not exist
    expected_questions: List[ExpectedQuestion]
    delivery_examples: List[DeliveryExample]
    warnings: List[str]  # Medical judgment warnings
    timings: Dict[str, float]


@dataclass(slots=True)
class RetrievalOutput:
    """Aggregated pipeline output for counselor consumption."""

    analysis: QuestionAnalysisResult
    answer: str
    citations: List[str]
    observations: List[str]
    safety: SafetyEnvelope
    timings: Dict[str, float]
    evidence: List[Chunk] = field(default_factory=list)
    preparation_analysis: PreparationAnalysis | None = None


class RetrievalPipeline:
    """Executes safety gating, LangGraph retrieval, and answer synthesis."""

    def __init__(
        self,
        analyzer: QuestionAnalyzer | None = None,
        chunks: Sequence[Chunk] | None = None,
    ) -> None:
        self.analyzer = analyzer or QuestionAnalyzer()
        try:
            self.embedding_provider = EmbeddingProvider(resolve_embedding_config())
        except RuntimeError as exc:
            LOGGER.warning(
                "Embedding provider initialization failed (%s); using offline fallback.", exc
            )
            offline_config = EmbeddingConfig(
                model_name=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
                backend="offline",
                embedding_size=int(os.getenv("EMBEDDING_DIM", "384")),
            )
            self.embedding_provider = EmbeddingProvider(offline_config)
        self.small_llm = get_small_llm()
        self.main_llm = get_main_llm()
        self.default_vector_top_k = int(os.getenv("VECTOR_TOP_K", "3"))
        self.graph_top_k = int(os.getenv("GRAPH_TOP_K", "5"))
        self.max_evidence = int(os.getenv("EVIDENCE_LIMIT", "5"))

        # Initialize FAQ cache
        cache_dir = Path(os.getenv("CACHE_DIR", ".cache/backend"))
        cache_file = cache_dir / "faq_cache.json"
        self.faq_cache = FAQCache(cache_file)

        # Populate with default FAQs if cache is empty
        if self.faq_cache.size() == 0:
            self.faq_cache.populate_defaults()
            LOGGER.info("Initialized FAQ cache with default entries")

        self._chunks = list(chunks) if chunks is not None else list(iter_chunks())
        disable_ingestion = os.getenv("DISABLE_INGESTION") is not None
        if not self._chunks and not disable_ingestion:
            LOGGER.info("Chunk cache empty; running ingestion pipeline on-demand")
            try:
                IngestionPipeline().run()
            except FileNotFoundError:
                LOGGER.warning(
                    "No documents available for ingestion. Retrieval will return fallback evidence."
                )
            self._chunks = list(iter_chunks())

        if not self._chunks:
            LOGGER.info("Using fallback chunk set")
            self._chunks = [
                Chunk(
                    chunk_id="fallback:0000",
                    document_id="fallback",
                    section_path=["advice"],
                    source_path="fallback.md",
                    text="일반적인 생활습관 가이드를 참고하세요. 담당 의사와 상담을 권장합니다.",
                    token_count=12,
                    metadata={"document_id": "fallback"},
                )
            ]

        vector_db_url = None
        if os.getenv("USE_VECTOR_DB") is not None and os.getenv("DISABLE_VECTOR_DB") is None:
            vector_db_url = os.getenv("DATABASE_URL")

        graph_url = None
        if os.getenv("USE_GRAPH_DB") is not None and os.getenv("DISABLE_GRAPH_DB") is None:
            graph_url = os.getenv("NEO4J_URL") or os.getenv("NEO4J_URI")

        self.vector_retriever = VectorRetriever(
            chunks=self._chunks,
            embedding_provider=self.embedding_provider,
            table_name=os.getenv("VECTOR_TABLE", "document_chunks"),
            database_url=vector_db_url,
        )
        self.graph_retriever = GraphRetriever(
            chunks=self._chunks,
            uri=graph_url,
            user=os.getenv("NEO4J_USER"),
            password=os.getenv("NEO4J_PASSWORD"),
        )

        self._graph = self._build_graph()

    # ------------------------------------------------------------------
    def _build_graph(self):
        graph = StateGraph(dict)
        # Existing live mode nodes
        graph.add_node("analysis", self._node_analyze)
        graph.add_node("safety", self._node_safety)
        graph.add_node("rewrite", self._node_rewrite)
        graph.add_node("decompose", self._node_decompose)
        graph.add_node("vector", self._node_vector_retrieval)
        graph.add_node("graph", self._node_graph_retrieval)
        graph.add_node("merge", self._node_merge_evidence)
        graph.add_node("synthesize", self._node_synthesize)

        # NEW: Preparation mode nodes
        graph.add_node("prep_analyze_patient", self._node_prep_analyze_patient)
        graph.add_node("prep_analyze_history", self._node_prep_analyze_history)
        graph.add_node("prep_generate_questions", self._node_prep_generate_questions)
        graph.add_node("prep_prepare_answers", self._node_prep_prepare_answers)
        graph.add_node("prep_delivery_examples", self._node_prep_delivery_examples)
        graph.add_node("prep_synthesize", self._node_prep_synthesize)

        graph.set_entry_point("analysis")
        graph.add_edge("analysis", "safety")

        # NEW: Mode-based routing after safety
        graph.add_conditional_edges(
            "safety",
            self._route_after_safety,
            {
                "escalate": END,
                "proceed_live": "rewrite",
                "proceed_prep": "prep_analyze_patient",
            },
        )

        # Existing live mode edges
        graph.add_conditional_edges(
            "rewrite",
            self._route_post_rewrite,
            {"vector": "vector", "decompose": "decompose", "graph": "graph"},
        )
        graph.add_conditional_edges(
            "vector",
            self._route_post_vector,
            {"graph": "graph", "merge": "merge"},
        )
        graph.add_edge("graph", "merge")
        graph.add_edge("merge", "synthesize")
        graph.add_edge("decompose", "synthesize")

        # NEW: Preparation mode flow
        graph.add_edge("prep_analyze_patient", "prep_analyze_history")
        graph.add_edge("prep_analyze_history", "prep_generate_questions")
        graph.add_edge("prep_generate_questions", "prep_prepare_answers")
        graph.add_edge("prep_prepare_answers", "prep_delivery_examples")
        graph.add_edge("prep_delivery_examples", "prep_synthesize")
        graph.add_edge("prep_synthesize", END)

        return graph.compile()

    # ------------------------------------------------------------------
    def run(
        self, question: str, *, context: str | None = None, mode: str = "live"
    ) -> RetrievalOutput:
        start_total = time.perf_counter()

        # Check FAQ cache for live mode (skip for preparation mode)
        if mode == "live":
            cached_answer = self.faq_cache.get(question, similarity_threshold=0.85)
            if cached_answer:
                cache_duration = time.perf_counter() - start_total
                LOGGER.info(
                    f"FAQ cache hit for: {question[:50]}... (took {cache_duration*1000:.1f}ms)"
                )

                # Return cached result with minimal processing
                return RetrievalOutput(
                    analysis=QuestionAnalysisResult(
                        domain="metabolic",
                        complexity="simple",
                        strategy="cached",
                        safety=SafetyLevel.CLEAR,
                        reasoning="Cached FAQ response",
                    ),
                    answer=cached_answer,
                    citations=["FAQ Cache"],
                    observations=["FAQ cache hit - instant response"],
                    safety=SafetyEnvelope(
                        level=SafetyLevel.CLEAR, guidance="", scrubbed=cached_answer
                    ),
                    timings={"total": cache_duration, "cache_lookup": cache_duration},
                    evidence=[],
                )

        state = self._graph.invoke(
            {
                "question": question,
                "context": context,
                "mode": mode,
                "observations": [],
                "timings": {},
            }
        )

        entries = state.get("_timing_entries", [])
        timings = {stage: duration for stage, duration in entries}
        timings["total"] = time.perf_counter() - start_total
        if "retrieval" not in timings:
            timings["retrieval"] = timings.get("retrieval_vector", 0.0) + timings.get(
                "retrieval_graph", 0.0
            )

        analysis: QuestionAnalysisResult = state["analysis"]
        safety: SafetyEnvelope = state["safety"]

        # Mode-specific output handling
        if mode == "preparation":
            prep_analysis: PreparationAnalysis | None = state.get("preparation_analysis")
            return RetrievalOutput(
                analysis=analysis,
                answer="",  # No single answer in preparation mode
                citations=[],
                observations=scrub_observations(state.get("observations", [])),
                safety=safety,
                timings=timings,
                evidence=[],
                preparation_analysis=prep_analysis,
            )

        # Existing live mode logic
        evidence: List[Chunk] = list(state.get("evidence", []))
        answer = state.get("answer", "")
        citations = list(state.get("citations", []))

        if analysis.safety is SafetyLevel.CAUTION and safety.level is not SafetyLevel.ESCALATE:
            answer = append_caution_guidance(answer, safety)

        return RetrievalOutput(
            analysis=analysis,
            answer=scrub_text(answer),
            citations=citations,
            observations=scrub_observations(state.get("observations", [])),
            safety=safety,
            timings=timings,
            evidence=evidence,
            preparation_analysis=None,
        )

    def stream(self, question: str, *, context: str | None = None, mode: str = "live"):
        """Stream LangGraph node updates in real-time for AG-UI protocol."""
        initial_state = {
            "question": question,
            "context": context,
            "mode": mode,
            "observations": [],
            "timings": {},
        }

        # LangGraph .stream() yields {node_name: node_output} for each node
        for chunk in self._graph.stream(initial_state):
            yield chunk

    # ------------------------------------------------------------------
    def _node_analyze(self, state: dict) -> dict:
        start = time.perf_counter()
        analysis = self.analyzer.analyze(state["question"], context=state.get("context"))
        duration = time.perf_counter() - start

        observations = self._append_ag_message(
            state,
            role="reasoning",
            title="질문 분석",
            content=f"도메인: {analysis.domain}, 복잡도: {analysis.complexity}, 안전도: {analysis.safety.value}",
        )

        # Pass mode to strategy selection
        mode = state.get("mode", "live")
        strategy = self._select_strategy(analysis, state["question"], state.get("context"), mode)
        observations = self._append_ag_message(
            state,
            role="action",
            title="검색 전략 선택",
            content=f"선택된 전략: {strategy['name']} (모드: {mode})",
        )
        self._update_timings(state, "analysis", duration)
        base = self._base_state(state)
        base.update(
            {
                "analysis": analysis,
                "observations": observations,
                "strategy": strategy["name"],
                "strategy_config": strategy,
            }
        )
        return base

    def _node_safety(self, state: dict) -> dict:
        start = time.perf_counter()
        analysis: QuestionAnalysisResult = state["analysis"]
        envelope = build_safety_envelope(analysis)
        duration = time.perf_counter() - start

        observations = self._append_ag_message(
            state,
            role="action",
            title="안전성 검증",
            content=f"안전 수준: {analysis.safety.value}",
        )
        self._update_timings(state, "safety", duration)
        base = self._base_state(state)
        update = {
            "analysis": analysis,
            "safety": envelope,
            "observations": observations,
        }
        base.update(update)
        if analysis.safety is SafetyLevel.ESCALATE:
            update["answer"] = envelope.answer_override or ""
            update["citations"] = []
            update["evidence"] = []
        base.update(update)
        return base

    def _route_after_safety(self, state: dict) -> str:
        envelope: SafetyEnvelope = state["safety"]
        if envelope.level is SafetyLevel.ESCALATE:
            return "escalate"

        # Route based on mode
        mode = state.get("mode", "live")
        if mode == "preparation":
            return "proceed_prep"
        return "proceed_live"

    def _route_post_rewrite(self, state: dict) -> str:
        strategy = state.get("strategy")
        if strategy == "decompose":
            return "decompose"
        if strategy == "graph":
            return "graph"
        return "vector"

    def _route_post_vector(self, state: dict) -> str:
        return "merge"

    def _node_rewrite(self, state: dict) -> dict:
        start = time.perf_counter()
        analysis: QuestionAnalysisResult = state["analysis"]
        strategy = state.get("strategy", "vector")
        rewritten = self._rewrite_question(state["question"], analysis, strategy=strategy)
        duration = time.perf_counter() - start

        observations = self._append_ag_message(
            state,
            role="action",
            title="질문 재작성",
            content=f"재작성된 질문: {rewritten}",
        )
        self._update_timings(state, "rewrite", duration)
        base = self._base_state(state)
        base.update(
            {
                "analysis": state.get("analysis"),
                "safety": state.get("safety"),
                "rewritten_question": rewritten,
                "observations": observations,
            }
        )
        return base

    def _node_vector_retrieval(self, state: dict) -> dict:
        if state.get("strategy") != "vector":
            observations = self._append_ag_message(
                state,
                role="action",
                title="Vector 검색",
                content="전략에 따라 건너뜀",
            )
            base = self._base_state(state)
            base.update(
                {
                    "analysis": state.get("analysis"),
                    "safety": state.get("safety"),
                    "vector_results": [],
                    "observations": observations,
                }
            )
            return base

        query = state.get("rewritten_question") or state["question"]
        start = time.perf_counter()
        config = state.get("strategy_config", {})
        vector_k = config.get("vector_k", self.default_vector_top_k)
        results = self.vector_retriever.retrieve(query, limit=vector_k)
        duration = time.perf_counter() - start

        observations = self._append_ag_message(
            state,
            role="action",
            title="Vector 검색 실행",
            content=f"{len(results)}개의 관련 문서를 찾았습니다",
        )
        self._update_timings(state, "retrieval_vector", duration)
        base = self._base_state(state)
        base.update(
            {
                "analysis": state.get("analysis"),
                "safety": state.get("safety"),
                "vector_results": results,
                "observations": observations,
            }
        )
        return base

    def _node_graph_retrieval(self, state: dict) -> dict:
        if state.get("strategy") != "graph":
            observations = self._append_ag_message(
                state,
                role="action",
                title="Graph 검색",
                content="전략에 따라 건너뜀",
            )
            base = self._base_state(state)
            base.update(
                {
                    "analysis": state.get("analysis"),
                    "safety": state.get("safety"),
                    "graph_results": [],
                    "observations": observations,
                }
            )
            return base

        query = state.get("rewritten_question") or state["question"]
        start = time.perf_counter()
        config = state.get("strategy_config", {})
        graph_k = config.get("graph_k", self.graph_top_k)
        results = self.graph_retriever.retrieve(query, limit=graph_k)
        duration = time.perf_counter() - start
        observations = self._append_ag_message(
            state,
            role="action",
            title="Graph 검색 실행",
            content=f"{len(results)}개의 관계 문서를 찾았습니다",
        )
        self._update_timings(state, "retrieval_graph", duration)
        base = self._base_state(state)
        base.update(
            {
                "analysis": state.get("analysis"),
                "safety": state.get("safety"),
                "graph_results": results,
                "observations": observations,
            }
        )
        return base

    def _node_decompose(self, state: dict) -> dict:
        start = time.perf_counter()
        analysis: QuestionAnalysisResult = state["analysis"]
        question = state.get("rewritten_question") or state["question"]
        subquestions = self._decompose_question(question, analysis)

        config = state.get("strategy_config", {})
        limit = config.get("sub_limit", 5)

        # PARALLEL EXECUTION: Retrieve all sub-questions concurrently
        async def _retrieve_parallel() -> List[Chunk]:
            tasks = []
            for subquestion in subquestions:
                search_type = self._determine_question_type(subquestion)
                if search_type == "graph":
                    # Primary: graph, fallback: vector
                    task = self._retrieve_with_fallback(
                        subquestion, limit, primary="graph", fallback="vector"
                    )
                else:
                    # Primary: vector, fallback: graph
                    task = self._retrieve_with_fallback(
                        subquestion, limit, primary="vector", fallback="graph"
                    )
                tasks.append((subquestion, search_type, task))

            # Execute all tasks in parallel
            results = await asyncio.gather(*[task for _, _, task in tasks])

            # Flatten and enrich results
            evidence: List[Chunk] = []
            for (subquestion, search_type, _), chunks in zip(tasks, results):
                for chunk in chunks:
                    enriched = replace(chunk)
                    enriched.metadata = dict(chunk.metadata)
                    enriched.metadata["subquestion"] = subquestion
                    enriched.metadata.setdefault("retrieval", search_type)
                    evidence.append(enriched)

            return evidence

        # Run async code in sync context
        try:
            evidence = asyncio.run(_retrieve_parallel())
        except RuntimeError:
            # Event loop already running - use nest_asyncio
            try:
                import nest_asyncio

                nest_asyncio.apply()
                evidence = asyncio.run(_retrieve_parallel())
            except Exception as exc:
                LOGGER.warning("Parallel execution failed, falling back to sequential: %s", exc)
                evidence = self._retrieve_sequential(subquestions, limit)

        # Deduplication (existing logic)
        deduped: List[Chunk] = []
        seen = set()
        for chunk in evidence:
            if chunk.chunk_id in seen:
                continue
            seen.add(chunk.chunk_id)
            deduped.append(chunk)
            if len(deduped) >= self.max_evidence:
                break

        observations = self._append_ag_message(
            state,
            role="action",
            title="질문 분해 및 병렬 검색",
            content=f"{len(subquestions)}개의 하위 질문으로 분해, {len(deduped)}개의 증거 수집 (병렬 실행)",
        )
        self._update_timings(state, "decompose", time.perf_counter() - start)
        base = self._base_state(state)
        base.update(
            {
                "analysis": analysis,
                "safety": state.get("safety"),
                "observations": observations,
                "subquestions": subquestions,
                "evidence": deduped,
            }
        )
        return base

    def _select_strategy(
        self,
        analysis: QuestionAnalysisResult,
        question: str,
        context: str | None,
        mode: str = "live",
    ) -> Dict[str, object]:
        complexity = analysis.complexity.lower()
        question_trimmed = question.strip()
        connectors = {"그리고", "및", "또", "동시에", "고 ", " 고 ", "며", " 와 ", " 과 "}
        relationship_keywords = {"관계", "영향", "연관", "비교", "차이", "상관", "함께", "동시에"}
        contains_connector = any(connector in question_trimmed for connector in connectors)
        contains_relationship = any(
            keyword in question_trimmed for keyword in relationship_keywords
        )
        multiple_questions = question_trimmed.count("?") >= 2

        # Mode-specific top-k values
        if mode == "live":
            vector_k_simple = 3
            vector_k_complex = 5
            graph_k = 5
            sub_limit = 5
        else:  # preparation mode
            vector_k_simple = 5
            vector_k_complex = 7
            graph_k = 7
            sub_limit = 7

        if complexity == "simple":
            if contains_relationship:
                return {"name": "graph", "graph_k": graph_k}
            if contains_connector or multiple_questions or len(question_trimmed) >= 100:
                return {"name": "decompose", "sub_limit": sub_limit}
            return {"name": "vector", "vector_k": vector_k_simple}

        if complexity == "multi-hop":
            if contains_relationship or contains_connector:
                return {"name": "graph", "graph_k": graph_k}
            return {"name": "vector", "vector_k": vector_k_complex}

        # Treat compound/long questions as complex and perform decomposition
        return {"name": "decompose", "sub_limit": sub_limit}

    def _decompose_question(self, question: str, analysis: QuestionAnalysisResult) -> List[str]:
        prompt = (
            "복잡한 상담 질문을 2~3개의 하위 질문으로 분해하세요.\n"
            "- 각 하위 질문은 독립적으로 검색 가능해야 합니다.\n"
            "- 운동/식단/생활습관과 관련된 핵심 키워드를 유지하세요.\n"
            f"질문: {question}\n하위 질문 목록 (번호 없이 한 줄에 하나 씩):"
        )
        if self.small_llm:
            response = self.small_llm.invoke([HumanMessage(content=prompt)])
            text = response.content.strip()
        else:
            text = question  # Fallback
        candidates: List[str] = []
        for line in text.splitlines():
            normalized = line.strip("-• ").strip()
            if normalized:
                candidates.append(normalized)

        if not candidates:
            # Fallback heuristic splitting by conjunctions or question marks
            for token in ["?", "그리고", "및", "또"]:
                if token in question:
                    parts = [part.strip() for part in question.split(token) if part.strip()]
                    if len(parts) > 1:
                        candidates.extend(parts)
                        break

        if not candidates:
            candidates.append(question.strip())

        # Limit to 3 subquestions to keep retrieval bounded
        return candidates[:3]

    @staticmethod
    def _determine_question_type(text: str) -> str:
        text = text.lower()
        relationship_keywords = {
            "관계",
            "영향",
            "연관",
            "비교",
            "차이",
            "상관",
            "같이",
            "함께",
            "동시에",
        }
        connectors = {"그리고", "및", "또", "동시에", "하지만"}
        if any(keyword in text for keyword in relationship_keywords) or any(
            connector in text for connector in connectors
        ):
            return "graph"
        if "네트워크" in text or "연결" in text:
            return "graph"
        return "vector"

    def _node_merge_evidence(self, state: dict) -> dict:
        if state.get("strategy") == "decompose" and state.get("evidence"):
            observations = self._append_ag_message(
                state,
                role="observation",
                title="증거 병합",
                content="분해된 질문의 증거를 재사용",
            )
            base = self._base_state(state)
            base.update(
                {
                    "analysis": state.get("analysis"),
                    "safety": state.get("safety"),
                    "evidence": list(state.get("evidence", [])),
                    "observations": observations,
                }
            )
            return base

        vector_results: List[Chunk] = list(state.get("vector_results", []))
        graph_results: List[Chunk] = list(state.get("graph_results", []))

        merged: List[Chunk] = []
        seen = set()
        combined = list(vector_results) + list(graph_results)
        combined.sort(key=lambda item: getattr(item, "score", 0.0) or 0.0, reverse=True)

        for chunk in combined:
            if chunk.chunk_id in seen:
                continue
            seen.add(chunk.chunk_id)
            merged.append(chunk)
            if len(merged) >= self.max_evidence:
                break

        observations = self._append_ag_message(
            state,
            role="observation",
            title="증거 병합 완료",
            content=f"Vector: {len(vector_results)}개, Graph: {len(graph_results)}개, 고유: {len(merged)}개",
        )
        base = self._base_state(state)
        base.update(
            {
                "analysis": state.get("analysis"),
                "safety": state.get("safety"),
                "evidence": merged,
                "observations": observations,
            }
        )
        return base

    def _node_synthesize(self, state: dict) -> dict:
        start = time.perf_counter()
        analysis: QuestionAnalysisResult = state["analysis"]
        evidence: List[Chunk] = list(state.get("evidence", []))
        answer, citations = self._synthesize_answer(
            state["question"], analysis, evidence, state.get("strategy", "vector")
        )
        duration = time.perf_counter() - start

        observations = self._append_ag_message(
            state,
            role="observation",
            title="답변 생성 완료",
            content=f"증거 {len(evidence)}개를 기반으로 답변을 생성했습니다",
        )
        self._update_timings(state, "synthesis", duration)
        base = self._base_state(state)
        base.update(
            {
                "analysis": state.get("analysis"),
                "safety": state.get("safety"),
                "answer": answer,
                "citations": citations,
                "observations": observations,
            }
        )
        return base

    # ------------------------------------------------------------------
    def _rewrite_question(
        self, question: str, analysis: QuestionAnalysisResult, *, strategy: str
    ) -> str:
        normalized = question.strip()
        if strategy == "vector":
            return normalized

        prompt = (
            "아래 상담 질문을 검색에 유리하게 1문장으로 정제해 주세요."
            "\n- 핵심 키워드를 유지하고, 불필요한 감탄/수식어는 제거합니다."
            "\n- 운동/식단/생활습관과 관련된 세부 용어는 유지합니다."
            "\n질문: "
            f"{normalized}\n정제된 질문:"
        )
        if self.small_llm:
            response = self.small_llm.invoke([HumanMessage(content=prompt)])
            rewritten = response.content.strip()
        else:
            rewritten = normalized  # Fallback
        if not rewritten or "정제된 질문" in rewritten or "검색에 유리" in rewritten:
            rewritten = normalized
        return rewritten

    def _synthesize_answer(
        self,
        question: str,
        analysis: QuestionAnalysisResult,
        evidence: Sequence[Chunk],
        strategy: str,
    ) -> tuple[str, List[str]]:
        citations = [f"[{chunk.chunk_id}]" for chunk in evidence]
        evidence_snippets = "\n".join(
            f"- ({idx+1}) {chunk.chunk_id}: {chunk.text}"
            for idx, chunk in enumerate(evidence[: self.max_evidence])
        )

        if evidence:
            prompt = (
                "당신은 대사증후군 상담사를 돕는 시스템입니다."
                "\n다음 근거를 정리하여 2-3문장 답변을 작성하세요."
                "\n- 구체적인 행동 권장(예: 주 5회 30분 등)을 포함하세요."
                "\n- 의학적 판단/약물 조언은 피하고 필요한 경우 담당 의사 상담을 안내하세요."
                "\n- 마지막 문장에 근거 번호를 괄호 형태로 첨부하세요."
                f"\n질문: {question}"
                f"\n질문 전략: {strategy}"
                f"\n근거:\n{evidence_snippets}\n답변:"
            )
            if self.main_llm:
                response = self.main_llm.invoke([HumanMessage(content=prompt)])
                answer = response.content.strip()
            else:
                answer = "LLM이 초기화되지 않아 답변을 생성할 수 없습니다."
            if not answer:
                answer = (
                    "근거 자료를 바탕으로 생활습관 개선을 권장드립니다. 하루 30분 내외의 중등도 운동을 주 5회 정도 "
                    "실천하고, 상담 시 근거 번호를 함께 안내해 주세요."
                )
            if citations and citations[0] not in answer:
                answer = f"{answer} ({', '.join(citations)})"
            return answer, citations

        message = (
            "현재 확보된 자료에서 직접적인 근거를 찾지 못했습니다. "
            "일반적인 생활습관 가이드라인을 참고하시고, 필요 시 담당 의사와 상담해 주세요."
        )
        return message, []

    # ------------------------------------------------------------------
    @staticmethod
    def _append_observation(state: dict, message: str) -> List[str]:
        """Legacy method for backward compatibility."""
        observations = list(state.get("observations", []))
        observations.append(message)
        state["observations"] = observations
        return observations

    @staticmethod
    def _append_ag_message(
        state: dict, *, role: str, title: str, content: str
    ) -> List[Dict[str, str]]:
        """Append structured AG-UI protocol message."""
        observations = list(state.get("observations", []))
        ag_message = {
            "role": role,  # reasoning, action, observation
            "title": title,
            "content": content,
        }
        observations.append(ag_message)
        state["observations"] = observations
        return observations

    @staticmethod
    def _update_timings(state: dict, stage: str, duration: float) -> Dict[str, float]:
        entries = list(state.get("_timing_entries", []))
        entries.append((stage, duration))
        state["_timing_entries"] = entries
        return dict(entries)

    # ------------------------------------------------------------------
    # Parallel execution helper methods
    # ------------------------------------------------------------------
    async def _retrieve_with_fallback(
        self, query: str, limit: int, *, primary: str, fallback: str
    ) -> List[Chunk]:
        """Retrieve with primary strategy and fallback."""
        if primary == "graph":
            hits = await self.graph_retriever.retrieve_async(query, limit=limit)
            if not hits:
                hits = await self.vector_retriever.retrieve_async(query, limit=limit)
        else:
            hits = await self.vector_retriever.retrieve_async(query, limit=limit)
            if not hits:
                hits = await self.graph_retriever.retrieve_async(query, limit=limit)

        # Sort by score
        hits.sort(key=lambda item: getattr(item, "score", 0.0) or 0.0, reverse=True)
        return hits[:limit]

    def _retrieve_sequential(self, subquestions: List[str], limit: int) -> List[Chunk]:
        """Fallback sequential retrieval (original logic)."""
        evidence: List[Chunk] = []
        for subquestion in subquestions:
            search_type = self._determine_question_type(subquestion)
            if search_type == "graph":
                hits = self.graph_retriever.retrieve(subquestion, limit=limit)
                if not hits:
                    hits = self.vector_retriever.retrieve(subquestion, limit=limit)
            else:
                hits = self.vector_retriever.retrieve(subquestion, limit=limit)
                if not hits:
                    hits = self.graph_retriever.retrieve(subquestion, limit=limit)

            hits.sort(key=lambda item: getattr(item, "score", 0.0) or 0.0, reverse=True)
            for chunk in hits[:limit]:
                enriched = replace(chunk)
                enriched.metadata = dict(chunk.metadata)
                enriched.metadata["subquestion"] = subquestion
                enriched.metadata.setdefault("retrieval", search_type)
                evidence.append(enriched)

        return evidence

    @staticmethod
    def _base_state(state: dict) -> Dict[str, object]:
        base = dict(state)
        base["question"] = state.get("question")
        base["context"] = state.get("context")
        if "_timing_entries" in state:
            base["_timing_entries"] = list(state["_timing_entries"])
        if "observations" in base:
            base["observations"] = list(base["observations"])
        return base

    # ------------------------------------------------------------------
    # Preparation Mode Nodes
    # ------------------------------------------------------------------
    def _node_prep_analyze_patient(self, state: dict) -> dict:
        """Step 1: Analyze patient state from context."""
        start = time.perf_counter()
        context = state.get("context", "")

        prompt = (
            "아래 환자 정보를 분석하여 현재 상태를 요약하세요.\n"
            "- 객관적 수치만 전달 (BMI, 혈압, 혈당 등)\n"
            "- 주요 관리 포인트 3-5개 도출\n"
            "- 의학적 판단은 하지 말 것\n\n"
            f"환자 정보:\n{context}\n\n"
            "요약:"
        )

        if self.main_llm:
            response = self.main_llm.invoke([HumanMessage(content=prompt)])
            summary = response.content.strip()
        else:
            summary = "환자 정보를 확인하세요."  # Fallback

        patient_state = PatientStateAnalysis(
            summary=summary,
            key_metrics={},
            concerns=[],
        )

        duration = time.perf_counter() - start
        observations = self._append_ag_message(
            state,
            role="action",
            title="환자 상태 분석 완료",
            content=f"현재 상태 요약 완료",
        )

        self._update_timings(state, "prep_patient_analysis", duration)
        base = self._base_state(state)
        base.update(
            {
                "patient_state": patient_state,
                "observations": observations,
            }
        )
        return base

    def _node_prep_analyze_history(self, state: dict) -> dict:
        """Step 2: Analyze previous consultation patterns."""
        start = time.perf_counter()
        context = state.get("context", "")

        prompt = (
            "이전 상담 기록을 분석하여 패턴을 파악하세요.\n"
            "- 다뤘던 주제들\n"
            "- 환자의 실천 여부\n"
            "- 어려워했던 부분\n\n"
            f"상담 기록:\n{context}\n\n"
            "이전 기록이 없다면 '없음'이라고 응답하세요.\n\n"
            "분석:"
        )

        if self.main_llm:
            response = self.main_llm.invoke([HumanMessage(content=prompt)])
            analysis_text = response.content.strip()
        else:
            analysis_text = "없음"  # Fallback

        if "없음" in analysis_text or not analysis_text:
            pattern = None
        else:
            pattern = ConsultationPattern(
                previous_topics=[],
                adherence_notes=[],
                difficulties=[],
            )

        duration = time.perf_counter() - start
        observations = self._append_ag_message(
            state,
            role="action",
            title="상담 이력 분석 완료",
            content="이전 패턴 파악됨" if pattern else "이전 기록 없음",
        )

        self._update_timings(state, "prep_history_analysis", duration)
        base = self._base_state(state)
        base.update(
            {
                "consultation_pattern": pattern,
                "observations": observations,
            }
        )
        return base

    def _node_prep_generate_questions(self, state: dict) -> dict:
        """Step 3: Generate expected questions based on patient state."""
        start = time.perf_counter()

        patient_state: PatientStateAnalysis = state["patient_state"]
        pattern: ConsultationPattern | None = state.get("consultation_pattern")

        context_parts = [f"환자 상태: {patient_state.summary}"]
        if pattern:
            context_parts.append(f"이전 상담: 있음")

        prompt = (
            "아래 환자 정보를 바탕으로 이번 상담에서 나올 가능성이 높은 질문 5개를 생성하세요.\n"
            "- 운동 관련 질문\n"
            "- 식단 관련 질문\n"
            "- 생활습관 관련 질문\n\n"
            f"{chr(10).join(context_parts)}\n\n"
            "예상 질문 목록 (번호 없이 한 줄에 하나씩):"
        )

        if self.small_llm:
            response = self.small_llm.invoke([HumanMessage(content=prompt)])
            questions_text = response.content.strip()
        else:
            questions_text = ""  # Fallback

        expected_questions_text = []
        for line in questions_text.splitlines():
            normalized = line.strip("-• ").strip()
            if normalized and "?" in normalized:
                expected_questions_text.append(normalized)

        expected_questions_text = expected_questions_text[:5]

        duration = time.perf_counter() - start
        observations = self._append_ag_message(
            state,
            role="action",
            title="예상 질문 생성 완료",
            content=f"{len(expected_questions_text)}개의 예상 질문 생성됨",
        )

        self._update_timings(state, "prep_question_generation", duration)
        base = self._base_state(state)
        base.update(
            {
                "expected_questions_text": expected_questions_text,
                "observations": observations,
            }
        )
        return base

    def _node_prep_prepare_answers(self, state: dict) -> dict:
        """Step 4: Prepare recommended answers for expected questions (WITH PARALLEL EXECUTION)."""
        start = time.perf_counter()

        expected_questions_text: List[str] = state.get("expected_questions_text", [])

        async def _prepare_answers_parallel() -> List[ExpectedQuestion]:
            tasks = []
            for question_text in expected_questions_text:
                task = self._prepare_single_answer(question_text)
                tasks.append(task)

            return await asyncio.gather(*tasks)

        try:
            expected_questions = asyncio.run(_prepare_answers_parallel())
        except RuntimeError:
            try:
                import nest_asyncio

                nest_asyncio.apply()
                expected_questions = asyncio.run(_prepare_answers_parallel())
            except Exception as exc:
                LOGGER.warning("Parallel answer prep failed, using sequential: %s", exc)
                expected_questions = [
                    self._prepare_single_answer_sync(q) for q in expected_questions_text
                ]

        duration = time.perf_counter() - start
        observations = self._append_ag_message(
            state,
            role="action",
            title="권장 답변 준비 완료",
            content=f"{len(expected_questions)}개의 답변 준비됨 (병렬 실행)",
        )

        self._update_timings(state, "prep_answer_preparation", duration)
        base = self._base_state(state)
        base.update(
            {
                "expected_questions": expected_questions,
                "observations": observations,
            }
        )
        return base

    async def _prepare_single_answer(self, question: str) -> ExpectedQuestion:
        """Prepare answer for a single expected question (async)."""
        analysis = self.analyzer.analyze(question)

        if analysis.complexity == "simple":
            chunks = await self.vector_retriever.retrieve_async(question, limit=5)
        else:
            vector_task = self.vector_retriever.retrieve_async(question, limit=5)
            graph_task = self.graph_retriever.retrieve_async(question, limit=5)
            vector_chunks, graph_chunks = await asyncio.gather(vector_task, graph_task)
            chunks = list(vector_chunks) + list(graph_chunks)
            chunks.sort(key=lambda c: getattr(c, "score", 0.0) or 0.0, reverse=True)
            chunks = chunks[:5]

        # Generate actual answer using LLM
        evidence_snippets = "\n".join(
            f"- ({idx+1}) {chunk.chunk_id}: {chunk.text[:200]}"
            for idx, chunk in enumerate(chunks[:3])
        )
        
        prompt = (
            "예상 질문에 대한 권장 답변을 작성하세요.\n"
            "- 2-3문장으로 간결하게 답변\n"
            "- 구체적인 행동 권장 포함 (예: 하루 30분, 주 5회)\n"
            "- 제안의 톤 유지 ('~를 권장드립니다', '~하시면 좋습니다')\n"
            "- 의학적 판단은 피하고 일반적인 가이드라인만 제공\n\n"
            f"예상 질문: {question}\n\n"
            f"근거:\n{evidence_snippets}\n\n"
            "권장 답변:"
        )

        if self.small_llm:
            response = self.small_llm.invoke([HumanMessage(content=prompt)])
            answer = response.content.strip()
        else:
            answer = "근거 자료를 바탕으로 생활습관 개선을 권장합니다."  # Fallback
        
        # Extract citations from chunks
        citations = []
        for chunk in chunks[:3]:
            doc_id = chunk.metadata.get("document_id", chunk.document_id)
            if doc_id:
                # Try to extract guideline name from document_id or metadata
                guideline_name = chunk.metadata.get("guideline_name") or doc_id
                citations.append(f"{guideline_name}" if guideline_name else chunk.chunk_id)

        return ExpectedQuestion(
            question=question,
            recommended_answer=answer or "일반적인 생활습관 가이드라인을 참고하여 상담하시면 좋습니다.",
            evidence_chunks=chunks,
            citations=citations,
        )

    def _prepare_single_answer_sync(self, question: str) -> ExpectedQuestion:
        """Synchronous fallback for answer preparation."""
        analysis = self.analyzer.analyze(question)

        if analysis.complexity == "simple":
            chunks = self.vector_retriever.retrieve(question, limit=5)
        else:
            vector_chunks = self.vector_retriever.retrieve(question, limit=5)
            graph_chunks = self.graph_retriever.retrieve(question, limit=5)
            chunks = list(vector_chunks) + list(graph_chunks)
            chunks.sort(key=lambda c: getattr(c, "score", 0.0) or 0.0, reverse=True)
            chunks = chunks[:5]

        # Generate actual answer using LLM
        evidence_snippets = "\n".join(
            f"- ({idx+1}) {chunk.chunk_id}: {chunk.text[:200]}"
            for idx, chunk in enumerate(chunks[:3])
        )
        
        prompt = (
            "예상 질문에 대한 권장 답변을 작성하세요.\n"
            "- 2-3문장으로 간결하게 답변\n"
            "- 구체적인 행동 권장 포함 (예: 하루 30분, 주 5회)\n"
            "- 제안의 톤 유지 ('~를 권장드립니다', '~하시면 좋습니다')\n"
            "- 의학적 판단은 피하고 일반적인 가이드라인만 제공\n\n"
            f"예상 질문: {question}\n\n"
            f"근거:\n{evidence_snippets}\n\n"
            "권장 답변:"
        )

        if self.small_llm:
            response = self.small_llm.invoke([HumanMessage(content=prompt)])
            answer = response.content.strip()
        else:
            answer = "근거 자료를 바탕으로 생활습관 개선을 권장합니다."  # Fallback
        
        # Extract citations from chunks
        citations = []
        for chunk in chunks[:3]:
            doc_id = chunk.metadata.get("document_id", chunk.document_id)
            if doc_id:
                # Try to extract guideline name from document_id or metadata
                guideline_name = chunk.metadata.get("guideline_name") or doc_id
                citations.append(f"{guideline_name}" if guideline_name else chunk.chunk_id)

        return ExpectedQuestion(
            question=question,
            recommended_answer=answer or "일반적인 생활습관 가이드라인을 참고하여 상담하시면 좋습니다.",
            evidence_chunks=chunks,
            citations=citations,
        )

    def _node_prep_delivery_examples(self, state: dict) -> dict:
        """Step 5: Generate delivery method examples."""
        start = time.perf_counter()

        patient_state: PatientStateAnalysis = state["patient_state"]

        delivery_examples = [
            DeliveryExample(
                topic="체중 관리",
                technical_version="BMI 28.5로 과체중 범위입니다",
                patient_friendly_version="현재 체중이 건강 범위보다 조금 높은 편이에요",
                framing_notes="긍정적으로 프레이밍, '과체중' 대신 완곡한 표현 사용",
            )
        ]

        duration = time.perf_counter() - start
        observations = self._append_ag_message(
            state,
            role="action",
            title="전달 방식 예시 생성 완료",
            content=f"{len(delivery_examples)}개의 전달 예시 생성됨",
        )

        self._update_timings(state, "prep_delivery_examples", duration)
        base = self._base_state(state)
        base.update(
            {
                "delivery_examples": delivery_examples,
                "observations": observations,
            }
        )
        return base

    def _node_prep_synthesize(self, state: dict) -> dict:
        """Final synthesis node for preparation mode."""
        start = time.perf_counter()

        patient_state: PatientStateAnalysis = state["patient_state"]
        pattern: ConsultationPattern | None = state.get("consultation_pattern")
        expected_questions: List[ExpectedQuestion] = state.get("expected_questions", [])
        delivery_examples: List[DeliveryExample] = state.get("delivery_examples", [])

        prep_analysis = PreparationAnalysis(
            patient_state=patient_state,
            consultation_pattern=pattern,
            expected_questions=expected_questions,
            delivery_examples=delivery_examples,
            warnings=[
                "의학적 판단이 필요한 질문은 담당 의사에게 에스컬레이션하세요",
                "약물 관련 질문은 절대 답변하지 마세요",
            ],
            timings=dict(state.get("_timing_entries", [])),
        )

        duration = time.perf_counter() - start
        observations = self._append_ag_message(
            state,
            role="observation",
            title="상담 준비 완료",
            content=f"총 {len(expected_questions)}개의 예상 질문 및 답변 준비됨",
        )

        self._update_timings(state, "prep_synthesis", duration)
        base = self._base_state(state)
        base.update(
            {
                "preparation_analysis": prep_analysis,
                "observations": observations,
            }
        )
        return base

    def __del__(self) -> None:  # pragma: no cover - best effort cleanup
        try:
            self.graph_retriever.close()
        except Exception:
            pass


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    pipeline = RetrievalPipeline()
    sample = "혈당이 높은데 어떤 운동을 권장하면 좋을까요?"
    output = pipeline.run(sample)
    LOGGER.info("Answer: %s", output.answer)
    LOGGER.info("Citations: %s", output.citations)
    for obs in output.observations:
        LOGGER.info(obs)
