package {{ base_package }};

import static com.tngtech.archunit.library.Architectures.layeredArchitecture;

import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

/**
 * Límites de capas del proyecto (JAVA-010): Controller -> Service -> Repository.
 * Un controller que importa un repository directamente hace fallar este test —
 * es la violación canónica que el agente `architecture` detecta y que la
 * puerta `./mvnw verify` bloquea en CI.
 *
 * `allowEmptyShould(true)`: un proyecto recién generado aún no tiene capas
 * service/repository — el test tolera capas vacías para no bloquear el
 * arranque, y empieza a morder en cuanto la primera clase cae en una capa.
 */
@AnalyzeClasses(packages = "{{ base_package }}")
public class ArchitectureTest {

    @ArchTest
    static final ArchRule capas = layeredArchitecture()
            .consideringAllDependencies()
            .layer("Controller")
            .definedBy("..controller..")
            .layer("Service")
            .definedBy("..service..")
            .layer("Repository")
            .definedBy("..repository..")
            .whereLayer("Controller")
            .mayNotBeAccessedByAnyLayer()
            .whereLayer("Service")
            .mayOnlyBeAccessedByLayers("Controller")
            .whereLayer("Repository")
            .mayOnlyBeAccessedByLayers("Service")
            .allowEmptyShould(true);

    @ArchTest
    static final ArchRule sin_ciclos = com.tngtech.archunit.library.dependencies.SlicesRuleDefinition.slices()
            .matching("{{ base_package }}.(*)..")
            .should()
            .beFreeOfCycles();
}
