# Editor AI — Pipeline de Edición Automatizada

Pipeline de edición de video para el canal de Serudda. Cada paso está documentado por separado y los scripts ejecutables viven en `scripts/`.

**Regla:** Todo lo temporal vive en `tmp/` dentro del folder del video. Nada va a `/tmp/` del sistema.

## Estructura del proyecto

```
editor-ai/
├── README.md                          ← Estás aquí
├── 1_sincronizar-audio-y-video.md     ← Paso 1
├── 2_reducir-ruido-visual.md          ← Paso 2
├── 3_color-grade-cinematografico.md   ← Paso 3
├── 4_eliminar-silencios.md            ← Paso 4
├── 5_generar-transcripcion.md                 ← Paso 5
├── 6_logo-overlay.md                  ← Paso 6
├── 7_media-overlay.md                 ← Paso 7
├── 8_text-overlay.md                  ← Paso 8
├── 9_inserts.md                       ← Paso 9
└── scripts/
    ├── sync-audio.py                  ← Script Paso 1
    ├── denoise.py                     ← Script Paso 2
    ├── color-grade.py                 ← Script Paso 3
    ├── jump-cut.py                    ← Script Paso 4
    ├── transcribe.py                  ← Script Paso 5
    ├── logo-overlay.py               ← Script Paso 6
    ├── media-overlay.py              ← Script Paso 7
    ├── text-overlay.py               ← Script Paso 8
    └── inserts.py                    ← Script Paso 9
```

## Estructura de cada video

Los videos viven en: `~/Documents/Edicion/Serudda/serudda-videos/`

```
YYYY-MM-DD_nombre-del-video/
├── README.md                               ← Info del video
├── fuente/                                 ← Todo lo del pipeline (intermedios)
│   ├── audio/                              ← Audio original + procesado
│   │   ├── 0_audio_original.mkv                       ← Original OBS (SM7B)
│   │   ├── 1_audio_extraido.aac              ← Paso 1: audio puro
│   │   └── 1_audio_stereo.wav                ← Paso 1: mono → estéreo
│   ├── video/                              ← Video original + cada paso
│   │   ├── 0_video_original.MP4              ← Original cámara (Sony A6400)
│   │   ├── 1_video_sincronizado.mp4          ← Paso 1: video + audio SM7B
│   │   ├── 2_video_denoised.mp4              ← Paso 2: ruido visual reducido
│   │   ├── 3_video_color_grade.mp4           ← Paso 3: color cinematográfico
│   │   └── 4_video_jumpcut.mp4               ← Paso 4: silencios eliminados
│   ├── transcription/                      ← Transcripciones y overlays
│   │   ├── transcription_original.json     ← Paso 5: Whisper word-level (FUENTE DE VERDAD, no tocar)
│   │   ├── transcription_limpia.md         ← Paso 5: Versión legible (BASE para todos los overlays)
│   │   ├── overlay-logos.md                ← Paso 6: Copia de limpia + detecciones de logos (✅/❌)
│   │   ├── overlay-media.md               ← Paso 7: Copia de limpia + media overlays fullscreen (>>>)
│   │   ├── overlay-text.md                 ← Paso 8: Copia de limpia + marcas de text cards (>>>)
│   │   └── overlay-inserts.md             ← Paso 9: Copia de limpia + inserciones de clips (>>>)
│   ├── overlays/                           ← Imágenes/videos que van ENCIMA (Paso 7)
│   │   ├── ai-timeline.png
│   │   └── demo.mp4
│   ├── inserts/                            ← Clips que CORTAN el video (Paso 9)
│   │   └── sam-altman.mp4
│   └── logos/                              ← Logos descargados para este video
│       ├── openai.png
│       └── ...
├── output/                                 ← Videos finales para publicar
│   └── video_final.mp4                     ← El que se sube a YouTube
└── tmp/                                    ← Pruebas y basura (borrable)
    └── jc_segments/                        ← Segmentos del jump cut
```

**¿Qué va dónde?**

- **`fuente/`** → intermedios del pipeline. Cada paso genera un archivo aquí.
- **`output/`** → lo que sale de la carpeta. El video listo para YouTube.
- **`tmp/`** → pruebas, test clips, basura. Se puede borrar con `rm -rf tmp/`.

**Recursos compartidos:** `~/Documents/Edicion/Serudda/recursos/logos/` (~120 marcas en slug). Fallback cuando SVGL no tiene un logo.

---

## Pipeline — Checklist de Edición

> **Cómo usar:** Abre este README cada vez que edites un video. Sigue los pasos en orden.
> Los pasos marcados 🌑 los hace Sinistra. Los marcados 🎬 los hace Sergio.
> Reemplaza `$VIDEO` con la ruta de tu carpeta de video.

```
$VIDEO = ~/Documents/Edicion/Serudda/serudda-videos/YYYY-MM-DD_nombre-del-video
```

---

### Paso 1 — Sincronizar Audio y Video

**Doc:** [1_sincronizar-audio-y-video.md](1_sincronizar-audio-y-video.md) · **Script:** [`scripts/sync-audio.py`](scripts/sync-audio.py)

Combina el audio del SM7B (OBS) con el video de la cámara (Sony A6400).

- [ ] 🌑 **Sinistra** corre el script:
  ```bash
  python3 scripts/sync-audio.py $VIDEO
  ```
- [ ] 🎬 **Sergio** revisa `fuente/video/1_video_sincronizado.mp4` — ¿labios y audio están sincronizados?

**Flags útiles:**

| Flag              | Default              | Qué hace                              |
| ----------------- | -------------------- | ------------------------------------- |
| `--video-file`    | 0_video_original.MP4 | Nombre del video de cámara            |
| `--audio-file`    | 0_audio_original.mkv | Nombre del audio OBS                  |
| `--sony-start`    | 30                   | Segundo de inicio para chunk de Sony  |
| `--sony-duration` | 60                   | Duración del chunk de Sony            |
| `--dry-run`       | —                    | Solo detectar offset, no genera video |

---

### Paso 2 — Reducir Ruido Visual

**Doc:** [2_reducir-ruido-visual.md](2_reducir-ruido-visual.md) · **Script:** [`scripts/denoise.py`](scripts/denoise.py)

Reduce ruido/grano con denoising temporal (hqdn3d).

- [ ] 🌑 **Sinistra** corre el script:
  ```bash
  python3 scripts/denoise.py $VIDEO
  ```
- [ ] 🎬 **Sergio** revisa `fuente/video/2_video_denoised.mp4` — ¿se ve más limpio sin perder detalle?

**Flags útiles:**

| Flag         | Default                  | Qué hace                            |
| ------------ | ------------------------ | ----------------------------------- |
| `--input`    | 1_video_sincronizado.mp4 | Video de entrada                    |
| `--strength` | medium                   | Preset: light / medium / heavy      |
| `--custom`   | —                        | Valores custom hqdn3d (ej: 5:5:6:6) |

---

### Paso 3 — Color Grade Cinematográfico

**Doc:** [3_color-grade-cinematografico.md](3_color-grade-cinematografico.md) · **Script:** [`scripts/color-grade.py`](scripts/color-grade.py)

Aplica tono cálido + look cinematográfico por capas.

- [ ] 🌑 **Sinistra** corre el script:
  ```bash
  python3 scripts/color-grade.py $VIDEO
  ```
- [ ] 🎬 **Sergio** revisa `fuente/video/3_video_color_grade.mp4` — ¿el color se ve bien?

**Flags útiles:**

| Flag            | Default              | Qué hace                       |
| --------------- | -------------------- | ------------------------------ |
| `--input`       | 2_video_denoised.mp4 | Video de entrada               |
| `--warmth`      | 0.05                 | Calidez en midtonos (0.0-0.10) |
| `--saturation`  | 1.1                  | Saturación global              |
| `--no-vignette` | —                    | Desactivar viñeta              |

---

### Paso 4 — Eliminar Silencios (Jump Cuts)

**Doc:** [4_eliminar-silencios.md](4_eliminar-silencios.md) · **Script:** [`scripts/jump-cut.py`](scripts/jump-cut.py)

Detecta silencios del teleprompter y los corta automáticamente. ⚠️ Tarda varios minutos en videos largos.

- [ ] 🎬 **Sergio** corre el script (tarda >7 min en videos largos):
  ```bash
  python3 scripts/jump-cut.py $VIDEO/fuente/video/3_video_color_grade.mp4 --padding 0.5
  ```
- [ ] 🎬 **Sergio** revisa `fuente/video/4_video_jumpcut.mp4` — ¿los cortes se sienten naturales?

**Tip:** Usa `--dry-run` primero para ver cuántos silencios detecta y cuánto tiempo ahorra.

**Flags útiles:**

| Flag            | Default | Qué hace                                   |
| --------------- | ------- | ------------------------------------------ |
| `--padding`     | 0.3     | Segundos de "aire" antes/después del corte |
| `--min-silence` | 1.5     | Solo cortar silencios mayores a N segundos |
| `--noise`       | -30     | Threshold de silencio en dB                |
| `--dry-run`     | —       | Solo muestra stats, no genera video        |

---

### Paso 5 — Transcripción

**Doc:** [5_generar-transcripcion.md](5_generar-transcripcion.md) · **Script:** [`scripts/transcribe.py`](scripts/transcribe.py)

Genera la transcripción cruda con timestamps a nivel de palabra. Es la **fuente de verdad** para todos los overlays.

- [ ] 🌑 **Sinistra** corre el script:
  ```bash
  python3 scripts/transcribe.py $VIDEO
  ```
- [ ] 🌑 **Sinistra** confirma que `fuente/transcription/transcription_original.json` tiene words + segments
- [ ] 🌑 **Sinistra** confirma que `fuente/transcription/transcription_limpia.md` se generó (se crea automáticamente)
  - Este archivo es la **base para todos los overlays** (text, logos, broll, images)
  - Si necesitás regenerarla sin re-transcribir: `python3 scripts/transcribe.py $VIDEO --clean-only`

**Flags útiles:**

| Flag           | Default             | Qué hace                                                  |
| -------------- | ------------------- | --------------------------------------------------------- |
| `--input`      | 4_video_jumpcut.mp4 | Video de entrada                                          |
| `--language`   | es                  | Idioma del audio                                          |
| `--audio-only` | —                   | Solo extraer audio, no transcribir                        |
| `--clean-only` | —                   | Solo regenerar `transcription_limpia.md` desde JSON existente |
| `--dry-run`    | —                   | Muestra qué haría sin ejecutar                            |

---

### Paso 6 — Logo Overlay

**Doc:** [6_logo-overlay.md](6_logo-overlay.md) · **Script:** [`scripts/logo-overlay.py`](scripts/logo-overlay.py)

Detecta marcas mencionadas en la transcripción y superpone sus logos.

- [ ] 🌑 **Sinistra** crea `overlay-logos.md` copiando `transcription_limpia.md` (si no existe)
- [ ] 🌑 **Sinistra** detecta marcas en la transcripción y agrega debajo de cada segmento:
  ```
  → nombre.png | MM:SS.xx | ✅
  ```
  (timestamp exacto word-level de cuando se menciona la marca)
- [ ] 🌑 **Sinistra** descarga logos (SVGL API → Dashboard Icons → repo local → manual)
- [ ] 🎬 **Sergio** revisa `overlay-logos.md` y cambia ✅/❌ en cada detección
  - Quitar repeticiones (ej: si dice "OpenAI" 5 veces en 30s, dejar solo la primera)
  - Quitar falsos positivos
- [ ] 🌑 **Sinistra** confirma que todos los logos ✅ están en `fuente/logos/` como PNG
- [ ] 🎬 **Sergio** corre el render (tarda ~10-20 min):
  ```bash
  python3 scripts/logo-overlay.py $VIDEO
  ```
- [ ] 🎬 **Sergio** revisa el video final en `output/` — ¿los logos aparecen en el momento correcto?

**Flags útiles:**

| Flag          | Default             | Qué hace                       |
| ------------- | ------------------- | ------------------------------ |
| `--video`     | 4_video_jumpcut.mp4 | Video de entrada               |
| `--size`      | 120                 | Tamaño del logo en px          |
| `--padding`   | 40                  | Padding del borde en px        |
| `--fade`      | 0.3                 | Fade in/out en segundos        |
| `--dry-run`   | —                   | Solo muestra detecciones       |

---

### Paso 7 — Media Overlay

**Doc:** [7_media-overlay.md](7_media-overlay.md) · **Script:** [`scripts/media-overlay.py`](scripts/media-overlay.py)

Superpone imágenes o videos fullscreen mientras tu voz sigue sonando. Infografías, screenshots, demos — el visual reemplaza la cámara pero el audio no se interrumpe.

- [ ] 🌑 **Sinistra** corre dry-run — si `overlay-media.md` no existe, se copia automáticamente de `transcription_limpia.md`:
  ```bash
  python3 scripts/media-overlay.py $VIDEO --dry-run
  ```
- [ ] 🎬 **Sergio** abre `overlay-media.md` y marca medios con `>>>`:
  ```markdown
  [4:37.35 - 4:57.15] (19.8s) en 2022 la IA no podía hacer una multiplicación...
  >>> ai-timeline.png | @"multiplicación" | 19s
  ```
  - Archivos en `fuente/overlays/`
  - `@"palabra"` = aparece cuando se dice esa palabra
  - Duración opcional (`5s`). Default: hasta fin del segmento (imagen) o duración del clip (video)
  - Audio del overlay se ignora — tu voz sigue
- [ ] 🎬 **Sergio** corre el render:
  ```bash
  python3 scripts/media-overlay.py $VIDEO
  ```
- [ ] 🎬 **Sergio** revisa `fuente/video/7_video_media_overlay.mp4`

**Flags útiles:**

| Flag       | Default                    | Qué hace              |
| ---------- | -------------------------- | --------------------- |
| `--video`  | `6_video_limpio_logos.mp4` | Video de entrada      |
| `--output` | `7_video_media_overlay.mp4`| Video de salida       |
| `--fade`   | `0.3`                      | Fade in/out (reservado) |
| `--crf`    | `18`                       | Calidad de video      |
| `--dry-run`| —                          | Solo muestra detecciones |

---

### Paso 8 — Text Overlay (Black Cards)

**Doc:** [8_text-overlay.md](8_text-overlay.md) · **Script:** [`scripts/text-overlay.py`](scripts/text-overlay.py)

Superpone pantallas negras con texto blanco centrado en momentos clave — estilo Dan Koe. El audio sigue sonando debajo.

- [ ] 🌑 **Sinistra** corre dry-run — si `overlay-text.md` no existe, se copia automáticamente de `transcription_limpia.md` (Paso 5):
  ```bash
  python3 scripts/text-overlay.py $VIDEO --dry-run
  ```
- [ ] 🎬 **Sergio** abre `overlay-text.md` en Antigravity (format on save desactivado) y marca frases con `>>>`:
  ```markdown
  [0:32.96 - 0:34.72] Porque me estaba volviendo obsoleto.
  >>> Porque me estaba
  volviendo obsoleto
  ```
  - El texto después de `>>>` es lo que aparece en pantalla
  - Saltos de línea = saltos de línea en pantalla
  - Para frases seguidas sin gap (negro continuo), agrupar con `===`:
    ```markdown
    ===
    >>> Primera frase
    >>> Segunda frase
    >>> Tercera frase
    ===
    ```
- [ ] 🌑 **Sinistra** corre dry-run para verificar timestamps:
  ```bash
  python3 scripts/text-overlay.py $VIDEO --dry-run
  ```
- [ ] 🎬 **Sergio** corre el render:
  ```bash
  python3 scripts/text-overlay.py $VIDEO
  ```
- [ ] 🎬 **Sergio** revisa `fuente/video/8_video_text_overlay.mp4` — ¿texto legible, bien posicionado, timing correcto?

**Flags útiles:**

| Flag             | Default                                  | Qué hace                          |
| ---------------- | ---------------------------------------- | --------------------------------- |
| `--video`        | `7_video_media_overlay.mp4`              | Video de entrada                  |
| `--output`       | `8_video_text_overlay.mp4`               | Video de salida                   |
| `--font`         | `recursos/fuentes/default.ttf`           | Ruta a la fuente (Source Serif Bold) |
| `--fontsize`     | `64`                                     | Tamaño de fuente en px            |
| `--min-duration` | `3.0`                                    | Segundos mínimos en pantalla      |
| `--pad-before`   | `0.3`                                    | Padding antes de la frase (s)     |
| `--pad-after`    | `0.5`                                    | Padding después de la frase (s)   |
| `--crf`          | `18`                                     | Calidad de video (menor = mejor)  |
| `--dry-run`      | —                                        | Solo muestra detecciones          |

**⚠️ Cuidado con caracteres especiales:** El script escapa `%` automáticamente (`\%` para ffmpeg). Si ves pantalla negra sin texto, revisar que no haya un carácter sin escapar. Ver la doc completa en `8_text-overlay.md` → sección "Bugs conocidos".

---

### Paso 9 — Inserts

**Doc:** [9_inserts.md](9_inserts.md) · **Script:** [`scripts/inserts.py`](scripts/inserts.py)

Corta el video en puntos específicos e inserta clips completos (con su audio). El video resultante es más largo. **Va al final del pipeline** porque modifica la duración — si fuera antes, todos los timestamps de los overlays se descuadrarían.

- [ ] 🌑 **Sinistra** corre dry-run — si `overlay-inserts.md` no existe, se copia automáticamente de `transcription_limpia.md`:
  ```bash
  python3 scripts/inserts.py $VIDEO --dry-run
  ```
- [ ] 🎬 **Sergio** abre `overlay-inserts.md` y marca inserciones con `>>>`:
  ```markdown
  [0:32.96 - 0:34.72] (1.8s) Porque me estaba volviendo obsoleto.
  >>> sam-altman.mp4 | @"obsoleto"
  ```
  - Clips en `fuente/inserts/` (entran completos con su audio)
  - `@"palabra"` = se inserta DESPUÉS de esa palabra
- [ ] 🎬 **Sergio** corre el render:
  ```bash
  python3 scripts/inserts.py $VIDEO
  ```
- [ ] 🎬 **Sergio** revisa `fuente/video/9_video_inserts.mp4`

**Flags útiles:**

| Flag       | Default                     | Qué hace              |
| ---------- | --------------------------- | --------------------- |
| `--video`  | `8_video_text_overlay.mp4`  | Video de entrada      |
| `--output` | `9_video_inserts.mp4`       | Video de salida       |
| `--crf`    | `18`                        | Calidad de video      |
| `--dry-run`| —                           | Solo muestra detecciones |

---

## Dependencias

- `ffmpeg` + `ffprobe` — procesamiento de audio/video (⚠️ Paso 8 requiere `drawtext`: instalar desde `homebrew-ffmpeg/ffmpeg` tap, no el estándar)
- `python3` — scripts de automatización
- `numpy` + `scipy` — cross-correlation (Paso 1)
- `rsvg-convert` — conversión SVG → PNG (`brew install librsvg`)
- OpenAI API key — transcripción con Whisper (Paso 5, lo corre Sinistra)
- `requests` (opcional) — llamadas HTTP (el script usa urllib por defecto)
