"""Session management API endpoints."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor


router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


def get_db_connection():
    """Get PostgreSQL database connection."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return psycopg2.connect(database_url)


class CreateSessionRequest(BaseModel):
    patient_id: str
    user_id: str
    metadata: Optional[Dict[str, Any]] = {}


class SaveMessageRequest(BaseModel):
    session_id: str
    role: str  # "user", "assistant", "system"
    content: str
    metadata: Optional[Dict[str, Any]] = {}


class SessionResponse(BaseModel):
    session_id: str
    created_at: str


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    metadata: Dict[str, Any]
    created_at: str


@router.post("", response_model=SessionResponse)
def create_session(request: CreateSessionRequest):
    """Create a new consultation session."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        session_id = str(uuid.uuid4())

        # Merge patient_id into metadata
        merged_metadata = {
            "patient_id": request.patient_id,
            **request.metadata,
        }

        cursor.execute(
            """
            INSERT INTO sessions (id, user_id, metadata, created_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id, created_at
            """,
            (session_id, request.user_id, json.dumps(merged_metadata)),
        )

        result = cursor.fetchone()
        conn.commit()

        return SessionResponse(
            session_id=result["id"],
            created_at=result["created_at"].isoformat(),
        )
    except Exception as e:
        logging.exception("Error creating session: %s", e)
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")
    finally:
        conn.close()


@router.post("/messages")
def save_message(request: SaveMessageRequest):
    """Save a message to a session."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO messages (session_id, role, content, metadata, created_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            """,
            (
                request.session_id,
                request.role,
                request.content,
                json.dumps(request.metadata),
            ),
        )

        conn.commit()
        return {"status": "saved", "session_id": request.session_id}
    except Exception as e:
        logging.exception("Error saving message: %s", e)
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save message: {str(e)}")
    finally:
        conn.close()


@router.get("/{session_id}/messages")
def get_session_messages(session_id: str):
    """Get all messages for a session."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            """
            SELECT id, role, content, metadata, created_at
            FROM messages
            WHERE session_id = %s
            ORDER BY created_at ASC
            """,
            (session_id,),
        )

        messages = cursor.fetchall()

        return {
            "session_id": session_id,
            "messages": [
                MessageResponse(
                    id=msg["id"],
                    role=msg["role"],
                    content=msg["content"],
                    metadata=msg["metadata"] if msg["metadata"] else {},
                    created_at=msg["created_at"].isoformat(),
                )
                for msg in messages
            ],
        }
    except Exception as e:
        logging.exception("Error fetching messages: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch messages: {str(e)}")
    finally:
        conn.close()


@router.get("/{session_id}")
def get_session(session_id: str):
    """Get session details."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            """
            SELECT id, user_id, metadata, created_at
            FROM sessions
            WHERE id = %s
            """,
            (session_id,),
        )

        session = cursor.fetchone()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return {
            "session_id": session["id"],
            "user_id": session["user_id"],
            "metadata": session["metadata"] if session["metadata"] else {},
            "created_at": session["created_at"].isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error fetching session: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch session: {str(e)}")
    finally:
        conn.close()


@router.post("/{session_id}/summary")
def generate_session_summary(session_id: str):
    """Generate consultation summary using LLM."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Fetch all messages for the session
        cursor.execute(
            """
            SELECT role, content, created_at
            FROM messages
            WHERE session_id = %s
            ORDER BY created_at ASC
            """,
            (session_id,),
        )

        messages = cursor.fetchall()

        if not messages:
            return {"summary": "상담 기록이 없습니다."}

        # Build conversation text
        conversation_lines = []
        for msg in messages:
            role_label = "상담사" if msg["role"] == "user" else "시스템"
            conversation_lines.append(f"{role_label}: {msg['content']}")

        conversation_text = "\n".join(conversation_lines)

        # Generate summary using LLM
        from ..providers import get_main_llm

        llm = get_main_llm()

        summary_prompt = f"""다음은 대사증후군 환자와의 상담 내용입니다. 이를 요약해주세요.

{conversation_text}

다음 형식으로 작성해주세요:

## 주요 논의 주제
- (3-5개의 bullet points)

## 제공된 권장사항
- (3-5개의 bullet points)

## 다음 상담 시 확인 사항
- (2-3개의 bullet points)

## 상담사 메모
- (특이사항이나 주의사항)
"""

        response = llm.invoke(summary_prompt)
        summary = response.content if hasattr(response, "content") else str(response)

        # Save summary to session metadata
        cursor.execute(
            """
            UPDATE sessions
            SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
            WHERE id = %s
            """,
            (json.dumps({"summary": summary, "summary_generated_at": datetime.now().isoformat()}), session_id),
        )

        conn.commit()

        return {
            "session_id": session_id,
            "summary": summary,
            "generated_at": datetime.now().isoformat(),
        }
    except Exception as e:
        logging.exception("Error generating summary: %s", e)
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")
    finally:
        conn.close()
