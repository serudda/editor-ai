# Paso 7 — Media Overlay

**Problema:** En ciertos momentos del video, Sergio quiere mostrar una imagen o video en pantalla completa mientras su voz sigue sonando debajo. Infografías, screenshots, demos — el visual reemplaza la imagen de cámara pero el audio no se interrumpe. Hacerlo en DaVinci implica importar, posicionar, escalar, repetir × N.

**Razonamiento:** Funciona exactamente como Logo Overlay (Paso 6), pero en vez de un logo chiquito en la esquina, el medio ocupa toda la pantalla. El script lee `overlay-media.md`, busca timestamps word-level, y genera un solo comando ffmpeg con overlays fullscreen activados por `enable='between(t,...)'`.

**Diferencia con Inserts (Paso 9):** Los inserts CORTAN el video y lo alargan. Media Overlay va ENCIMA — el video base sigue corriendo debajo y la duración no cambia.

**Prerequisito:**
- Paso 5 completado (`transcription_original.json` + `transcription_limpia.md`)
- Paso 6 completado (`6_video_limpio_logos.mp4` como input)
- Archivos de media listos en `fuente/overlays/`

---

## Flujo completo

### 1. 🌑 `overlay-media.md` se crea automáticamente

Al correr `media-overlay.py --dry-run`, si `overlay-media.md` no existe, el script lo copia de `transcription_limpia.md` y le agrega instrucciones.

```bash
python3 scripts/media-overlay.py $VIDEO --dry-run
```

### 2. 🎬 Sergio marca medios con `>>>`

Abre `overlay-media.md` y agrega `>>>` debajo del segmento donde quiere el overlay:

```markdown
[4:37.35 - 4:57.15] (19.8s) en 2022 la IA no podía hacer una multiplicación bien...
>>> ai-timeline.png | @"multiplicación" | 19s

[3:22.11 - 3:44.25] (22.1s) OpenAI confirmaron en su documentación oficial...
>>> screenshot-codex.png | @"documentación" | 5s

[1:15.16 - 1:21.76] (6.5s) Mira lo que puede hacer hoy...
>>> demo-cursor.mp4 | @"hacer"
```

**Formato:**
- `>>>` activa el overlay
- Primer valor = nombre del archivo en `fuente/overlays/`
- `@"palabra"` = el overlay aparece cuando se dice esa palabra (timestamp word-level)
- `| 5s` = duración opcional. **Defaults:**
  - Si es video: duración del video
  - Si es imagen sin duración: hasta el final del segmento
  - Si se especifica duración: esa duración exacta

**Tipos soportados:**
- **Imágenes:** `.png`, `.jpg`, `.jpeg`, `.webp` — se muestran estáticas durante la duración
- **Videos:** `.mp4`, `.mov`, `.mkv`, `.avi`, `.webm` — se reproduce el video encima, pero **el audio del overlay se ignora** (tu voz sigue)

### 3. 🌑 Sinistra corre dry-run

```bash
python3 scripts/media-overlay.py $VIDEO --dry-run
```

Verificar: timestamps correctos, archivos encontrados, duraciones razonables.

### 4. 🎬 Sergio corre el render

```bash
python3 scripts/media-overlay.py $VIDEO
```

### 5. 🎬 Sergio revisa

```bash
open $VIDEO/fuente/video/7_video_media_overlay.mp4
```

---

## Comportamiento

### Imágenes fullscreen
- Se escalan a la resolución del video base (respetando aspect ratio)
- Se centran con padding negro si el ratio no coincide
- Aparecen con el timing de la palabra y duran lo especificado

### Videos fullscreen
- Se escalan igual que las imágenes
- Su audio se ignora — solo se usa el visual
- Duración default = duración del video overlay

### Sin overlays
Si no hay marcas `>>>` en el archivo, el script copia el video de entrada como salida sin re-encodear. No bloquea el pipeline.

---

## Flags

| Flag | Default | Qué hace |
|------|---------|----------|
| `--video` | `6_video_limpio_logos.mp4` | Video de entrada |
| `--output` | `7_video_media_overlay.mp4` | Video de salida |
| `--fade` | `0.3` | Fade in/out en segundos (reservado para futuro) |
| `--crf` | `18` | Calidad de video |
| `--preset` | `fast` | Preset de encoding |
| `--dry-run` | — | Solo muestra detecciones |

---

## Archivos involucrados

```
$VIDEO/
├── fuente/
│   ├── overlays/                          ← Media para superponer
│   │   ├── ai-timeline.png               ← Infografía
│   │   ├── screenshot-codex.png           ← Screenshot
│   │   └── demo-cursor.mp4               ← Video corto (su audio se ignora)
│   ├── transcription/
│   │   ├── transcription_original.json    ← Word-level Whisper (Paso 5)
│   │   ├── transcription_limpia.md        ← Base legible (Paso 5)
│   │   └── overlay-media.md              ← Copia de limpia + marcas >>> (Sergio edita)
│   └── video/
│       ├── 6_video_limpio_logos.mp4       ← Input (con logos)
│       └── 7_video_media_overlay.mp4      ← Output
```

---

## Dependencias

- `ffmpeg` — overlays de video
- `python3` — parsing, word-level matching, generación de comandos
