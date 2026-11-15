# Targets namespaced for adoption into an existing Java project.
DSKIT_MVN = {% if build_tool == 'maven' %}./mvnw{% else %}./gradlew{% endif %}
DSKIT_AGENTS = uv run --no-project python -m agents

.PHONY: dskit-init dskit-test dskit-eval dskit-backlog

dskit-init:
	@./init.sh

dskit-test:
{% if build_tool == 'maven' %}
	@$(DSKIT_MVN) verify
{% else %}
	@$(DSKIT_MVN) build
{% endif %}

dskit-eval:
	@$(DSKIT_AGENTS).evals.runner --harness --contracts

dskit-backlog:
	@$(DSKIT_AGENTS) --json run harness status
