# DailyClaw build commands
# Version format: 1.0.0.YYYYMMDD.HHMM
VERSION  := 1.0.0.$(shell date +%Y%m%d.%H%M)
IMAGE    := dailyclaw
REGISTRY := buhuipao/dailyclaw

.PHONY: help version build wheel docker docker-push push clean test

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

docker-save: ## Export Docker image to .tar.gz for offline deploy
	docker save $(IMAGE):latest | gzip > dist/$(IMAGE)-$(VERSION).tar.gz
	@echo "Saved: dist/$(IMAGE)-$(VERSION).tar.gz"

push: docker-amd64 ## Build amd64 + push to Docker Hub (buhuipao/dailyclaw)
	docker tag $(IMAGE):$(VERSION) $(REGISTRY):$(VERSION)
	docker tag $(IMAGE):latest $(REGISTRY):latest
	docker push $(REGISTRY):$(VERSION)
	docker push $(REGISTRY):latest
	@echo "Pushed: $(REGISTRY):$(VERSION) + latest"

docker-push: ## Push Docker image to custom registry: make docker-push REPO=your.registry.com/repo
	@if [ -z "$(REPO)" ]; then echo "Usage: make docker-push REPO=your.registry.com/repo"; exit 1; fi
	docker tag $(IMAGE):$(VERSION) $(REPO):$(VERSION)
	docker tag $(IMAGE):latest $(REPO):latest
	docker push $(REPO):$(VERSION)
	docker push $(REPO):latest

deploy: docker-amd64 docker-save ## Build amd64 image + export .tar.gz (offline deploy)

clean: ## Clean build artifacts
	rm -rf dist/ build/ *.egg-info src/*.egg-info
