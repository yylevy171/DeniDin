.PHONY: help test clean docker-build docker-run

help:
	@echo "morning-mcp-app Development Commands"
	@echo ""
	@echo "  make test         - Run pytest test suite"
	@echo "  make clean        - Remove Python cache files"
	@echo "  make docker-build - Build the morning-mcp-app Docker image"
	@echo "  make docker-run   - Run the morning-mcp-app Docker image"
	@echo ""

test:
	@echo "Running pytest..."
	python3 -m pytest tests/ -v --tb=short

clean:
	@echo "Cleaning Python cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

docker-build:
	docker build -t morning-mcp-app .

docker-run:
	docker run --rm -v "$(PWD)/config:/app/config:ro" morning-mcp-app
