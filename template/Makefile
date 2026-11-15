# Makefile Java — fachada fina sobre ./mvnw (D6 del spec JAVA: cero logica propia)
.PHONY: help setup init test verify check compile lint format security typecheck mutation audit crap \
        migrations batch-run context-check index-rag knowledge clean \
        agents-list agents-doctor agents-eval backlog prompts-sync prompts-check \
        skills assistants-sync

MVNW = {% if build_tool == 'maven' %}./mvnw{% else %}./gradlew{% endif %}
AGENTS = uv run --no-project python -m agents

help:
	@echo ""
	@echo "  {{ project_name }} — Java ({{ framework }}, Java {{ java_version }})"
	@echo ""
	@echo "  Build ({{ build_tool }})"
	@echo "    make setup          resuelve dependencias"
	@echo "    make compile        compila"
	@echo "    make test           ejecuta los tests"
	@echo "    make verify         build completo + cobertura"
	@echo "    make check          verify + puerta del arnes"
	@echo "    make clean          limpia el build"
	@echo ""
	@echo "  Calidad"
	@echo "    make lint           Spotless check"
	@echo "    make format         Spotless apply"
	@echo "    make typecheck      Error Prone + NullAway (-Ptypecheck)"
	@echo "    make mutation       PIT sobre una clase (make mutation TARGET=com.ejemplo.Servicio)"
	@echo "    make security       Trivy fs + SBOM cyclonedx"
	@echo "    make audit          PMD CPD (duplicacion)"
	@echo "    make crap           CRAP de una clase (make crap TARGET=src/.../Servicio.java)"
	@echo "    make migrations     estado de las migraciones"
	@echo "    make batch-run      ejecuta un job (make batch-run JOB=demoJob)"
	@echo "    make context-check  smoke del ApplicationContext"
	@echo "    make index-rag      indexa el proyecto en el RAG"
	@echo "    make knowledge      regenera el vault estructural (docs/vault/)"
	@echo ""
	@echo "  Arnes"
	@echo "    make init           ./init.sh — la puerta"
	@echo "    make backlog        estado de harness/featureslist.json"
	@echo "    make agents-list    agentes del plano de control"
	@echo "    make agents-doctor  diagnostico del arnes"
	@echo "    make agents-eval    harness + contracts + smoke"
	@echo "    make prompts-sync   regenera prompts desde codigo y contratos"
	@echo "    make prompts-check  falla si un prompt se desincronizo"
	@echo "    make skills         instala prompts como skills en .opencode/skills/"
	@echo "    make assistants-sync espeja subagentes a .claude/agents/"
	@echo ""

setup:
{% if build_tool == 'maven' %}
	@$(MVNW) -q dependency:go-offline
{% else %}
	@$(MVNW) -q dependencies
{% endif %}

init:
	@./init.sh

test:
	@$(MVNW) test

verify:
{% if build_tool == 'maven' %}
	@$(MVNW) verify
{% else %}
	@$(MVNW) -q build
{% endif %}

check: verify
	@./init.sh

compile:
{% if build_tool == 'maven' %}
	@$(MVNW) -q compile
{% else %}
	@$(MVNW) -q compileJava
{% endif %}

lint:
{% if build_tool == 'maven' %}
	@$(MVNW) -q spotless:check
	@$(MVNW) -q org.apache.maven.plugins:maven-pmd-plugin:3.25.0:check
{% else %}
	@$(MVNW) -q spotlessCheck
{% endif %}

format:
{% if build_tool == 'maven' %}
	@$(MVNW) -q spotless:apply
{% else %}
	@$(MVNW) -q spotlessApply
{% endif %}

typecheck:
{% if build_tool == 'maven' %}
	@$(MVNW) -q compile -Ptypecheck
{% else %}
	@echo "  (typecheck Error Prone/NullAway en Gradle llega en la fase 2 de JAVA-001b)"
{% endif %}

mutation:
{% if build_tool == 'maven' %}
	@test -n "$(TARGET)" || (echo "  usa: make mutation TARGET=com.ejemplo.Servicio" && exit 1)
	@$(MVNW) org.pitest:pitest-maven:1.17.0:mutationCoverage \
		-DtargetClasses=$(TARGET) -DoutputFormats=XML,HTML
{% else %}
	@echo "  (PIT en Gradle llega en la fase 2 de JAVA-001b)"
{% endif %}

security:
	@command -v trivy >/dev/null 2>&1 && \
		trivy fs --severity HIGH,CRITICAL --exit-code 0 . || \
		echo "  (trivy no instalado — https://github.com/aquasecurity/trivy)"
{% if build_tool == 'maven' %}
	@$(MVNW) -q org.cyclonedx:cyclonedx-maven-plugin:2.9.1:makeAggregateBom || true
	@echo "  SBOM en target/ (bom.json)"
{% else %}
	@echo "  (SBOM cyclonedx en Gradle llega en la fase 2 de JAVA-001b)"
{% endif %}

audit:
{% if build_tool == 'maven' %}
	@$(MVNW) -q org.apache.maven.plugins:maven-pmd-plugin:3.25.0:cpd-check || true
{% else %}
	@echo "  (CPD en Gradle llega en la fase 2 de JAVA-001b)"
{% endif %}

crap:
	@test -n "$(TARGET)" || (echo "  usa: make crap TARGET=src/main/java/<paquete>/<Clase>.java" && exit 1)
	@$(AGENTS) --json run mutation crap_report --target $(TARGET)

migrations:
	@$(AGENTS) --json run migrations status

batch-run:
	@test -n "$(JOB)" || (echo "  usa: make batch-run JOB=demoJob" && exit 1)
{% if build_tool == 'maven' %}
	@$(MVNW) spring-boot:run "-Dspring-boot.run.arguments=--spring.batch.job.name=$(JOB) --spring.main.web-application-type=none"
{% else %}
	@$(MVNW) -q bootRun --args="--spring.batch.job.name=$(JOB) --spring.main.web-application-type=none"
{% endif %}

context-check:
{% if build_tool == 'maven' %}
	@$(MVNW) -q test -Dtest=ApplicationTests
{% else %}
	@$(MVNW) -q test --tests '*ApplicationTests'
{% endif %}

index-rag:
	@$(AGENTS) --json run rag index

knowledge:
	@$(AGENTS) --json run architecture build_vault
{% if use_graphify %}

knowledge-graph:
	@$(AGENTS) --json run architecture enrich_graphify
{% endif %}

clean:
	@$(MVNW) clean

agents-list:
	@$(AGENTS) list

agents-doctor:
	@$(AGENTS) doctor

agents-eval:
	@PYTHONUTF8=1 $(AGENTS).evals.runner --harness --contracts

backlog:
	@$(AGENTS) --json run harness status

prompts-sync assistants-sync:
	@$(AGENTS).prompts_sync --write

prompts-check:
	@$(AGENTS).prompts_sync

skills:
	@mkdir -p .opencode/skills
	@for skill in agents/prompts/*.md; do \
		name=$$(basename "$$skill" .md); \
		cp "$$skill" ".opencode/skills/$$name.md"; \
		echo "   skill: $$name"; \
	done
	@echo "   Skills instaladas en .opencode/skills/."
