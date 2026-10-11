import psycopg
import uuid
from backend.config import settings
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_postgres import PGVector, PostgresChatMessageHistory

CONN_SA = settings.CONN_SA
CONN_PG = settings.CONN_PG
EMBEDDING_MODEL = settings.EMBEDDING_MODEL
COLLECTION_NAME = settings.COLLECTION_NAME
CHAT_MODEL = settings.CHAT_MODEL
HISTORY_TABLE = "chat_history"
HISTORY_MESSAGES = 12
TOP_K = 4

vector_store = PGVector(
    embeddings=OllamaEmbeddings(model=EMBEDDING_MODEL),
    collection_name=COLLECTION_NAME,
    connection=CONN_SA,
)

retriever = vector_store.as_retriever(search_kwargs={"k": TOP_K})
llm = ChatOllama(model=CHAT_MODEL)

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "Answer using the context below. If the answer is not in the context, say so. Use the conversation history to resolve any follow-up questions."),
        MessagesPlaceholder(variable_name="history", optional=True),
        ("human", "{question}"),
    ]
)
chain = prompt | llm | StrOutputParser()


def main():
    session_id = str(uuid.uuid4())

    with psycopg.connect(CONN_PG, autocommit=True) as conn:
        PostgresChatMessageHistory.create_tables(conn, HISTORY_TABLE)
        history = PostgresChatMessageHistory(HISTORY_TABLE, session_id, sync_connection=conn)

        while True:
            question = input("\nUser> ").strip()
            if question in ("exit()", "quit()"):
                break
            answer(history, question)


def format_documents(docs):
    return "\n\n".join(
        f"[{d.metadata.get('source')} p.{d.metadata.get('page')}]\n{d.page_content}"
        for d in docs
    )

def answer(history, question):
    documents = retriever.invoke(question)
    context = format_documents(documents)
    past = history.messages[-HISTORY_MESSAGES:]

    reply = ""
    for token in chain.stream({"context": context, "history": past, "question": question}):
        print(token, end="", flush=True)
        reply += token
    print()

    sources = sorted({f"{d.metadata.get('source')} pg.{d.metadata.get('page')}" for d in documents})
    print("\nSources:", ", ".join(sources))

    history.add_user_message(question)
    history.add_ai_message(reply)

if __name__ == "__main__":
    main()