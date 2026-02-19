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
├── 5_logo-overlay.md                  ← Paso 5
└── scripts/
    ├── sync-audio.py                  ← Script Paso 1
    ├── denoise.py                     ← Script Paso 2
    ├── color-grade.py                 ← Script Paso 3
    ├── jump-cut.py                    ← Script Paso 4
    └── logo-overlay.py                ← Script Paso 5
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
│   ├── transcripcion/                      ← Transcripciones y detecciones
│   │   ├── transcription_words.json        ← Whisper word-level timestamps
│   │   └── logo-overlay.md                 ← Detecciones de logos (✅/❌)
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

| Flag | Default | Qué hace |
|------|---------|----------|
| `--video-file` | 0_video_original.MP4 | Nombre del video de cámara |
| `--audio-file` | 0_audio_original.mkv | Nombre del audio OBS |
| `--sony-start` | 30 | Segundo de inicio para chunk de Sony |
| `--sony-duration` | 60 | Duración del chunk de Sony |
| `--dry-run` | — | Solo detectar offset, no genera video |

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

| Flag | Default | Qué hace |
|------|---------|----------|
| `--input` | 1_video_sincronizado.mp4 | Video de entrada |
| `--strength` | medium | Preset: light / medium / heavy |
| `--custom` | — | Valores custom hqdn3d (ej: 5:5:6:6) |

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

| Flag | Default | Qué hace |
|------|---------|----------|
| `--input` | 2_video_denoised.mp4 | Video de entrada |
| `--warmth` | 0.05 | Calidez en midtonos (0.0-0.10) |
| `--saturation` | 1.1 | Saturación global |
| `--no-vignette` | — | Desactivar viñeta |

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

| Flag | Default | Qué hace |
|------|---------|----------|
| `--padding` | 0.3 | Segundos de "aire" antes/después del corte |
| `--min-silence` | 1.5 | Solo cortar silencios mayores a N segundos |
| `--noise` | -30 | Threshold de silencio en dB |
| `--dry-run` | — | Solo muestra stats, no genera video |

---

### Paso 5 — Logo Overlay
**Doc:** [5_logo-overlay.md](5_logo-overlay.md) · **Script:** [`scripts/logo-overlay.py`](scripts/logo-overlay.py)

Detecta marcas mencionadas en el video y superpone sus logos. Este paso tiene varias sub-tareas.

- [ ] 🌑 **Sinistra** transcribe el audio con word-level timestamps (Whisper API)
- [ ] 🌑 **Sinistra** detecta marcas en la transcripción y genera `fuente/transcripcion/logo-overlay.md`
- [ ] 🌑 **Sinistra** descarga logos (SVGL API → repo local → manual)
- [ ] 🎬 **Sergio** revisa `fuente/transcripcion/logo-overlay.md` y marca ✅/❌ en cada detección
  - Quitar repeticiones (ej: si dice "OpenAI" 5 veces en 30s, dejar solo la primera)
  - Quitar falsos positivos
- [ ] 🌑 **Sinistra** confirma que todos los logos ✅ están en `fuente/logos/` como PNG
- [ ] 🎬 **Sergio** corre el render (tarda ~10-20 min):
  ```bash
  python3 scripts/logo-overlay.py $VIDEO
  ```
- [ ] 🎬 **Sergio** revisa el video final en `output/` — ¿los logos aparecen en el momento correcto?

**Flags útiles:**

| Flag | Default | Qué hace |
|------|---------|----------|
| `--video` | 4_video_jumpcut.mp4 | Video de entrada |
| `--size` | 120 | Tamaño del logo en px |
| `--padding` | 40 | Padding del borde en px |
| `--fade` | 0.3 | Fade in/out en segundos |
| `--dry-run` | — | Solo muestra detecciones |
| `--print-cmd` | — | Solo imprime el comando ffmpeg |

---

## Dependencias

- `ffmpeg` + `ffprobe` — procesamiento de audio/video
- `python3` — scripts de automatización
- `numpy` + `scipy` — cross-correlation (Paso 1)
- `rsvg-convert` — conversión SVG → PNG (`brew install librsvg`)
- OpenAI API key — transcripción con Whisper (Paso 5, lo corre Sinistra)
