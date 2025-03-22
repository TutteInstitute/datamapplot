# Testing Makefile for datamapplot

PYTHON_INTERPRETER = python3
PACKAGE_NAME = datamapplot

.PHONY: test
## Run all tests
test: test-static test-ui
	echo "All tests run"

.PHONY: test-fast-no-static
## Run backend tests and fast frontend tests. Leaves out static frontend tests.
test-fast-no-static: test-backend test-ui-fast
	echo "All fast tests run"

.PHONY: test-static
## Run python based backend and static frontend tests
test-static:
	pytest --mpl --cov=datamapplot/ --cov-report=html --mpl-generate-summary=html

.PHONY: test-backend
## Run python based backend tests
test-backend:
	pytest --cov=datamapplot/ --cov-report=html

.PHONY: test-ui
## Run interactive frontend tests
test-ui:
	cd datamapplot/interactive_tests && npx playwright test

.PHONY: test-ui-fast
## Run interactive frontend tests, not slow tests
test-ui-fast:
	cd datamapplot/interactive_tests && npx playwright test --grep-invert @slow

.PHONY: update-static-baseline
## Update visual baseline images
update-static-baseline:
	pytest --mpl --mpl-generate-path=datamapplot/tests/baseline

.PHONY: report-playwright
## Open the playwright report
report-playwright:
	cd datamapplot/interactive_tests && npx playwright show-report

#################################################################################
# Self Documenting Commands                                                     #
#################################################################################

HELP_VARS := PACKAGE_NAME

.DEFAULT_GOAL := show-help
.PHONY: show-help
show-help:
	@$(PYTHON_INTERPRETER) scripts/help.py $(foreach v,$(HELP_VARS),-v $(v) $($(v))) $(MAKEFILE_LIST)