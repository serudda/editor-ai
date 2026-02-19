# Paso 6 — Logo Overlay

**Problema:** Sergio menciona empresas, productos y marcas en sus videos. Quiere que aparezca el logo en pantalla cuando los nombra. Hacerlo manualmente en DaVinci toma mucho tiempo.

**Solución:** Semi-automatizado. Leer la transcripción (Paso 5) → detectar marcas → generar `overlay-logos.md` → Sergio valida con ✅/❌ → aplicar overlays con ffmpeg en single pass.

**Prerequisito:** Paso 5 completado (`fuente/transcription/transcription_original.json` debe existir).

---

## Flujo completo

### 1. 🌑 Sinistra detecta marcas en la transcripción

Lee `transcription_original.json` (generado en Paso 5), busca menciones de marcas tech en las palabras con timestamps, y genera `fuente/transcription/overlay-logos.md`.

**NO vuelve a llamar a Whisper API.** La transcripción ya existe.

**Proceso de traducción (lo hace Sinistra manualmente, no un script):**

1. Abre `fuente/transcription/transcription_original.json`
2. Recorre el array `words[]` buscando nombres de marcas tech (OpenAI, Anthropic, Google, Claude, etc.)
3. Por cada marca encontrada, toma el `start` de esa palabra como timestamp exacto
4. Genera una entrada en `overlay-logos.md` con formato:
   ```
   [MM:SS - MM:SS] "contexto de la frase donde aparece la marca"
     → nombre-logo.png | ✅
   ```
   Donde el primer timestamp = `word.start` y el segundo = `word.start + 3s` (duración del logo)
5. Marca todas como ✅ por defecto — Sergio decide cuáles quitar

**Ejemplo concreto de la traducción:**

JSON (input):
```json
{ "word": "OpenAI", "start": 5.10, "end": 5.58 }
```

overlay-logos.md (output):
```
[0:05 - 0:08] "algo aún más fuerte OpenAI los creadores de ChatGPT"
  → openai.png | ✅
```

**¿Por qué no es un script?** Porque la detección de marcas requiere criterio: "Apple" puede ser la empresa o la fruta, "Meta" puede ser la empresa o la palabra "meta". Sinistra usa contexto de la frase para decidir. Un script regex tendría muchos falsos positivos.

### 2. 🌑 Sinistra descarga logos

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

### 3. 🎬 Sergio revisa `fuente/transcription/overlay-logos.md`

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

### 4. 🎬 Sergio corre el script

```bash
# Ver qué va a hacer (sin generar video)
python3 scripts/logo-overlay.py $VIDEO --dry-run

# Solo ver el comando ffmpeg que generaría
python3 scripts/logo-overlay.py $VIDEO --print-cmd

# Generar el video (tarda ~10-20 min para 17 min de video)
python3 scripts/logo-overlay.py $VIDEO

# Personalizar
python3 scripts/logo-overlay.py $VIDEO --size 150 --padding 50
```

| Flag | Default | Qué hace |
|------|---------|----------|
| `--video` | 4_video_jumpcut.mp4 | Video de entrada |
| `--output` | `<video>_logos.mp4` | Video de salida (en output/) |
| `--size` | 120 | Tamaño del logo en px |
| `--padding` | 40 | Padding del borde en px |
| `--fade` | 0.3 | Fade in/out en segundos |
| `--duration` | 3 | Duración del logo en pantalla (segundos) |
| `--crf` | 18 | Calidad de video |
| `--dry-run` | — | Solo muestra detecciones |
| `--print-cmd` | — | Solo imprime el comando ffmpeg |

---

## Archivos involucrados

```
fuente/
├── transcription/
│   ├── transcription_original.json   ← INPUT (del Paso 5, NO tocar)
│   └── overlay-logos.md              ← Detecciones para revisión (✅/❌)
├── logos/                            ← PNGs descargados
│   ├── anthropic.png
│   ├── openai.png
│   └── ...
└── video/
    └── 4_video_jumpcut.mp4           ← Video de entrada

output/
└── 4_video_jumpcut_logos.mp4         ← Video con logos
```

---

## Cómo funciona el script internamente

### Single pass (no batches)

El script genera UN SOLO comando ffmpeg con todos los overlays en el `filter_complex`. Cada logo es un input separado y se activa/desactiva con `enable='between(t,start,end)'`.

**¿Por qué single pass?** Probamos batches (dividir en múltiples passes) y los logos no aparecían en el video final. Single pass funciona correctamente.

### Parseo de `overlay-logos.md`

El script busca líneas con este formato:

```
[MM:SS - MM:SS] "cualquier texto"
  → nombre_logo.png | ✅
```

- Solo procesa las marcadas con ✅
- Detecta overlaps y apila logos verticalmente
- El nombre del logo debe coincidir con el archivo en `fuente/logos/`

### Overlays con ffmpeg

Cada logo se aplica con:

- `scale` → redimensiona al tamaño configurado
- `format=rgba` → preserva transparencia del PNG
- `fade` → fade in al inicio, fade out al final
- `overlay` con `enable='between(t,start,end)'` → solo visible en el rango
- Posición: esquina inferior derecha con padding
- Logos solapados en tiempo se apilan verticalmente

---

## Resolución de Logos (orden de prioridad)

1. **SVGL API** — `curl -sS "https://api.svgl.app?search=nombre"`
2. **Repo local** — `~/Documents/Edicion/Serudda/recursos/logos/` (~120 marcas en slug)
3. **Manual** — Sergio lo busca y lo deja en `fuente/logos/`

---

## Lecciones aprendidas

1. **Timestamps por segmento son imprecisos.** Siempre usar word-level (Paso 5 ya lo hace).
2. **Batches no funcionan.** Single pass es la solución.
3. **3 segundos es la duración ideal.** 5s es demasiado largo.
4. **El logo aparece cuando se dice la palabra, no antes.**

---

## 🐛 Bug abierto: Logos no aparecen en video completo (Feb 19, 2026)

### Síntoma
El script genera el video (re-encodea completo, ~7 min, ~766MB) pero los logos NO aparecen visualmente en ningún timestamp. ffmpeg reporta stream mapping correcto con todos los overlays.

### Lo que SÍ funciona
- **Clip corto (10s) con 1 logo** → logo visible ✅
- **Video completo con 1 logo, comando manual single-line** → logo visible ✅
  ```bash
  ffmpeg -i video.mp4 -i logo.png -filter_complex "[1:v]scale=...;[0:v][logo]overlay=...:enable='between(t,105,108)'[out]" -map "[out]" -map 0:a -c:v libx264 -crf 18 -preset fast -c:a copy -y output.mp4
  ```

### Lo que NO funciona
- **Video completo con 12 logos via `logo-overlay.py`** → logos no aparecen ❌
- Tanto con `subprocess.run(cmd_list)` como generando `.sh` + `bash script.sh`
- Tanto con `enable='between(t,105,108)'` (comillas simples) como `enable=between(t\,105\,108)` (commas escapadas)

### Hipótesis descartadas
- ❌ Timestamps incorrectos — transcripción coincide con duración del video (1030s ambos)
- ❌ PTS del video descalibrado — `start_time: 0.021` (normal)
- ❌ `-ss` reseteando timestamps — no se usa `-ss` en el script
- ❌ Logos PNG corruptos — funcionan en test de clip corto
- ❌ `\n` en filter_complex — eliminado, mismo resultado
- ❌ `capture_output=True` ocultando errores — removido, mismo resultado

### Hipótesis pendientes de investigar
- **¿El encadenamiento de 12 overlays causa el problema?** El test de 1 logo manual funciona. Nunca se probó correctamente un comando manual con 2+ logos en video completo (los intentos previos se pegaron multi-línea desde Telegram y podrían haberse corrompido).
- **¿Algo en el `.sh` generado vs el comando manual difiere sutilmente?** El `.sh` generado se ve idéntico al formato manual, pero no se ha probado corriendo el `.sh` manualmente con `bash`.
- **¿El video `4_video_jumpcut.mp4` tiene algo especial?** Fue creado concatenando 160 segmentos .ts. Los timestamps podrían tener discontinuidades internas que confunden el `enable=between()` en overlays encadenados.
- **¿Probar con `drawtext` como debug?** Poner un texto con timestamp visible en el video para confirmar qué valores tiene `t` en cada momento.

### Próximo paso sugerido
1. Probar corriendo `bash tmp/logo_overlay_cmd.sh` directamente en terminal (no via Python)
2. Si no funciona, probar con solo 2 logos (no 12) en un `.sh` manual
3. Si 2 logos no funcionan, probar `drawtext=text='%{pts}':fontsize=48` para ver timestamps reales del video

---

## Dependencias

- `ffmpeg` — overlays de video
- `rsvg-convert` — conversión SVG → PNG (`brew install librsvg`)
- `python3` — script de overlay
