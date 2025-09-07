# -------- detect python and venv bin folder --------
PY := $(shell command -v python3 >/dev/null 2>&1 && echo python3 || echo python)

# Windows vs *nix bin folder
ifeq ($(OS),Windows_NT)
  VENV_BIN := .venv/Scripts
else
  VENV_BIN := .venv/bin
endif

PIP    := $(VENV_BIN)/pip
PYBIN  := $(VENV_BIN)/python
PRECOM := $(VENV_BIN)/pre-commit
RUFF   := $(VENV_BIN)/ruff
BLACK  := $(VENV_BIN)/black
NBQA   := $(VENV_BIN)/nbqa

.PHONY: help venv install hooks lint format nbformat test clean

help:
	@echo "make install  - create venv + install deps"
	@echo "make hooks    - install pre-commit hooks"
	@echo "make lint     - run ruff"
	@echo "make format   - ruff --fix + black"
	@echo "make nbformat - format notebooks via nbqa"
	@echo "make clean    - remove caches"

venv:
	$(PY) -m venv .venv

install: venv
	$(PIP) install -U pip
	$(PIP) install -r requirements.txt

hooks:
	$(PRECOM) install
	$(PRECOM) run --all-files

lint:
	$(RUFF) check .

format:
	$(RUFF) check --fix .
	$(RUFF) format .

nbformat:
	$(NBQA) ruff check --fix .
	$(NBQA) format .


clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

data:
	$(PYBIN) -m src.data.ingest --config config/settings.yaml

validate:
	$(PYBIN) scripts/validate_data.py

update:        # same as data for now
	$(PYBIN) -m src.data.ingest --config config/settings.yaml

rebuild:       # wipe processed & rebuild from raw, does not fetch new data
	rm -f data/processed/*.parquet
	$(PYBIN) -m src.data.ingest --config config/settings.yaml
