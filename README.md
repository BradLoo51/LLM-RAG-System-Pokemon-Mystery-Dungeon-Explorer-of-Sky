# LLM RAG System (Ollama & Postgres)

A LLM Pipeline where it respond to user about the information in Pokemon Mystery Dungeon: Explorer of Sky game. It utilizes memory persistence as well to bring forward some contexts on future prompts.

**Architecture:** Flask serves the dynamic frontend which queries the FASTAPI backend for the sessions saved in Postgres. The Postgres database will contained the embedding vectors of the information ingested to allow information retrieval. The backend will also be connected to the Ollama Pipeline to get the streaming response to the output.

<img width="1884" height="941" alt="FrontEnd Preview" src="https://github.com/user-attachments/assets/248ff2a3-7fa1-48b3-be00-342961a7f91b" />

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

<img width="1081" height="354" alt="Terminal Chat Preview" src="https://github.com/user-attachments/assets/1f905bd4-e2bf-4c8e-925e-1416457b0d83" />
