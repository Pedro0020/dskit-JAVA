package {{ base_package }};

import static org.junit.jupiter.api.Assertions.assertFalse;

import java.util.Set;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.core.env.Environment;
import org.springframework.test.context.ActiveProfiles;

/**
 * Gate de exposure (JAVA-014c): los endpoints sensibles de actuator NO pueden
 * quedar expuestos en el perfil base — es una familia real de CVEs (env, beans
 * y configprops filtran secretos; heapdump es una copia de memoria).
 *
 * Es la comprobación determinista que acompaña al agente `security`: si alguien
 * añade "env" o "*" a management.endpoints.web.exposure.include, este test
 * rompe `./mvnw verify` y la puerta del arnés no deja cerrar la feature.
 */
@SpringBootTest
@ActiveProfiles("test")
class ActuatorExposureTest {

    private static final Set<String> ENDPOINTS_SENSIBLES =
            Set.of("env", "beans", "configprops", "heapdump", "threaddump", "mappings", "conditions");

    @Autowired
    private Environment environment;

    @Test
    void noExponeEndpointsSensibles() {
        String include = environment.getProperty("management.endpoints.web.exposure.include", "");
        for (String endpoint : include.split(",")) {
            String limpio = endpoint.trim();
            assertFalse(
                    ENDPOINTS_SENSIBLES.contains(limpio),
                    "El endpoint de actuator '" + limpio + "' no puede exponerse en producción");
        }
    }
}
