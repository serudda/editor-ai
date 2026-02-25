# Paso 9 — Inserts

**Problema:** En ciertos momentos del video, Sergio quiere insertar clips (con su propio audio) que cortan el video principal. El resultado es un video más largo donde el clip entra como un segmento independiente. Hacerlo manualmente en DaVinci implica partir el timeline, arrastrar clips, alinear — repetir × N.

**Razonamiento:** El script lee `overlay-inserts.md` donde Sergio marca en qué palabra exacta se inserta cada clip. El script calcula el timestamp word-level de esa palabra, corta el video base en ese punto, inserta el clip completo (con su audio), y retoma el video base donde lo dejó.

**Prerequisito:**
- Paso 5 completado (`transcription_original.json` + `transcription_limpia.md`)
- Paso 8 completado (`8_video_text_overlay.mp4` como input)
- Clips editados y listos en `fuente/inserts/`

---

## Flujo completo

### 1. 🌑 `overlay-inserts.md` se crea automáticamente

Al correr `inserts.py --dry-run`, si `overlay-inserts.md` no existe, el script lo copia de `transcription_limpia.md` y le agrega instrucciones.

```bash
python3 scripts/inserts.py $VIDEO --dry-run
```

### 2. 🎬 Sergio marca puntos de inserción con `>>>`

Abre `overlay-inserts.md` y agrega `>>>` debajo del segmento donde quiere insertar el clip:

```markdown
[0:32.96 - 0:34.72] (1.8s) Porque me estaba volviendo obsoleto.
>>> sam-altman.mp4 | @"obsoleto"
```

**Reglas del marcado:**
- `>>>` activa la inserción del clip
- Primer valor = nombre del archivo en `fuente/inserts/` (ej: `sam-altman.mp4`)
- `@"palabra"` = el clip se inserta **después** de esa palabra
- El script busca la palabra en la transcripción word-level para el timestamp exacto
- El clip entra completo (no se recorta). Si Sergio quiere solo una parte, lo edita antes de ponerlo en `fuente/inserts/`

### 3. 🌑 Sinistra corre dry-run

```bash
python3 scripts/inserts.py $VIDEO --dry-run
```

Verificar: timestamps correctos, archivos encontrados, orden de inserción.

### 4. 🎬 Sergio corre el render

```bash
python3 scripts/inserts.py $VIDEO
```

### 5. 🎬 Sergio revisa

```bash
open $VIDEO/fuente/video/9_video_inserts.mp4
```

---

## Cómo funciona el corte

```
Video base: [====A====|corte|====B====]
                      ↓
Resultado:  [====A====][---BROLL---][====B====]
```

1. El script identifica el timestamp exacto de la palabra marcada con `@"..."`
2. Usa `word.end` como punto de corte (después de que termina la palabra)
3. Corta el video base en ese punto
4. Inserta el clip de B-Roll completo (video + audio)
5. Retoma el video base desde el punto de corte
6. Si hay múltiples inserciones, se procesan en orden cronológico

**Importante:** Los timestamps se calculan sobre el video base original. El script ajusta internamente los offsets cuando hay múltiples inserciones (cada B-Roll desplaza todo lo que viene después).

---

## Múltiples inserciones

```markdown
[0:32.96 - 0:34.72] (1.8s) Porque me estaba volviendo obsoleto.
>>> sam-altman.mp4 | @"obsoleto"

[1:15.16 - 1:21.76] (6.5s) Esto no es un framework nuevo, esto no es una tendencia.
>>> demo-cursor.mp4 | @"tendencia"

(Los clips deben estar en `fuente/inserts/`)
```

El script las procesa en orden cronológico. No importa en qué orden aparezcan en el archivo.

---

## Implementación técnica

El script usa `ffmpeg` con `concat demuxer` para unir los segmentos:

1. **Partir** el video base en segmentos usando `-ss` y `-t` (cortes precisos con re-encode)
2. **Normalizar** los B-Roll clips para que coincidan en codec, resolución, framerate y sample rate con el video base
3. **Generar** un archivo `concat_list.txt` con todos los segmentos en orden
4. **Concatenar** usando `ffmpeg -f concat`

```
# concat_list.txt
file 'segment_000.mp4'    # Video base 0:00 → 0:34.72
file 'broll_000.mp4'      # sam-altman.mp4 (normalizado)
file 'segment_001.mp4'    # Video base 0:34.72 → 1:21.76
file 'broll_001.mp4'      # demo-cursor.mp4 (normalizado)
file 'segment_002.mp4'    # Video base 1:21.76 → final
```

### Normalización de B-Roll

Para que el concat funcione sin problemas, cada B-Roll se re-encodea para coincidir con el video base:

- Resolución: misma que video base (scale + pad si es necesario)
- Codec: libx264 (mismo CRF y preset)
- Framerate: mismo que video base
- Audio: AAC, mismo sample rate y canales
- **Si el B-Roll no tiene audio:** se genera un track de silencio automáticamente

---

## ⚠️ Bugs conocidos

### 1. Clip sin audio rompe la concatenación (Resuelto)

Si un clip no tiene stream de audio, el `concat demuxer` de ffmpeg pierde el audio de los segmentos siguientes del video base. El video se genera sin errores pero el audio desaparece después del primer clip sin audio.

**Causa:** `ffmpeg -f concat` requiere que todos los segmentos tengan la misma estructura de streams (video + audio). Si un segmento no tiene audio, el concat se desincroniza.

**Solución:** El script detecta si el clip tiene audio con `ffprobe`. Si no tiene, agrega un input de silencio (`anullsrc`) con `-shortest` para generar un track de audio silencioso que coincida con la duración del video. Así todos los segmentos tienen video + audio y el concat funciona correctamente.

---

## Flags

| Flag | Default | Qué hace |
|------|---------|----------|
| `--video` | `8_video_text_overlay.mp4` | Video de entrada |
| `--output` | `9_video_inserts.mp4` | Video de salida |
| `--crf` | `18` | Calidad de video |
| `--preset` | `fast` | Preset de encoding |
| `--dry-run` | — | Solo muestra detecciones |

---

## Archivos involucrados

```
$VIDEO/
├── fuente/
│   ├── inserts/
│   │   ├── sam-altman.mp4                ← Clips que se insertan (editados y listos)
│   │   └── demo-cursor.mp4
│   ├── transcription/
│   │   ├── transcription_original.json   ← Word-level Whisper (Paso 5)
│   │   ├── transcription_limpia.md       ← Base legible (Paso 5)
│   │   └── overlay-inserts.md            ← Copia de limpia + marcas >>> (Sergio edita)
│   └── video/
│       ├── 8_video_text_overlay.mp4      ← Input (con text overlays)
│       └── 9_video_inserts.mp4           ← Output
└── tmp/
    └── inserts/
        ├── segment_000.mp4               ← Segmentos del video base
        ├── insert_000.mp4                ← Clip normalizado
        └── concat_list.txt               ← Lista para ffmpeg concat
```

---

## Dependencias

- `ffmpeg` — corte, normalización y concatenación
- `python3` — parsing, word-level matching, generación de comandos
