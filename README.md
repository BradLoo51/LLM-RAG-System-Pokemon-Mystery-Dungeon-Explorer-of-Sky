# LLM RAG System (Ollama & Postgres)

A LLM Pipeline where it respond to user about the information in Pokemon Mystery Dungeon: Explorer of Sky game. It utilizes memory persistence as well to bring forward some contexts on future prompts.

**Architecture:** Flask serves the dynamic frontend which queries the FASTAPI backend for the sessions saved in Postgres. The Postgres database will contained the embedding vectors of the information ingested to allow information retrieval. The backend will also be connected to the Ollama Pipeline to get the streaming response to the output.


## Step 1

`docker-compose.yml` contains the setup needed to initialize the Postgres database.

```bash
docker compose up -d
```

---

## Step 2

`ingest.py` is ran to ingest any `*.pdf` information stored in the `data` folder.

Run it with:
```bash
uv run python -m backend.database.ingest
```

---

## Step 3

`backend.py` will initialize the server running on uvicorn to receive RESTful requests.

Run it locally with:
```bash
uv run python -m backend.backend
```

---

## Step 4

`frontend.py` only serves the HTML page. It is hosting in `http://localhost:5000`

Run it locally with:
```bash
uv run python -m frontend.frontend
```

---

## Optional

`chat.py` allows chatting with the pipeline through the `cmd` instead.

Run it locally with:
```bash
uv run python -m backend.chat
```

