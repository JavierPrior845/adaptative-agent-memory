# Adaptive Agent Memory Engine (AAME) - Fase 1: Core Engine & Token Analyzer

Motor determinista y desacoplado para la auditoría de contexto, análisis de KV-Cache y optimización del ciclo de vida de la memoria en arneses de agentes de IA (Google Antigravity, Claude Code, Cursor, Cline).

---

## 1. Arquitectura de la Fase 1

La Fase 1 implementa el núcleo fundacional del motor siguiendo principios de diseño modular, alta cohesión y bajo acoplamiento:

```
adaptative-agent-memory/
├── pyproject.toml              # Definición estándar PEP 621 con Hatchling y dependencias
├── README.md                   # Documentación técnica de arquitectura y uso
├── src/
│   └── aame/
│       ├── __init__.py         # Exportaciones del API público
│       ├── core/
│       │   ├── __init__.py
│       │   ├── models.py       # Modelos Pydantic v2 (UnifiedMessage, UnifiedSession, NoiseReport)
│       │   ├── tokenizer.py    # Contador local con tiktoken y comparador de prefijos KV-Cache
│       │   ├── analyzer.py     # Motor heurístico de ruido (tool churn, errores transitorios, side-quests)
│       │   └── cache.py        # Simulador de estabilidad y tasas de acierto de Prefix Caching
│       ├── adapters/
│       │   ├── __init__.py
│       │   ├── base.py         # Clase base abstracta HarnessAdapter (streaming JSONL resiliente)
│       │   └── antigravity.py  # Adaptador para Antigravity IDE (brain/.../transcript.jsonl)
│       ├── utils/
│       │   ├── __init__.py
│       │   └── paths.py        # Resolución multiplataforma (Linux, macOS, Windows)
│       └── demo.py             # CLI de auditoría en vivo para probar sesiones reales o sintéticas
└── tests/
    ├── __init__.py
    ├── conftest.py             # Fixtures para sesiones unificadas y transcripciones sintéticas
    ├── test_models.py          # Validación y métricas computadas de modelos Pydantic
    ├── test_tokenizer.py       # Tests de conteo de tokens y matching de prefijos
    ├── test_cache.py           # Tests de análisis de retención de KV-Cache
    ├── test_analyzer.py        # Tests de clasificación heurística y detección de ruido
    └── test_antigravity_adapter.py # Tests de streaming resiliente y parsing de Antigravity
```

---

## 2. Decisiones Técnicas y Buenas Prácticas

1. **Desacoplamiento Estricto de Arneses (`HarnessAdapter`):**
   - El modelo interno de AAME no depende del esquema JSON específico de ningún proveedor.
   - `AntigravityAdapter` mapea los tipos de pasos (`USER_INPUT`, `PLANNER_RESPONSE`, `RUN_COMMAND`, `VIEW_FILE`, etc.) a roles estándar (`USER`, `ASSISTANT`, `TOOL`, `SYSTEM`) y categorías semánticas.
   - Permite añadir en el futuro `ClaudeCodeAdapter` o `CursorAdapter` sin tocar una sola línea del analizador ni de la interfaz.

2. **Coste 0 y Operación Local:**
   - La tokenización se realiza 100% en local usando `tiktoken` (`cl100k_base` / `o200k_base`), con un estimador heurístico determinista de respaldo si no hay conexión a internet.
   - No se requiere ninguna API Key ni llamadas de red de pago para auditar sesiones o detectar bloques de ruido.

3. **La Paradoja de la KV-Cache (Prefix Caching):**
   - `KVCacheAnalyzer` y `TokenCounter.common_prefix_tokens` miden la estabilidad del prefijo acumulado entre turnos.
   - Evita la trampa de los middlewares que modifican mensajes intermedios en caliente, lo cual invalidaría el prefijo de la KV-cache y aumentaría la latencia y el coste.

4. **Clasificación Heurística y Reglas de Podado:**
   - **`ARCHITECTURE`**: Decisiones técnicas, directrices y reglas permanentes (protegidas, nunca podables).
   - **`USER_INSTRUCTION`**: Peticiones directas del usuario (protegidas).
   - **`TOOL_OUTPUT` / `MASSIVE_TOOL_OUTPUT`**: Salidas de terminal masivas (> 800 tokens, cat/view_file enteros, listas gigantes) marcadas automáticamente para *squash*.
   - **`TRANSIENT_ERROR_RESOLVED`**: Errores y fallos de compilación resueltos en turnos posteriores marcados como podables.
   - **`SIDE_QUEST`**: Explicaciones pedagógicas teóricas sin impacto en el código identificadas y descartables para el contexto operativo.

---

## 3. Instalación y Uso

### Configurar Entorno Virtual (con `uv`)

```bash
cd adaptative-agent-memory
uv venv
source .venv/bin/activate
uv pip install -e .
uv pip install pytest
```

### Ejecutar Suite de Tests

```bash
pytest
```
*23 tests unitarios cubren modelos, tokenizador, analizador de ruido, caché y adaptador de Antigravity.*

### Ejecutar CLI Headless (`aame`)

El paquete incluye el ejecutable de terminal `aame`:

```bash
# 1. Listar sesiones descubiertas en el sistema
aame sessions --limit 5

# 2. Auditar el consumo y ruido de la sesión activa
aame inspect

# 3. Auditar una sesión específica por ID o ruta
aame inspect <session_id>

# 4. Iniciar el Cockpit Interactivo TUI (Textual)
aame cockpit

# 5. Abrir el Cockpit en una sesión específica
aame cockpit <session_id>

# 6. Generar un Context Handoff (Save Game) a HANDOFF.md para abrir un chat limpio
aame squash

# 7. Imprimir el checkpoint directamente por pantalla
aame squash --print
```

---

## 4. Cockpit Interactivo de Terminal (`aame cockpit`)

Inspirado en herramientas modernas como Claude Code y Lazygit, el Cockpit TUI implementa las directrices de `modern-tui-craft`:

* **Sidebar Lateral**: Explorador en tiempo real de sesiones descubiertas en el sistema.
* **Banner de Métricas & KV-Cache**: Barras de progreso fluidas usando caracteres Unicode fraccionarios (`█`, `▆`, `▅`, `▄`, `▎`, `▏`), cálculo del ratio de ruido y estimación de prefijo estable.
* **Tabla de Turnos Interactiva**:
  * Visualización por categorías con código de colores semánticos (Arquitectura, Herramientas, Errores, Side-Quests).
  * `[Espacio]`: Alterna individualmente si un paso se conserva (`✔`) o se poda (`✖`).
  * `[P]`: Aplica automáticamente las heurísticas para podar todo el ruido y salidas de herramientas masivas.
  * `[S]`: Genera el archivo `HANDOFF.md` instantáneamente con feedback visual no invasivo (`notify`).
* **Panel de Inspección**: Muestra el contenido crudo, argumentos de herramientas o códigos de salida del paso seleccionado.

---

## 5. Próximos Pasos (Roadmap Fase 4)

- [ ] Adaptador para **Claude Code** (`~/.claude/`).
- [ ] Gestor de reglas y hechos persistentes a nivel repositorio (`.agents/memory/project.json`).
- [ ] Pruebas en Windows y Linux.
