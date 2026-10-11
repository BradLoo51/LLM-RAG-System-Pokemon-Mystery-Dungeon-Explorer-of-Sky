import hashlib
import psycopg
import pymupdf
from backend.config import settings
from langchain_postgres import PGVector
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pathlib import Path

CONN_SA = settings.CONN_SA
CONN_PG = settings.CONN_PG
EMBEDDING_MODEL = settings.EMBEDDING_MODEL
COLLECTION_NAME = settings.COLLECTION_NAME
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data"
BUF_SIZE = 65536 # Hashing the file in 64kb chunks to prevent memory issues with large files
BATCH = 64 # Batched the chunks before adding into the Postgres Table

def main():
    vector_store = PGVector(
        embeddings=OllamaEmbeddings(model=EMBEDDING_MODEL),
        collection_name=COLLECTION_NAME,
        connection=CONN_SA,
    )

    with psycopg.connect(CONN_PG, autocommit=True) as conn:
        documents = load_documents(conn)
        chunks = split_documents(documents)
        if chunks:
            for i in range(0, len(chunks), BATCH):
                vector_store.add_documents(chunks[i:i + BATCH])
                print(f"Added {min(i + BATCH, len(chunks))}/{len(chunks)} Chunks")
        else:
            print("Nothing New to Ingest.")


def file_hash(path: Path):
    sha256 = hashlib.sha256()

    with open(path, "rb") as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha256.update(data)

    return sha256.hexdigest()


def get_indexed(conn) -> dict[str, str]:
    """Return {source: file_hash} for files that are already in the DB."""

    rows = conn.execute(
        """
        SELECT DISTINCT e.cmetadata->>'source', e.cmetadata->>'file_hash'
        FROM langchain_pg_embedding e
        JOIN langchain_pg_collection c ON c.uuid = e.collection_id
        WHERE c.name = %s
        """,
        (COLLECTION_NAME,),
    ).fetchall()

    return {src: h for src, h in rows}


def delete_source(conn, source: str):
    conn.execute(
        """
        DELETE FROM langchain_pg_embedding AS e
        USING langchain_pg_collection AS c
        WHERE c.uuid = e.collection_id
          AND c.name = %s
          AND e.cmetadata->>'source' = %s
        """,
        (COLLECTION_NAME, source),
    )


def load_documents(conn):
    indexed = get_indexed(conn)
    documents = []

    for file_path in Path(DATA_PATH).rglob("*.pdf"):
        source = file_path.relative_to(DATA_PATH).as_posix()
        digest = file_hash(file_path)

        if indexed.get(source) == digest:
            print(f"Skip Source (Unchanged): {source}")
            continue

        if source in indexed:
            print(f"Changed, Re-indexing: {source}")
            delete_source(conn, source)

        with pymupdf.open(file_path) as pdf:
            for page_num, page in enumerate(pdf, start=1):
                text = page.get_text("text").strip()
                if not text:
                    print(f"Warning: No text on {file_path.name} Page {page_num}")
                    continue
                documents.append(Document(
                    page_content=text,
                    metadata={"source": source, "page": page_num, "file_hash": digest},
                ))

    return documents


def split_documents(documents: list[Document]):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
    )

    return text_splitter.split_documents(documents)


if __name__ == "__main__":
    main()