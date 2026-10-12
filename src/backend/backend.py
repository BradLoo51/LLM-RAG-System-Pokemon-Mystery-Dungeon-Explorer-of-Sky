import json
import uuid
from contextlib import asynccontextmanager
import psycopg
import uvicorn
from backend.config import settings
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_postgres import PGVector, PostgresChatMessageHistory
from pydantic import BaseModel

CONN_SA = settings.CONN_SA
CONN_PG = settings.CONN_PG
EMBEDDING_MODEL = settings.EMBEDDING_MODEL
COLLECTION_NAME = settings.COLLECTION_NAME
CHAT_MODEL = settings.CHAT_MODEL
HISTORY_TABLE = "chat_history"
HISTORY_MESSAGES = 4
TOP_K = 4


# ---------- RAG Setup ----------
vector_store = PGVector(
    embeddings=OllamaEmbeddings(model=EMBEDDING_MODEL),
    collection_name=COLLECTION_NAME,
    connection=CONN_SA,
)
retriever = vector_store.as_retriever(search_kwargs={"k": TOP_K})
llm = ChatOllama(model=CHAT_MODEL)

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "Answer using the context below. If the answer is not in the context, say so. Use the conversation history to resolve any follow-up questions.\n\n CONTEXT:\n{context}"),
        MessagesPlaceholder(variable_name="history", optional=True),
        ("human", "{question}"),
    ]
)
chain = prompt | llm | StrOutputParser()


def format_docs(docs):
    return "\n\n".join(
        f"[{d.metadata.get('source')} p.{d.metadata.get('page')}]\n{d.page_content}"
        for d in docs
    )


# ---------- Database Helpers ----------
def db():
    return psycopg.connect(CONN_PG, autocommit=True)


def init_db():
    """Create the history table (LangChain) and our own sessions table (sidebar list)."""
    with db() as conn:
        PostgresChatMessageHistory.create_tables(conn, HISTORY_TABLE)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id         UUID PRIMARY KEY,
                title      TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )


def session_exists(conn, sid: str) -> bool:
    return conn.execute("SELECT 1 FROM chat_sessions WHERE id = %s", (sid,)).fetchone() is not None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateSession(BaseModel):
    title: str = "New chat"


class ChatRequest(BaseModel):
    message: str


# ---------- Sessions API ----------
@app.get("/api/sessions")
def list_sessions():
    with db() as conn:
        rows = conn.execute(
            "SELECT id, title FROM chat_sessions ORDER BY updated_at DESC"
        ).fetchall()
    return [{"id": str(r[0]), "title": r[1]} for r in rows]


@app.post("/api/sessions")
def create_session(body: CreateSession):
    title = body.title.strip()[:60] or "New chat"
    sid = str(uuid.uuid4())
    with db() as conn:
        conn.execute("INSERT INTO chat_sessions (id, title) VALUES (%s, %s)", (sid, title))
    return {"id": sid, "title": title}


@app.get("/api/sessions/{sid}/messages")
def get_messages(sid: uuid.UUID):
    sid = str(sid)
    with db() as conn:
        if not session_exists(conn, sid):
            raise HTTPException(404, "Session not found")
        history = PostgresChatMessageHistory(HISTORY_TABLE, sid, sync_connection=conn)
        messages = history.messages
    return [
        {"role": "user" if m.type == "human" else "assistant", "content": m.content}
        for m in messages
    ]


@app.delete("/api/sessions/{sid}")
def delete_session(sid: uuid.UUID):
    sid = str(sid)
    with db() as conn:
        history = PostgresChatMessageHistory(HISTORY_TABLE, sid, sync_connection=conn)
        history.clear()
        conn.execute("DELETE FROM chat_sessions WHERE id = %s", (sid,))
    return Response(status_code=204)


# ---------- Chat (Streamed) ----------
def stream_chat(sid: str, question: str):
    """Yield newline-delimited JSON: {"t": token} ... {"sources": [...]} or {"error": "..."}."""
    with db() as conn:
        history = PostgresChatMessageHistory(HISTORY_TABLE, sid, sync_connection=conn)
        try:
            docs = retriever.invoke(question)
            context = format_docs(docs)
            past = history.messages[-HISTORY_MESSAGES:]

            reply = ""
            for token in chain.stream({"context": context, "history": past, "question": question}):
                reply += token
                yield json.dumps({"t": token}) + "\n"

            # sources = sorted({f"{d.metadata.get('source')} p.{d.metadata.get('page')}" for d in docs})
            # yield json.dumps({"sources": sources}) + "\n"

            history.add_user_message(question)
            history.add_ai_message(reply)
            conn.execute("UPDATE chat_sessions SET updated_at = now() WHERE id = %s", (sid,))
        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"


@app.post("/api/sessions/{sid}/chat")
def chat(sid: uuid.UUID, body: ChatRequest):
    sid = str(sid)
    question = body.message.strip()
    if not question:
        raise HTTPException(400, "Empty message")
    with db() as conn:
        if not session_exists(conn, sid):
            raise HTTPException(404, "Session not found")
    return StreamingResponse(stream_chat(sid, question), media_type="application/x-ndjson")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)