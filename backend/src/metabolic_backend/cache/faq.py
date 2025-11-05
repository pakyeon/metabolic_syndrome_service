"""FAQ caching system for frequently asked questions.

Provides <0.1s response time for common questions using semantic similarity search.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np


class FAQCache:
    """FAQ caching system with semantic similarity search and TTL management."""

    def __init__(self, cache_file: Path):
        self.cache_file = cache_file
        self.cache: Dict[str, Dict] = {}
        self.embeddings: Optional[np.ndarray] = None
        self.questions: List[str] = []

        # Try to use sentence-transformers for better performance
        try:
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            self.use_sentence_transformer = True
        except ImportError:
            logging.warning(
                "sentence-transformers not installed, falling back to simple string matching"
            )
            self.model = None
            self.use_sentence_transformer = False

        self._load_cache()

    def _load_cache(self):
        """Load cache from file and generate embeddings."""
        if self.cache_file.exists():
            with open(self.cache_file, "r", encoding="utf-8") as f:
                self.cache = json.load(f)

            logging.info(f"Loaded {len(self.cache)} FAQ entries from cache")

            # Generate embeddings for questions
            self.questions = list(self.cache.keys())
            if self.use_sentence_transformer and self.questions:
                self.embeddings = self.model.encode(self.questions)
                logging.info(f"Generated embeddings for {len(self.questions)} questions")
        else:
            logging.info("No FAQ cache file found, starting with empty cache")

    def get(self, question: str, similarity_threshold: float = 0.85) -> Optional[str]:
        """
        Get cached answer for a question if it exists and is similar enough.

        Args:
            question: User question
            similarity_threshold: Minimum similarity score (0.0-1.0)

        Returns:
            Cached answer if found and valid, None otherwise
        """
        if not self.questions:
            return None

        if self.use_sentence_transformer:
            return self._get_with_embeddings(question, similarity_threshold)
        else:
            return self._get_with_string_match(question, similarity_threshold)

    def _get_with_embeddings(self, question: str, similarity_threshold: float) -> Optional[str]:
        """Use semantic similarity search with embeddings."""
        # Encode query
        query_embedding = self.model.encode([question])[0]

        # Calculate cosine similarity
        similarities = np.dot(self.embeddings, query_embedding) / (
            np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_embedding)
        )

        # Find most similar question
        max_idx = np.argmax(similarities)
        max_similarity = similarities[max_idx]

        if max_similarity >= similarity_threshold:
            matched_question = self.questions[max_idx]
            cached_data = self.cache[matched_question]

            # Check TTL
            if self._is_valid(cached_data):
                logging.info(
                    f"FAQ cache hit: {question[:50]}... → {matched_question[:50]}... "
                    f"(similarity: {max_similarity:.3f})"
                )
                return cached_data["answer"]
            else:
                logging.info(f"FAQ cache expired for: {matched_question[:50]}...")
                # Remove expired entry
                del self.cache[matched_question]
                self._save_cache()
                self._load_cache()  # Reload to update embeddings

        return None

    def _get_with_string_match(self, question: str, similarity_threshold: float) -> Optional[str]:
        """Fallback to simple string matching."""
        question_lower = question.lower().strip()

        for cached_question, cached_data in self.cache.items():
            cached_lower = cached_question.lower().strip()

            # Simple Jaccard similarity
            q_words = set(question_lower.split())
            c_words = set(cached_lower.split())

            if not q_words or not c_words:
                continue

            intersection = len(q_words & c_words)
            union = len(q_words | c_words)
            similarity = intersection / union if union > 0 else 0.0

            if similarity >= similarity_threshold:
                if self._is_valid(cached_data):
                    logging.info(
                        f"FAQ cache hit (string match): {question[:50]}... → {cached_question[:50]}... "
                        f"(similarity: {similarity:.3f})"
                    )
                    return cached_data["answer"]
                else:
                    # Remove expired entry
                    del self.cache[cached_question]
                    self._save_cache()

        return None

    def _is_valid(self, cached_data: Dict) -> bool:
        """Check if cached entry is still valid based on TTL."""
        cached_at = datetime.fromisoformat(cached_data["cached_at"])
        ttl = timedelta(days=cached_data.get("ttl_days", 30))

        return datetime.now() - cached_at < ttl

    def set(self, question: str, answer: str, ttl_days: int = 30):
        """
        Add or update FAQ entry in cache.

        Args:
            question: The question text
            answer: The answer text
            ttl_days: Time to live in days (default: 30)
        """
        self.cache[question] = {
            "answer": answer,
            "cached_at": datetime.now().isoformat(),
            "ttl_days": ttl_days,
        }

        self._save_cache()
        self._load_cache()  # Reload to update embeddings

        logging.info(f"Added FAQ entry: {question[:50]}... (TTL: {ttl_days} days)")

    def _save_cache(self):
        """Save cache to file."""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def populate_defaults(self):
        """Populate cache with predefined FAQs."""
        defaults = {
            "운동은 얼마나 해야 하나요?": {
                "answer": "대한비만학회 가이드라인에 따르면, 주 150분 이상의 중강도 유산소 운동을 권장합니다. "
                "이를 주 5일로 나누면 하루 30분씩 걷기나 자전거 타기를 하시면 좋습니다. "
                "근력운동은 주 2-3회 추가하시면 더욱 효과적입니다.",
                "ttl_days": 90,
            },
            "혈당 목표치는 얼마인가요?": {
                "answer": "공복혈당은 100mg/dL 미만이 정상입니다. 100-125mg/dL은 당뇨병 전단계, "
                "126mg/dL 이상이면 당뇨병으로 진단됩니다. 개인별 목표는 담당 의사와 상담하세요.",
                "ttl_days": 90,
            },
            "어떤 식단이 좋나요?": {
                "answer": "채소, 통곡물, 저지방 단백질을 중심으로 한 균형 잡힌 식단을 권장합니다. "
                "하루 3끼 규칙적으로 드시고, 가공식품과 고염분 식품은 피하세요. "
                "야채는 매끼 2접시 이상, 과일은 하루 1-2회 적당량 섭취하시면 좋습니다.",
                "ttl_days": 90,
            },
            "허리둘레가 왜 중요한가요?": {
                "answer": "허리둘레는 복부비만을 나타내는 중요한 지표입니다. "
                "남성은 90cm, 여성은 85cm 이상일 때 대사증후군 위험이 높아집니다. "
                "복부지방은 인슐린 저항성과 심혈관 질환 위험을 증가시킵니다.",
                "ttl_days": 90,
            },
            "대사증후군이란 무엇인가요?": {
                "answer": "대사증후군은 복부비만, 고혈압, 고혈당, 고중성지방, 저HDL 콜레스테롤 중 "
                "3가지 이상을 동시에 가진 상태를 말합니다. 당뇨병과 심혈관 질환의 위험이 높아집니다. "
                "생활습관 개선으로 관리할 수 있습니다.",
                "ttl_days": 90,
            },
        }

        for question, data in defaults.items():
            if question not in self.cache:
                self.cache[question] = {
                    "answer": data["answer"],
                    "cached_at": datetime.now().isoformat(),
                    "ttl_days": data["ttl_days"],
                }

        self._save_cache()
        self._load_cache()
        logging.info(f"Populated {len(defaults)} default FAQ entries")

    def size(self) -> int:
        """Get number of cached entries."""
        return len(self.cache)

    def clear_expired(self):
        """Remove all expired entries from cache."""
        expired = [q for q, data in self.cache.items() if not self._is_valid(data)]

        for question in expired:
            del self.cache[question]

        if expired:
            self._save_cache()
            self._load_cache()
            logging.info(f"Cleared {len(expired)} expired FAQ entries")
