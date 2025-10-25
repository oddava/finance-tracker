LOCALES = bot/locales

al_revision:
	alembic revision --autogenerate -m "initial"
al_upg:
	alembic upgrade head


# I18N
babel-extract: ## Extracts translatable strings from the source code into a .pot file
	@uv run pybabel extract --input-dirs=. -o $(LOCALES)/messages.pot
.PHONY: locales-extract

babel-update: ## Updates .pot files by merging changed strings into the existing .pot files
	@uv run pybabel update -d $(LOCALES) -i $(LOCALES)/messages.pot
.PHONY: locales-update

babel-compile: ## Compiles translation .po files into binary .mo files
	@uv run pybabel compile -d $(LOCALES)
.PHONY: locales-compile

babel: extract update
#.PHONY: babel
