import logging

from app.core.database import get_connection, release_connection

logger = logging.getLogger("llm_qa")


async def create_questions_table():
    """Create the questions table if it doesn't exist."""
    conn = await get_connection()
    try:
        # Enable UUID extension
        await conn.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
        
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                status VARCHAR(50) DEFAULT 'success',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create index on created_at for efficient history retrieval
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_questions_created_at 
            ON questions(created_at DESC)
        """)
        
        logger.info("Questions table created or already exists with UUID primary key and index")
    finally:
        await release_connection(conn)


async def save_question(question: str, answer: str, status: str = "success"):
    """Save a question and its answer to the database."""
    conn = await get_connection()
    try:
        await conn.execute(
            """
            INSERT INTO questions (question, answer, status)
            VALUES ($1, $2, $3)
            """,
            question,
            answer,
            status,
        )
        logger.info("Question saved to database")
    finally:
        await release_connection(conn)


async def get_all_questions(limit: int = 100):
    """Get all questions from the database."""
    conn = await get_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT id, question, answer, status, created_at
            FROM questions
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
        return [
            {
                "id": row["id"],
                "question": row["question"],
                "answer": row["answer"],
                "status": row["status"],
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ]
    finally:
        await release_connection(conn)
