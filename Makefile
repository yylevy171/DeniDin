.PHONY: help lint test clean

help:
	@echo "DeniDin Development Commands"
	@echo ""
	@echo "  make lint       - Run pylint on source code"
	@echo "  make test       - Run pytest test suite"
	@echo "  make clean      - Remove Python cache files"
	@echo "  make all        - Run lint and test"
	@echo ""

lint:
	@echo "Running pylint..."
	cd denidin-app && python3 -m pylint src/ \
		--fail-under=7.0 \
		--disable=C0303,C0305,R0914,R0917,R0912,R0915,W0611,W0707,W0719,C0411,W1514,C0325,W1309,C0301,W0612 \
		--max-line-length=120

test:
	@echo "Running pytest..."
	cd denidin-app && python3 -m pytest tests/ -v --tb=short

clean:
	@echo "Cleaning Python cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

all: lint test
