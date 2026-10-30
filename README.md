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

### Ejecutar Auditor en Vivo (Sesión Real o Archivo Específico)

AAME auto-detecta las sesiones reales de Antigravity en el sistema:

```bash
python src/aame/demo.py
```

O especificando una ruta concreta a cualquier archivo `transcript.jsonl`:

```bash
python src/aame/demo.py /ruta/a/brain/<session_id>/.system_generated/logs/transcript.jsonl
```

---

## 4. Próximos Pasos (Roadmap Fase 2)

- [ ] Implementar generador de checkpoints `HANDOFF.md` (*Save Game*).
- [ ] Desarrollar CLI headless con `Typer` (`aame inspect`, `aame squash`).
- [ ] Exportador de contexto limpio al portapapeles o archivo `@seed_context`.
