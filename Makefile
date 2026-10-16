.PHONY: install doctor examples demo test integration e2e engine-up engine-down dashboard
PYTHON ?= .venv/bin/python
install:
	bash scripts/setup.sh
doctor:
	$(PYTHON) -m holo_desert doctor
examples:
	$(PYTHON) -m holo_desert examples
demo:
	$(PYTHON) -m holo_desert run e01_chat
dashboard:
	$(PYTHON) -m holo_desert dashboard
test:
	$(PYTHON) -m holo_desert test
integration:
	$(PYTHON) -m holo_desert test --integration
e2e:
	$(PYTHON) -m holo_desert test --end-to-end
engine-up:
	$(PYTHON) -m holo_desert engine up
engine-down:
	$(PYTHON) -m holo_desert engine down
