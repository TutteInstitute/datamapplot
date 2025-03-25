# Testing Makefile for datamapplot

PYTHON_INTERPRETER = python3
PACKAGE_NAME = datamapplot

.PHONY: test
## Run all tests
test: test-static test-ui
	@echo "All tests run"

.PHONY: test-static
## Run python based backend and static frontend tests
test-static:
	pytest --mpl --cov=datamapplot/ --cov-report html:test-results/coverage.html --mpl-generate-summary=html --mpl-results-path=test-results

.PHONY: test-backend
## Run python based backend tests
test-backend:
	pytest --cov=datamapplot/ --cov-report html:test-results/coverage.html

.PHONY: test-ui
## Run interactive frontend tests
test-ui:
	cd datamapplot/interactive_tests && npx playwright test

.PHONY: test-ui-fast
## Run interactive frontend tests, not slow tests
test-ui-fast:
	cd datamapplot/interactive_tests && npx playwright test --grep-invert @slow

.PHONY: update-static-baseline
## Update static baseline images
update-static-baseline:
	pytest --mpl --mpl-generate-path=datamapplot/tests/baseline

.PHONY: report-static
## Open the mpl static test report
report-static:
	@echo "Serving test-results/fig_comparison.html at http://localhost:8000"
	@$(PYTHON_INTERPRETER) -m http.server --directory test-results 8000 &
	@sleep 1 && open http://localhost:8000/fig_comparison.html

.PHONY: report-interactive
## Open the playwright test report
report-interactive:
	cd datamapplot/interactive_tests && npx playwright show-report

#################################################################################
# Self Documenting Commands                                                     #
#################################################################################

HELP_VARS := PACKAGE_NAME

.DEFAULT_GOAL := show-help
.PHONY: show-help
show-help:
	@$(PYTHON_INTERPRETER) scripts/help.py $(foreach v,$(HELP_VARS),-v $(v) $($(v))) $(MAKEFILE_LIST)