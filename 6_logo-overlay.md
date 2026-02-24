# Paso 6 — Logo Overlay

**Problema:** Sergio menciona empresas, productos y marcas en sus videos. Quiere que aparezca el logo en pantalla cuando los nombra. Hacerlo manualmente en DaVinci toma mucho tiempo.

**Solución:** Semi-automatizado. Leer la transcripción (Paso 5) → detectar marcas → generar `overlay-logos.md` → Sergio valida con ✅/❌ → aplicar overlays con ffmpeg en single pass.

**Prerequisito:** Paso 5 completado (`fuente/transcription/transcription_original.json` debe existir).

---

## Flujo completo

### 1. 🌑 Sinistra detecta marcas en la transcripción

Sinistra copia `transcription_limpia.md` → `overlay-logos.md`, luego busca marcas en `transcription_original.json` y agrega las detecciones debajo del segmento correspondiente.

**Proceso de detección:**

1. Abre `transcription_original.json`
2. Recorre el array `words[]` buscando nombres de marcas tech:
   ```python
   brands = ['openai', 'anthropic', 'claude', 'cloudy', 'chatgpt', 'gemini', 'openclaw', ...]
   for word in transcription['words']:
       if any(brand in word['word'].lower() for brand in brands):
           print(f"{word['start']} | {word['word']}")
   ```
3. Por cada marca encontrada, toma `word.start` como timestamp exacto
4. Agrega debajo del segmento en `overlay-logos.md`:
   ```
   → nombre.png | MM:SS.xx | ✅
   ```
5. Marca todas como ✅ por defecto — Sergio decide cuáles quitar
6. Pre-marca como ❌ repeticiones cercanas (ej: "Claude" 3 veces en 30s → solo primera ✅)

**Ejemplo:**

JSON (input):
```json
{ "word": "OpenAI", "start": 202.69, "end": 203.15 }
```

overlay-logos.md (output):
```
[3:22.11 - 3:44.25] (22.1s) OpenAI, los creadores de ChatGPT, confirmaron...
→ openai.png | 3:22.69 | ✅
```

El logo aparece 3 segundos desde el timestamp exacto de la palabra.

**¿Por qué no es un script?** Porque la detección requiere criterio: "Apple" puede ser empresa o fruta, "Meta" puede ser empresa o la palabra "meta". Sinistra usa contexto para decidir.

### 2. 🌑 Sinistra descarga logos al repo central

**Repo central:** `~/Documents/Edicion/Serudda/recursos/logos/`

Estructura por marca:
```
recursos/logos/
├── anthropic/
│   ├── anthropic.svg    ← fuente editable
│   └── anthropic.png    ← 512x512 RGBA (lo que usa el script)
├── openai/
│   ├── openai.svg
│   └── openai.png
└── ...
```

**Flujo para cada logo:**
1. ¿Existe en `recursos/logos/{brand}/{brand}.png`? → usar ese
2. Si no → buscar en **SVGL API** (`curl -sS "https://api.svgl.app?search=brand"`)
3. Si no → buscar en **Dashboard Icons** (`curl -sS "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/brand.png"`)
4. Si no → Sergio lo agrega manualmente

**Al descargar:** siempre guardar SVG + PNG (512x512 RGBA) en `recursos/logos/{brand}/`.

```bash
# Buscar en SVGL
curl -sS "https://api.svgl.app?search=anthropic"

# Descargar SVG
curl -sS "https://svgl.app/library/anthropic_white.svg" -o recursos/logos/anthropic/anthropic.svg

# Convertir SVG → PNG 512x512
rsvg-convert -w 512 -h 512 --keep-aspect-ratio recursos/logos/anthropic/anthropic.svg -o recursos/logos/anthropic/anthropic.png

# O descargar PNG directo de Dashboard Icons (ya viene 512x512)
curl -sS -o recursos/logos/openclaw/openclaw.png "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/openclaw.png"
```

**⚠️ No hay `fuente/logos/` por video.** Todo vive en el repo central compartido.

### 3. 🎬 Sergio revisa `fuente/transcription/overlay-logos.md`

Solo cambia ✅ ↔ ❌. Nada más.

**Formato nuevo (basado en transcription_limpia.md):**

```
[3:22.11 - 3:44.25] (22.1s) OpenAI, los creadores de ChatGPT, confirmaron...
→ openai.png | 3:22.69 | ✅
→ chatgpt.png | 3:24.01 | ❌

[3:44.25 - 3:58.57] (14.3s) Darío Amodei, el CEO de Antropic, dice...
→ anthropic.png | 3:52.15 | ✅
```

Cada marca tiene: `→ logo.png | timestamp_exacto | ✅/❌`
- El timestamp es el momento word-level en que se dice la marca
- El logo aparece 3 segundos desde ese timestamp

**Formato viejo (retrocompatible):**
```
[5:10 - 5:13] "contexto de la frase"
  → openai.png | ✅
```

El script acepta ambos formatos.

**Tips para la revisión:**

- Si una marca se menciona varias veces seguidas (ej: OpenAI 3 veces en 20 segundos), dejar solo la primera ✅ y las demás ❌
- Si el intro se repite (teleprompter), dejar solo una mención ✅
- 3 segundos por logo es el default — suficiente para que se vea sin molestar

### 4. 🎬 Sergio corre el script

```bash
# Ver qué va a hacer (sin generar video)
python3 scripts/logo-overlay.py $VIDEO --dry-run

# Solo ver el comando ffmpeg que generaría
python3 scripts/logo-overlay.py $VIDEO

# Generar el video (tarda ~10-20 min para 17 min de video)
python3 scripts/logo-overlay.py $VIDEO

# Personalizar
python3 scripts/logo-overlay.py $VIDEO --size 150 --padding 50
```

| Flag | Default | Qué hace |
|------|---------|----------|
| `--video` | `5_video_limpio.mp4` | Video de entrada |
| `--output` | `6_video_limpio_logos.mp4` | Video de salida |
| `--size` | 250 | Tamaño del logo en px |
| `--padding-x` | 160 | Padding horizontal en px |
| `--padding-y` | 80 | Padding vertical en px |
| `--fade` | 0.3 | Fade in/out en segundos |
| `--duration` | 3 | Duración del logo en pantalla (segundos) |
| `--crf` | 18 | Calidad de video |
| `--dry-run` | — | Solo muestra detecciones |

---

## Archivos involucrados

```
fuente/
├── transcription/
│   ├── transcription_original.json   ← INPUT (del Paso 5, NO tocar)
│   └── overlay-logos.md              ← Detecciones para revisión (✅/❌)
└── video/
    └── 5_video_limpio.mp4            ← Video de entrada

~/Documents/Edicion/Serudda/recursos/logos/   ← Repo central de logos (compartido)
├── anthropic/
│   ├── anthropic.svg
│   └── anthropic.png
├── openai/
│   ├── openai.svg
│   └── openai.png
└── ...

output/
└── 5_video_limpio_logos.mp4          ← Video con logos
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
- `overlay` con `enable='between(t,start,end)'` → solo visible en el rango
- Posición: esquina inferior derecha con padding
- Logos solapados en tiempo se apilan verticalmente
- **⚠️ NO usar `fade` con `alpha=1` en overlays encadenados** (ver nota abajo)

---

## Resolución de Logos (orden de prioridad)

1. **SVGL API** — `curl -sS "https://api.svgl.app?search=nombre"`
2. **Dashboard Icons** (jsDelivr CDN) — `curl -sS -o logo.png "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/nombre.png"` — +1000 logos tech, PNG 512x512 RGBA
3. **Repo local** — `~/Documents/Edicion/Serudda/recursos/logos/` (~120 marcas en slug)
4. **Manual** — Sergio lo busca y lo deja en `fuente/logos/`

---

## Lecciones aprendidas

1. **Timestamps por segmento son imprecisos.** Siempre usar word-level (Paso 5 ya lo hace).
2. **Batches no funcionan.** Single pass es la solución.
3. **3 segundos es la duración ideal.** 5s es demasiado largo.
4. **El logo aparece cuando se dice la palabra, no antes.**
5. **NO usar `fade` con `alpha=1` en overlays encadenados.** Ver nota importante abajo.

---

## ⚠️ NOTA IMPORTANTE: Fade + overlays encadenados = logos invisibles (Resuelto Feb 24, 2026)

### El problema
Usar `fade=t=in:st=...:d=0.3:alpha=1` y `fade=t=out:st=...:d=0.3:alpha=1` en los filtros de escala de cada logo **hace que los logos no aparezcan** cuando hay 2 o más overlays encadenados en el filter_complex. El video se re-encodea completo (tamaño normal, sin errores en ffmpeg) pero los logos son invisibles.

### Qué funciona y qué no

| Escenario | Resultado |
|-----------|-----------|
| 1 logo, clip corto, con fade | ✅ Funciona |
| 1 logo, video completo, sin fade | ✅ Funciona |
| 2 logos, video completo, con fade | ❌ Logos invisibles |
| 2 logos, video completo, sin fade | ✅ Funciona |
| 7 logos, video completo, sin fade | ✅ Funciona |

### Causa probable
El filtro `fade` con `alpha=1` aplicado sobre el stream del logo (antes del overlay) corrompe el canal alpha en overlays encadenados. Con 1 solo overlay no hay problema, pero al encadenar `[v0][s1]overlay...` el alpha corrupto se propaga y los logos posteriores (y a veces todos) se vuelven transparentes.

### Solución
**No usar fade en los logos.** Los logos aparecen y desaparecen de golpe — se ve bien en videos con cortes rápidos.

**Alternativa futura:** Si se necesita fade, investigar el enfoque de **capa transparente pre-compositeada**: generar un video RGBA separado con todos los logos (incluyendo fades), y hacer un solo overlay sobre el video original. Esto evita el encadenamiento problemático.

### Hipótesis descartadas durante el debugging
- ❌ Timestamps incorrectos — PTS empieza en 0, coincide con duración del video
- ❌ PTS descalibrado — `start_time: 0.000000`
- ❌ Logos PNG corruptos — funcionan en test de 1 logo
- ❌ Encadenamiento de overlays en sí — funciona sin fade
- ❌ Script Python vs bash directo — mismo resultado
- ❌ Comillas simples vs commas escapadas — mismo resultado

---

## Dependencias

- `ffmpeg` — overlays de video
- `rsvg-convert` — conversión SVG → PNG (`brew install librsvg`)
- `python3` — script de overlay
