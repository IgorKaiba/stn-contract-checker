.PHONY: install run test gate check

install:
	pip install -r requirements.txt

run:
	uvicorn app.main:app --reload

test:
	python -m pytest -q

gate:
	python scripts/gate.py

check: test gate
