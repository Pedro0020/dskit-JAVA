from pathlib import Path

from tools.adopt import ProjectFacts, answers, detect


def test_detect_maven_batch(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text(
        """
        <project><properties><java.version>21</java.version></properties>
        <dependencies>
          <artifactId>spring-boot-starter-batch</artifactId>
          <artifactId>postgresql</artifactId><artifactId>flyway-core</artifactId>
        </dependencies></project>
        """,
        encoding="utf-8",
    )
    source = tmp_path / "src/main/java/com/acme/orders"
    source.mkdir(parents=True)
    (source / "Application.java").write_text("package com.acme.orders;\n", encoding="utf-8")

    assert detect(tmp_path) == ProjectFacts(
        build_tool="maven",
        java_version="21",
        base_package="com.acme.orders",
        framework="spring-boot-batch",
        db="postgres",
        migrations="flyway",
    )


def test_detect_gradle_web_and_batch(tmp_path: Path) -> None:
    (tmp_path / "build.gradle").write_text(
        "sourceCompatibility = '17'\n"
        "implementation 'org.springframework.boot:spring-boot-starter-web'\n"
        "implementation 'org.springframework.boot:spring-boot-starter-batch'\n",
        encoding="utf-8",
    )
    source = tmp_path / "src/main/java/com/acme/api"
    source.mkdir(parents=True)
    (source / "Application.java").write_text("package com.acme.api;\n", encoding="utf-8")

    facts = detect(tmp_path)
    assert facts.build_tool == "gradle"
    assert facts.java_version == "17"
    assert facts.framework == "spring-boot-web+batch"
    assert facts.base_package == "com.acme.api"


def test_answers_requires_ambiguous_values() -> None:
    try:
        answers(ProjectFacts(), {})
    except ValueError as exc:
        assert "build_tool" in str(exc)
    else:
        raise AssertionError("ambiguous project must require explicit overrides")
