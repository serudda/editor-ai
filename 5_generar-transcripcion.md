# Paso 5 — Transcripción (Word-Level)

Genera la transcripción cruda del video con timestamps a nivel de palabra usando OpenAI Whisper API. Este archivo es la **fuente de verdad** para todos los pasos de overlay (logos, B-Roll, imágenes, etc.).

## Por qué word-level

Los timestamps por segmento (frases) tienen ~2s de imprecisión. Los timestamps por palabra son exactos al centésimo de segundo. Para colocar un logo o cortar a B-Roll en el momento preciso, necesitamos word-level.

## Qué hace el script

1. **Extrae audio** del video post-jump-cut (`4_video_jumpcut.mp4`) como OGG comprimido (~5-6MB para 17 min)
2. **Envía a Whisper API** con `timestamp_granularities[]=word` + `timestamp_granularities[]=segment`
3. **Guarda** `fuente/transcription/transcription_original.json` — la transcripción cruda, nunca se modifica

## Uso

```bash
# Transcribir (requiere OPENAI_API_KEY en el entorno)
python3 scripts/transcribe.py ~/ruta/al/folder-del-video

# Con otro video de entrada
python3 scripts/transcribe.py ~/ruta/al/folder --input 4_video_jumpcut.mp4

# Solo extraer audio (sin llamar a Whisper)
python3 scripts/transcribe.py ~/ruta/al/folder --audio-only

# Dry run: muestra qué haría
python3 scripts/transcribe.py ~/ruta/al/folder --dry-run
```

## Flags

| Flag           | Default                     | Qué hace                                                |
| -------------- | --------------------------- | ------------------------------------------------------- |
| `--input`      | 4_video_jumpcut.mp4         | Video de entrada (en fuente/video/)                     |
| `--output`     | transcription_original.json | Nombre del archivo de salida (en fuente/transcription/) |
| `--model`      | whisper-1                   | Modelo de Whisper                                       |
| `--language`   | es                          | Idioma del audio                                        |
| `--audio-only` | —                           | Solo extrae el audio, no llama a Whisper                |
| `--dry-run`    | —                           | Muestra qué haría sin ejecutar                          |

## Output

El archivo `transcription_original.json` contiene:

```json
{
	"text": "Transcripción completa...",
	"segments": [
		{
			"start": 0.0,
			"end": 3.5,
			"text": "Hoy quiero hablarles de algo..."
		}
	],
	"words": [
		{
			"word": "Hoy",
			"start": 0.0,
			"end": 0.3
		},
		{
			"word": "quiero",
			"start": 0.35,
			"end": 0.6
		}
	]
}
```

## Importante

- **Este archivo NUNCA se modifica.** Es la fuente cruda.
- Los pasos siguientes (logos, B-Roll, imágenes) generan sus propios archivos de overlay a partir de este.
- Si re-transcribes, se sobreescribe `transcription_original.json`. Los archivos de overlay quedan intactos (se regeneran aparte).

## Requisitos

- `ffmpeg` — extracción de audio
- `OPENAI_API_KEY` — en el entorno o en `~/.openclaw/workspace/.env`
- `curl` o `requests` de Python — llamada a la API
