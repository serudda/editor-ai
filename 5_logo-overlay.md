# Logo Overlay — Detectar marcas y superponer logos

**Problema:** Sergio menciona empresas, productos y marcas en sus videos. Quiere que aparezca el logo en pantalla cuando los nombra. Hacerlo manualmente en DaVinci toma mucho tiempo.

**Solución:** Semi-automatizado. Transcribir con timestamps por palabra → detectar marcas → generar archivo de revisión → Sergio valida con ✅/❌ → aplicar overlays con ffmpeg en single pass.

---

## Flujo completo

### 1. Sinistra transcribe y detecta marcas

Sinistra transcribe el video con Whisper API usando **word-level timestamps** (no segmentos). Esto es clave — el logo aparece exactamente cuando se dice la palabra, no al inicio del segmento.

```bash
# Extraer audio comprimido (Whisper tiene límite de 25MB)
ffmpeg -i 4_video_jumpcut.mp4 -vn -c:a libopus -b:a 48k -y tmp/audio_whisper.ogg

# Transcribir con timestamps por palabra
curl -sS https://api.openai.com/v1/audio/transcriptions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -F "file=@tmp/audio_whisper.ogg" \
  -F "model=whisper-1" \
  -F "response_format=verbose_json" \
  -F "language=es" \
  -F "timestamp_granularities[]=word" \
  > tmp/transcription_words.json
```

**⚠️ IMPORTANTE:** Usar `timestamp_granularities[]=word`, NO `segment`. La diferencia es de varios segundos de precisión.

### 2. Sinistra descarga logos

Los logos se buscan en este orden:

1. **SVGL API** (automático, +500 logos tech con variantes light/dark)
2. **Repo local** (`~/Documents/Edicion/Serudda/recursos/logos/`)
3. **Sergio lo agrega manualmente**

Los logos descargados se guardan en `fuente/logos/` dentro del folder del video.

```bash
# Buscar en SVGL
curl -sS "https://api.svgl.app?search=anthropic"

# Descargar SVG y convertir a PNG 256x256
curl -sS "https://svgl.app/library/anthropic_white.svg" -o fuente/logos/anthropic.svg
rsvg-convert -w 256 -h 256 --keep-aspect-ratio fuente/logos/anthropic.svg -o fuente/logos/anthropic.png
```

### 3. Sergio revisa `fuente/transcripcion/logo-overlay.md`

Solo cambia ✅ ↔ ❌. Nada más.

```
[5:10 - 5:13] "algo aún más fuerte OpenAI los creadores de ChatGPT"
  → openai.png | ✅

[5:12 - 5:15] "OpenAI los creadores de ChatGPT confirmaron en su documentación"
  → chatgpt.png | ❌
```

**Tips para la revisión:**

- Si una marca se menciona varias veces seguidas (ej: OpenAI 3 veces en 20 segundos), dejar solo la primera ✅ y las demás ❌
- Si el intro se repite (teleprompter), dejar solo una mención ✅
- 3 segundos por logo es el default — suficiente para que se vea sin molestar

### 4. Sergio corre el script

```bash
# Ver qué va a hacer (sin generar video)
python3 ~/Documents/Projects/editor-ai/scripts/logo-overlay.py ~/ruta/al/folder --dry-run

# Solo ver el comando ffmpeg que generaría
python3 ~/Documents/Projects/editor-ai/scripts/logo-overlay.py ~/ruta/al/folder --print-cmd

# Generar el video (tarda ~10-20 min para 17 min de video)
python3 ~/Documents/Projects/editor-ai/scripts/logo-overlay.py ~/ruta/al/folder-fuente-video

# Con video diferente
python3 ~/Documents/Projects/editor-ai/scripts/logo-overlay.py ~/ruta/al/folder-fuente-video --video 4_video_jumpcut.mp4

# Personalizar
python3 ~/Documents/Projects/editor-ai/scripts/logo-overlay.py ~/ruta/al/folder-fuente-video --size 150 --padding 50
```

| Flag          | Default             | Qué hace                                 |
| ------------- | ------------------- | ---------------------------------------- |
| `--video`     | 4_video_jumpcut.mp4 | Video de entrada                         |
| `--output`    | `<video>_logos.mp4` | Video de salida                          |
| `--size`      | 120                 | Tamaño del logo en px                    |
| `--padding`   | 40                  | Padding del borde en px                  |
| `--fade`      | 0.3                 | Fade in/out en segundos                  |
| `--duration`  | 3                   | Duración del logo en pantalla (segundos) |
| `--crf`       | 18                  | Calidad de video                         |
| `--preset`    | fast                | Preset de encoding                       |
| `--dry-run`   | —                   | Solo muestra detecciones                 |
| `--print-cmd` | —                   | Solo imprime el comando ffmpeg           |

---

## Estructura de archivos por video

Todo lo relacionado al proceso vive dentro del folder del video:

```
2026-02-11_mejor-epoca-para-ti/
├── fuente/
│   ├── audio/
│   └── video/
├── tmp/                            ← Temporales del proceso
│   ├── logos/                      ← PNGs descargados (SVGL o local)
│   │   ├── anthropic.png
│   │   ├── openai.png
│   │   └── ...
│   ├── audio_whisper.ogg           ← Audio comprimido para Whisper
│   └── transcription_words.json    ← Transcripción con timestamps por palabra
├── logo-overlay.md                 ← Detecciones para revisión (✅/❌)
├── 4_video_jumpcut.mp4            ← Input
└── video_jumpcut_v1_logos.mp4      ← Output con logos
```

Para limpiar temporales: `rm -rf tmp/` dentro del folder del video.

---

## Cómo funciona el script internamente

### Single pass (no batches)

El script genera UN SOLO comando ffmpeg con todos los overlays en el `filter_complex`. Cada logo es un input separado y se activa/desactiva con `enable='between(t,start,end)'`.

**¿Por qué single pass?** Probamos batches (dividir en 4 passes de 4 overlays) y los logos no aparecían en el video final. El single pass funciona correctamente — cada overlay tiene sus timestamps absolutos y ffmpeg los aplica todos en una pasada.

**Trade-off RAM:** Con muchos overlays (20+), ffmpeg necesita más RAM. En Apple Silicon M1/M2 con 16GB no debería haber problema. Si se muere, reducir la cantidad de logos aprobados (✅).

### Parseo de `fuente/transcripcion/logo-overlay.md`

El script busca líneas con este formato:

```
[MM:SS - MM:SS] "cualquier texto"
  → nombre_logo.png | ✅
```

- Solo procesa las marcadas con ✅
- Detecta overlaps automáticamente y apila logos verticalmente (stack_level)
- El nombre del logo debe coincidir con el archivo en `fuente/logos/`

### Overlays con ffmpeg

Cada logo se aplica con:

- `scale` → redimensiona al tamaño configurado
- `format=rgba` → preserva transparencia del PNG
- `fade` → fade in al inicio, fade out al final (alpha-based)
- `overlay` con `enable='between(t,start,end)'` → solo visible en el rango de tiempo
- Posición default: esquina inferior derecha con padding configurable
- Logos que se solapan en tiempo se apilan verticalmente (uno encima del otro)

---

## Resolución de Logos (orden de prioridad)

### 1. SVGL API (primera opción — automático)

```bash
curl -sS "https://api.svgl.app?search=anthropic"
# route.light → logo para fondo claro (logo oscuro)
# route.dark  → logo para fondo oscuro (logo claro)
```

### 2. Repo local (fallback)

`~/Documents/Edicion/Serudda/recursos/logos/` (~120 marcas en formato slug)

### 3. Sergio lo agrega (último recurso)

Si no está en ningún lado, Sergio lo busca y lo deja en `fuente/logos/` del video.

---

## Lecciones aprendidas

1. **Timestamps por segmento son imprecisos.** Un segmento de Whisper puede empezar varios segundos antes de la palabra de la marca. Siempre usar `timestamp_granularities[]=word`.

2. **Batches no funcionan.** Al dividir en múltiples passes, los logos no aparecen en el video final. Causa probable: re-encoding entre passes afecta los timestamps. Single pass es la solución.

3. **3 segundos es la duración ideal.** 5 segundos se siente demasiado largo. 3 segundos es suficiente para que se vea sin molestar.

4. **El logo debe aparecer cuando se dice la palabra, no antes.** La precisión a nivel de palabra hace la diferencia entre "profesional" y "raro".

---

## Dependencias

- `ffmpeg` — overlays de video
- `curl` + OpenAI API — transcripción con Whisper (lo corre Sinistra)
- `rsvg-convert` — conversión SVG → PNG (`brew install librsvg`)
- `python3` — script de overlay
