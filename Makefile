.PHONY: test ci

test:
	uv run --with pytest --with PyYAML==6.0.2 python -m pytest tests gitrelease/tests whip/tests museum-catalog/scripts/test_museum_catalog.py $(PYTEST_ARGS)
	uv run --with pytest --with PyYAML==6.0.2 python -m pytest plugins/tyemirov/skills/gitrelease/tests plugins/tyemirov/skills/whip/tests plugins/tyemirov/skills/museum-catalog/scripts/test_museum_catalog.py $(PYTEST_ARGS)

ci: test
