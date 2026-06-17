.PHONY: setup dev backend frontend test smoke up

setup:
	python -m venv backend/.venv
	backend/.venv/bin/python -m pip install -r backend/requirements.txt
	npm --prefix frontend install
	cp -n backend/.env.example backend/.env || true

backend:
	backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --port 8000

frontend:
	npm --prefix frontend run dev

dev:
	backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --port 8000 & npm --prefix frontend run dev

test:
	backend/.venv/bin/python -m pytest backend/tests

smoke:
	backend/.venv/bin/python backend/scripts/smoke.py

up:
	docker compose up --build
