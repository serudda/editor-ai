# Paso 5 — Transcripción (Word-Level)

Genera la transcripción cruda del video con timestamps a nivel de palabra usando OpenAI Whisper API.

## Por qué word-level

Los timestamps por segmento (frases) tienen ~2s de imprecisión. Los timestamps por palabra son exactos al centésimo de segundo. Para colocar un logo o cortar a B-Roll en el momento preciso, necesitamos word-level.

## Qué hace el script

1. **Extrae audio** del video post-jump-cut (`4_video_jumpcut.mp4`) como OGG comprimido (~5-6MB para 17 min)
2. **Envía a Whisper API** con `timestamp_granularities[]=word` + `timestamp_granularities[]=segment`
3. **Guarda** `fuente/transcription/transcription_original.json` — la transcripción cruda, nunca se modifica
4. **Genera** `fuente/transcription/transcription_limpia.md` — versión legible con frases completas y timestamps

## Uso

```bash
# Transcribir (requiere OPENAI_API_KEY en el entorno)
python3 scripts/transcribe.py $VIDEO

# Con otro video de entrada
python3 scripts/transcribe.py $VIDEO --input 5_video_limpio.mp4

# Solo extraer audio (sin llamar a Whisper)
python3 scripts/transcribe.py $VIDEO --audio-only

# Solo regenerar transcription_limpia.md desde JSON existente
python3 scripts/transcribe.py $VIDEO --clean-only

# Dry run: muestra qué haría
python3 scripts/transcribe.py $VIDEO --dry-run
```

## Flags

| Flag           | Default                     | Qué hace                                                     |
| -------------- | --------------------------- | ------------------------------------------------------------- |
| `--input`      | `4_video_jumpcut.mp4`       | Video de entrada (en fuente/video/)                           |
| `--output`     | `transcription_original.json` | Archivo de salida (en fuente/transcription/)                |
| `--model`      | `whisper-1`                 | Modelo de Whisper                                             |
| `--language`   | `es`                        | Idioma del audio                                              |
| `--audio-only` | —                           | Solo extrae el audio, no llama a Whisper                      |
| `--clean-only` | —                           | Solo regenerar `transcription_limpia.md` desde JSON existente |
| `--dry-run`    | —                           | Muestra qué haría sin ejecutar                                |

## Output

### `transcription_original.json`

Transcripción cruda de Whisper. **NUNCA se modifica.** Contiene:

```json
{
  "text": "Transcripción completa...",
  "segments": [
    { "start": 0.0, "end": 3.5, "text": "Hoy quiero hablarles de algo..." }
  ],
  "words": [
    { "word": "Hoy", "start": 0.0, "end": 0.3 },
    { "word": "quiero", "start": 0.35, "end": 0.6 }
  ]
}
```

### `transcription_limpia.md`

Versión legible con frases completas y timestamps. Se genera automáticamente.

```markdown
[0:00 - 0:17.56] (17.6s) El 50% de los trabajos de oficina van a desaparecer...

[0:17.56 - 0:34.72] (17.2s) Yo lo viví en carne propia...
```

**¿Por qué no usar los segmentos de Whisper tal cual?** Whisper corta por tiempo (~5-10s), no por gramática. Las frases quedan a mitad de oración. El script reagrupa segmentos consecutivos hasta encontrar puntuación final (`. ? ! :`), con máximo ~20s por bloque, y fusiona remates cortos (<3s) con el bloque anterior.

**No editar directamente.** Regenerar con `--clean-only` si necesitás.

## Importante

- Si re-transcribes, se sobreescribe tanto el JSON como la limpia.
- Los archivos de overlay (`overlay-text.md`, `overlay-logos.md`, etc.) NO se sobreescriben — se generan aparte en cada paso.

## Requisitos

- `ffmpeg` — extracción de audio
- `OPENAI_API_KEY` — en el entorno o en `~/.openclaw/workspace/.env`
