"""
Graph utilities for Graphiti knowledge graph integration.

This module provides a high-level interface for interacting with the
Graphiti knowledge graph system, which stores entities and relationships
extracted from metabolic syndrome research documents.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from contextlib import asynccontextmanager
import asyncio

from graphiti_core import Graphiti
from graphiti_core.utils.maintenance.graph_data_operations import clear_data
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.nodes import EpisodeType
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class GraphitiClient:
    """
    Manages Graphiti knowledge graph operations.

    The knowledge graph stores entities (diseases, treatments, biomarkers, etc.)
    and their relationships extracted from research documents. It enables
    semantic search and relationship traversal.
    """

    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_user: Optional[str] = None,
        neo4j_password: Optional[str] = None
    ):
        """
        Initialize Graphiti client.

        Args:
            neo4j_uri: Neo4j connection URI (defaults to NEO4J_URI env var)
            neo4j_user: Neo4j username (defaults to NEO4J_USER env var)
            neo4j_password: Neo4j password (defaults to NEO4J_PASSWORD env var)

        Raises:
            ValueError: If required environment variables are not set

        Example:
            # Using environment variables
            client = GraphitiClient()

            # Or with explicit credentials
            client = GraphitiClient(
                neo4j_uri="bolt://localhost:7687",
                neo4j_user="neo4j",
                neo4j_password="password"
            )
        """
        # Neo4j configuration
        self.neo4j_uri = neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = neo4j_user or os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = neo4j_password or os.getenv("NEO4J_PASSWORD")

        if not self.neo4j_password:
            raise ValueError(
                "NEO4J_PASSWORD environment variable not set. "
                "Please configure your Neo4j credentials."
            )

        # LLM configuration for entity extraction and relationship inference
        self.llm_base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.llm_api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.llm_choice = os.getenv("LLM_CHOICE", "gpt-4o-mini")

        if not self.llm_api_key:
            raise ValueError(
                "LLM_API_KEY or OPENAI_API_KEY environment variable not set"
            )

        # Embedding configuration for semantic search
        self.embedding_base_url = os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1")
        self.embedding_api_key = os.getenv("EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self.embedding_dimensions = int(os.getenv("VECTOR_DIMENSION", "1536"))

        if not self.embedding_api_key:
            raise ValueError(
                "EMBEDDING_API_KEY or OPENAI_API_KEY environment variable not set"
            )

        self.graphiti: Optional[Graphiti] = None
        self._initialized = False

    async def initialize(self):
        """
        Initialize Graphiti client and build graph indices.

        This should be called during application startup. It establishes
        connections to Neo4j and creates necessary indices for efficient
        graph traversal.

        Raises:
            Exception: If initialization fails
        """
        if self._initialized:
            return

        try:
            # Create LLM configuration
            llm_config = LLMConfig(
                api_key=self.llm_api_key,
                model=self.llm_choice,
                small_model=self.llm_choice,  # Can use different model for cheaper operations
                base_url=self.llm_base_url
            )

            # Create OpenAI LLM client
            llm_client = OpenAIClient(config=llm_config)

            # Create OpenAI embedder for semantic search
            embedder = OpenAIEmbedder(
                config=OpenAIEmbedderConfig(
                    api_key=self.embedding_api_key,
                    embedding_model=self.embedding_model,
                    embedding_dim=self.embedding_dimensions,
                    base_url=self.embedding_base_url
                )
            )

            # Initialize Graphiti with custom clients
            self.graphiti = Graphiti(
                self.neo4j_uri,
                self.neo4j_user,
                self.neo4j_password,
                llm_client=llm_client,
                embedder=embedder,
                cross_encoder=OpenAIRerankerClient(client=llm_client, config=llm_config)
            )

            # Build indices and constraints for efficient queries
            await self.graphiti.build_indices_and_constraints()

            self._initialized = True
            logger.info(
                f"Graphiti client initialized successfully "
                f"(LLM: {self.llm_choice}, Embedder: {self.embedding_model})"
            )

        except Exception as e:
            logger.error(f"Failed to initialize Graphiti: {e}")
            raise

    async def close(self):
        """
        Close Graphiti connection.

        Should be called during application shutdown.
        """
        if self.graphiti:
            await self.graphiti.close()
            self.graphiti = None
            self._initialized = False
            logger.info("Graphiti client closed")

    async def add_episode(
        self,
        episode_id: str,
        content: str,
        source: str,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Add an episode (document chunk) to the knowledge graph.

        The content will be analyzed to extract entities (diseases, treatments,
        biomarkers, etc.) and relationships, which are stored in the graph.

        Args:
            episode_id: Unique identifier for this episode (e.g., chunk ID)
            content: Text content to process
            source: Source description (e.g., document title or path)
            timestamp: Reference time for the episode (defaults to now)
            metadata: Additional metadata (not currently used by Graphiti)

        Example:
            await client.add_episode(
                episode_id="chunk_001",
                content="대사증후군은 당뇨병, 고혈압, 비만이 함께 나타나는 상태입니다.",
                source="metabolic_syndrome_guideline.pdf",
                metadata={"document_id": "doc_123", "page": 5}
            )
        """
        if not self._initialized:
            await self.initialize()

        episode_timestamp = timestamp or datetime.now(timezone.utc)

        await self.graphiti.add_episode(
            name=episode_id,
            episode_body=content,
            source=EpisodeType.text,  # Always text for our content
            source_description=source,
            reference_time=episode_timestamp
        )

        logger.debug(f"Added episode {episode_id} to knowledge graph from {source}")

    async def search(
        self,
        query: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Search the knowledge graph semantically.

        Uses embedding-based similarity to find relevant facts and relationships.

        Args:
            query: Search query (e.g., "metabolic syndrome diagnostic criteria")
            limit: Maximum number of results (None = return all matches)

        Returns:
            List of facts with metadata:
            - fact: The factual statement
            - uuid: Unique identifier
            - valid_at: When the fact became valid
            - invalid_at: When the fact became invalid (if applicable)
            - source_node_uuid: UUID of the source node

        Example:
            results = await client.search("대사증후군 진단 기준")
            for result in results:
                print(f"Fact: {result['fact']}")
                print(f"Valid from: {result['valid_at']}")
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Use Graphiti's semantic search
            raw_results = await self.graphiti.search(query)

            # Convert results to dictionaries
            results = [
                {
                    "fact": result.fact,
                    "uuid": str(result.uuid),
                    "valid_at": str(result.valid_at) if hasattr(result, 'valid_at') and result.valid_at else None,
                    "invalid_at": str(result.invalid_at) if hasattr(result, 'invalid_at') and result.invalid_at else None,
                    "source_node_uuid": str(result.source_node_uuid) if hasattr(result, 'source_node_uuid') and result.source_node_uuid else None
                }
                for result in raw_results
            ]

            # Apply limit if specified
            if limit:
                results = results[:limit]

            logger.debug(f"Graph search for '{query}' returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Graph search failed for query '{query}': {e}")
            return []

    async def get_related_entities(
        self,
        entity_name: str,
        relationship_types: Optional[List[str]] = None,
        depth: int = 1
    ) -> Dict[str, Any]:
        """
        Get entities and relationships related to a given entity.

        Uses semantic search to find facts involving the specified entity.

        Args:
            entity_name: Name of the entity (e.g., "당뇨병", "hypertension")
            relationship_types: Types of relationships (not used with Graphiti)
            depth: Maximum depth (not used with Graphiti)

        Returns:
            Dict containing:
            - central_entity: The queried entity
            - related_facts: List of facts involving the entity
            - search_method: Method used for search

        Example:
            relations = await client.get_related_entities("대사증후군")
            for fact in relations['related_facts']:
                print(fact['fact'])
        """
        if not self._initialized:
            await self.initialize()

        # Use semantic search to find relationships
        raw_results = await self.graphiti.search(f"relationships involving {entity_name}")

        # Extract facts
        facts = [
            {
                "fact": result.fact,
                "uuid": str(result.uuid),
                "valid_at": str(result.valid_at) if hasattr(result, 'valid_at') and result.valid_at else None
            }
            for result in raw_results
        ]

        return {
            "central_entity": entity_name,
            "related_facts": facts,
            "fact_count": len(facts),
            "search_method": "graphiti_semantic_search"
        }

    async def get_entity_timeline(
        self,
        entity_name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get temporal facts for an entity (e.g., history of treatments).

        Args:
            entity_name: Name of the entity
            start_date: Start of time range (not currently used)
            end_date: End of time range (not currently used)

        Returns:
            List of facts ordered by validity time (most recent first)

        Example:
            timeline = await client.get_entity_timeline("metformin")
            for fact in timeline:
                print(f"{fact['valid_at']}: {fact['fact']}")
        """
        if not self._initialized:
            await self.initialize()

        # Search for temporal information
        raw_results = await self.graphiti.search(f"timeline history of {entity_name}")

        timeline = [
            {
                "fact": result.fact,
                "uuid": str(result.uuid),
                "valid_at": str(result.valid_at) if hasattr(result, 'valid_at') and result.valid_at else None,
                "invalid_at": str(result.invalid_at) if hasattr(result, 'invalid_at') and result.invalid_at else None
            }
            for result in raw_results
        ]

        # Sort by valid_at (most recent first)
        timeline.sort(key=lambda x: x.get('valid_at') or '', reverse=True)

        return timeline

    async def get_graph_statistics(self) -> Dict[str, Any]:
        """
        Get basic statistics about the knowledge graph.

        Returns:
            Dict with:
            - graphiti_initialized: Whether Graphiti is ready
            - sample_search_results: Count of results from a test search
            - note: Additional information

        Note:
            For detailed statistics (node counts, relationship counts),
            direct Neo4j access would be required.

        Example:
            stats = await client.get_graph_statistics()
            print(f"Graph initialized: {stats['graphiti_initialized']}")
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Test search to verify graph is working
            test_results = await self.graphiti.search("test")
            return {
                "graphiti_initialized": True,
                "sample_search_results": len(test_results),
                "note": "Detailed statistics require direct Neo4j access"
            }
        except Exception as e:
            return {
                "graphiti_initialized": False,
                "error": str(e)
            }

    async def clear_graph(self):
        """
        Clear all data from the knowledge graph.

        **WARNING**: This permanently deletes all nodes and relationships.
        Use only for development/testing or when explicitly required.

        Example:
            # Only do this if you're sure!
            await client.clear_graph()
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Use Graphiti's clear_data function
            await clear_data(self.graphiti.driver)
            logger.warning("⚠️  Cleared all data from knowledge graph")
        except Exception as e:
            logger.error(f"Failed to clear graph using clear_data: {e}")

            # Fallback: Reinitialize (creates fresh indices)
            if self.graphiti:
                await self.graphiti.close()

            # Recreate clients
            llm_config = LLMConfig(
                api_key=self.llm_api_key,
                model=self.llm_choice,
                small_model=self.llm_choice,
                base_url=self.llm_base_url
            )

            llm_client = OpenAIClient(config=llm_config)

            embedder = OpenAIEmbedder(
                config=OpenAIEmbedderConfig(
                    api_key=self.embedding_api_key,
                    embedding_model=self.embedding_model,
                    embedding_dim=self.embedding_dimensions,
                    base_url=self.embedding_base_url
                )
            )

            self.graphiti = Graphiti(
                self.neo4j_uri,
                self.neo4j_user,
                self.neo4j_password,
                llm_client=llm_client,
                embedder=embedder,
                cross_encoder=OpenAIRerankerClient(client=llm_client, config=llm_config)
            )
            await self.graphiti.build_indices_and_constraints()

            logger.warning("Reinitialized Graphiti client (fresh indices created)")


# ============================================================================
# Global client instance and convenience functions
# ============================================================================

# Global Graphiti client instance
graph_client = GraphitiClient()


async def initialize_graph():
    """
    Initialize graph client.

    Call during application startup.
    """
    await graph_client.initialize()


async def close_graph():
    """
    Close graph client.

    Call during application shutdown.
    """
    await graph_client.close()


async def add_to_knowledge_graph(
    content: str,
    source: str,
    episode_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Add content to the knowledge graph.

    Convenience function for adding episodes.

    Args:
        content: Content to add
        source: Source description
        episode_id: Optional episode ID (auto-generated if not provided)
        metadata: Optional metadata

    Returns:
        Episode ID

    Example:
        episode_id = await add_to_knowledge_graph(
            content="대사증후군은 당뇨병, 고혈압, 비만의 복합 상태입니다.",
            source="guideline.pdf"
        )
    """
    if not episode_id:
        episode_id = f"episode_{datetime.now(timezone.utc).isoformat()}"

    await graph_client.add_episode(
        episode_id=episode_id,
        content=content,
        source=source,
        metadata=metadata
    )

    return episode_id


async def search_knowledge_graph(
    query: str,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Search the knowledge graph.

    Convenience function for semantic search.

    Args:
        query: Search query
        limit: Maximum number of results

    Returns:
        List of matching facts

    Example:
        results = await search_knowledge_graph("당뇨병 치료")
        for result in results:
            print(result['fact'])
    """
    return await graph_client.search(query, limit=limit)


async def get_entity_relationships(
    entity: str,
    depth: int = 2
) -> Dict[str, Any]:
    """
    Get relationships for an entity.

    Convenience function for relationship queries.

    Args:
        entity: Entity name
        depth: Maximum traversal depth (not used with Graphiti)

    Returns:
        Entity relationships

    Example:
        relations = await get_entity_relationships("인슐린")
        print(f"Found {relations['fact_count']} related facts")
    """
    return await graph_client.get_related_entities(entity, depth=depth)


async def test_graph_connection() -> bool:
    """
    Test graph database connection.

    Returns:
        True if connection successful, False otherwise

    Example:
        if await test_graph_connection():
            print("Knowledge graph is ready!")
    """
    try:
        await graph_client.initialize()
        stats = await graph_client.get_graph_statistics()
        logger.info(f"Graph connection successful. Stats: {stats}")
        return True
    except Exception as e:
        logger.error(f"Graph connection test failed: {e}")
        return False
