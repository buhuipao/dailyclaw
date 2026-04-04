# DailyClaw build commands
# Version format: 1.0.0.YYYYMMDD.HHMM
VERSION := 1.0.0.$(shell date +%Y%m%d.%H%M)
IMAGE   := dailyclaw

.PHONY: help version build wheel docker docker-push clean test

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

version: ## Print current version
	@echo $(VERSION)

test: ## Run tests
	python -m pytest tests/ -v --tb=short

build: clean wheel docker ## Build wheel + Docker image

wheel: ## Build Python wheel (.whl)
	@echo "Building wheel $(VERSION)..."
	@sed -i.bak 's/^version = .*/version = "$(VERSION)"/' pyproject.toml && rm -f pyproject.toml.bak
	python -m build
	@git checkout pyproject.toml
	@echo "Built: dist/dailyclaw-$(VERSION)-py3-none-any.whl"

docker: ## Build Docker image (current platform)
	docker build -t $(IMAGE):$(VERSION) -t $(IMAGE):latest .
	@echo "Built: $(IMAGE):$(VERSION)"

docker-amd64: ## Build Docker image for linux/amd64 (deploy to Ubuntu)
	docker buildx build --platform linux/amd64 -t $(IMAGE):$(VERSION) -t $(IMAGE):latest --load .
	@echo "Built: $(IMAGE):$(VERSION) (linux/amd64)"

docker-push: ## Push Docker image (set REGISTRY first)
	@if [ -z "$(REGISTRY)" ]; then echo "Usage: make docker-push REGISTRY=your.registry.com/repo"; exit 1; fi
	docker tag $(IMAGE):$(VERSION) $(REGISTRY):$(VERSION)
	docker tag $(IMAGE):latest $(REGISTRY):latest
	docker push $(REGISTRY):$(VERSION)
	docker push $(REGISTRY):latest

clean: ## Clean build artifacts
	rm -rf dist/ build/ *.egg-info src/*.egg-info
