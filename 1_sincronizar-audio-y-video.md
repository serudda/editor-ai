# Sincronizar Audio y Video

## Contexto

Sergio grabó un video con dos fuentes separadas:

- **Cámara**: Grabó el video en `.MP4` (9.1 GB, ~25 min). El audio de cámara existe pero es de menor calidad.
- **OBS + SM7B**: Grabó el audio por separado con un micrófono Shure SM7B, capturado por OBS como `.mkv`. El archivo contiene un video negro (pantalla OBS vacía) + el audio de alta calidad.

**Objetivo**: Extraer el audio del SM7B, limpiarlo, y combinarlo con el video de cámara para tener el mejor resultado posible (video de cámara + audio de micrófono profesional).

## Archivos Fuente

| Archivo            | Descripción                             | Tamaño |
| ------------------ | --------------------------------------- | ------ |
| `fuente/video.MP4` | Video original de cámara                | 9.1 GB |
| `fuente/audio.mkv` | Grabación OBS: audio SM7B + video negro | 1.1 GB |

---

## Paso a Paso

### 1. Extraer audio del archivo OBS

**Problema:** El archivo `audio.mkv` de OBS pesa 1.1 GB pero el audio útil son solo ~30 MB. El resto es un video negro que OBS grabó por defecto. Necesitamos separar el audio puro.

**Razonamiento:** Usamos `-c:a copy` en vez de re-encodear porque queremos el audio _exacto_ que capturó el SM7B. Cualquier re-encoding introduce pérdida de calidad innecesaria. El flag `-vn` descarta el stream de video completamente.

```bash
ffmpeg -i fuente/audio.mkv -vn -c:a copy fuente/1_audio_extraido.aac
```

| Flag           | Qué hace                                                          |
| -------------- | ----------------------------------------------------------------- |
| `-i audio.mkv` | Archivo de entrada (grabación OBS)                                |
| `-vn`          | Descarta el video (fondo negro, no lo necesitamos)                |
| `-c:a copy`    | Copia el audio tal cual, sin re-encodear. Cero pérdida de calidad |

**Resultado:** `1_audio_extraido.aac` (30 MB, 25:27 de duración) — audio puro del SM7B.

**Verificación:** Se reprodujo el archivo para confirmar que el audio se escucha correctamente.

---

### 2. Convertir audio mono → estéreo

**Problema:** Al reproducir `1_audio_extraido.aac`, el audio solo se escuchaba por el lado izquierdo de los audífonos. El lado derecho estaba en silencio.

**Diagnóstico:** El SM7B es un micrófono mono (una sola cápsula, una sola señal). OBS lo grabó como "estéreo" técnicamente (2 canales), pero solo llenó el canal izquierdo (c0). El canal derecho (c1) quedó vacío/silencioso.

**Razonamiento:** No necesitamos hacer nada fancy — la señal mono es idéntica para ambos oídos. Solo hay que duplicar el canal izquierdo al derecho. Usamos el filtro `pan` de ffmpeg que permite reasignar canales. La salida es WAV (sin compresión) porque este archivo va directo a DaVinci Resolve para edición, y en edición siempre se trabaja con formatos sin pérdida.

```bash
ffmpeg -i fuente/1_audio_extraido.aac \
  -af "pan=stereo|c0=c0|c1=c0" \
  -c:a pcm_s16le \
  fuente/audio_stereo.wav
```

| Flag                             | Qué hace                                                                                                                           |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `-af "pan=stereo\|c0=c0\|c1=c0"` | Crea salida estéreo: canal izq (c0) = canal original izq (c0), canal der (c1) = también canal original izq (c0). Duplica la señal. |
| `-c:a pcm_s16le`                 | Codifica como WAV 16-bit sin compresión (máxima calidad para editar en DaVinci)                                                    |

**Resultado:** `1_audio_stereo.wav` (280 MB, 25:27, 48kHz estéreo) — audio por ambos lados.

**Por qué WAV y no AAC:** En edición de video se trabaja con audio sin compresión (WAV/PCM) para evitar artefactos de generación. AAC comprime → DaVinci decodifica → al exportar comprime de nuevo = doble pérdida. Con WAV la cadena es: original → WAV (sin pérdida) → DaVinci → export final (una sola compresión).

---

### 3. Detectar el offset entre video y audio (cross-correlation)

**Problema:** La Sony A6400 y OBS empezaron a grabar en momentos diferentes. Necesitamos saber exactamente cuántos segundos de diferencia hay entre ambos para sincronizar el audio SM7B con el video de cámara.

**Razonamiento:** Ambas grabaciones captan la misma voz (Sergio hablando), solo que una con el mic de la cámara (peor calidad) y otra con el SM7B (mejor calidad). Podemos usar **cross-correlation** para encontrar en qué punto las ondas de audio coinciden.

**El truco que funciona:** En vez de comparar la waveform cruda (que tiene mucho ruido y diferencias de calidad entre mics), comparamos los **envelopes** — la forma general del volumen a lo largo del tiempo. Cuando Sergio habla fuerte, ambos mics registran volumen alto; cuando calla, ambos registran silencio. Esa forma es idéntica independientemente de la calidad del mic.

**Paso 3a — Extraer chunks de audio para comparar:**

Downsamplamos a 8kHz mono (no necesitamos calidad, solo la forma de la onda) y tomamos segmentos específicos:

```bash
# Sony: 60 segundos empezando en t=30s (evitar ruido de setup al inicio)
ffmpeg -i fuente/video.MP4 -vn -ac 1 -ar 8000 -ss 30 -t 60 -y tmp/sony_chunk.wav

# SM7B: 90 segundos desde el inicio (ventana más amplia para encontrar dónde cae el chunk de Sony)
ffmpeg -i fuente/1_audio_stereo.wav -ac 1 -ar 8000 -t 90 -y tmp/sm7b_chunk.wav
```

| Flag              | Qué hace                                                                       |
| ----------------- | ------------------------------------------------------------------------------ |
| `-ac 1`           | Convierte a mono (1 canal) — para correlación no necesitamos estéreo           |
| `-ar 8000`        | Downsamplea a 8kHz — reduce datos 6x, suficiente para detectar patrones de voz |
| `-ss 30`          | (Solo Sony) Empieza en segundo 30 — evita el ruido de setup/inicio             |
| `-t 60` / `-t 90` | Duración del chunk. SM7B más largo para que el chunk de Sony "quepa" dentro    |

**Por qué empezar en t=30s del Sony:** Los primeros segundos suelen tener ruido de setup (ajustar cámara, sentarse, etc.) que confunde la correlación. A los 30 segundos ya hay voz clara.

**Por qué el SM7B empieza en t=0 con 90s:** No sabemos cuánto offset hay. Si el SM7B empezó 0-30s después que la Sony, el fragmento correspondiente al t=30-90s de la Sony podría estar en cualquier parte de los primeros 90s del SM7B.

**Paso 3b — Cross-correlation con Python:**

```bash
pip3 install scipy  # Si no está instalado
```

```python
import numpy as np
from scipy import signal
import wave

def read_wav(path):
    with wave.open(path, 'r') as w:
        frames = w.readframes(w.getnframes())
        data = np.frombuffer(frames, dtype=np.int16).astype(np.float64)
        return data, w.getframerate()

# Leer los chunks
sony, sr = read_wav('tmp/sony_chunk.wav')
sm7b, _ = read_wav('tmp/sm7b_chunk.wav')

# Calcular envelopes (volumen promediado en ventanas de 100ms)
# Esto suaviza las diferencias de calidad entre mics y deja solo el patrón de habla
win = int(sr * 0.1)  # ventana de 100ms
sony_env = np.convolve(np.abs(sony), np.ones(win)/win, mode='same')
sm7b_env = np.convolve(np.abs(sm7b), np.ones(win)/win, mode='same')

# Cross-correlación (FFT-based = rápido)
# Desliza un envelope sobre el otro y mide dónde se parecen más
corr = signal.correlate(sm7b_env, sony_env, mode='full', method='fft')
lags = signal.correlation_lags(len(sm7b_env), len(sony_env), mode='full')

# El pico de la correlación = el punto de máxima coincidencia
peak_idx = np.argmax(corr)
lag_samples = lags[peak_idx]
lag_seconds = lag_samples / sr

# Confianza: qué tan fuerte es el pico vs el promedio
# >5x = buena confianza, >10x = excelente
confidence = corr[peak_idx] / np.mean(np.abs(corr))

# Calcular offset real
# El chunk de Sony empieza en t=30s del video original
# lag_seconds = dónde en el SM7B empieza la sección que coincide
# offset = 30.0 - lag_seconds
sm7b_match_time = lag_seconds
offset = 30.0 - sm7b_match_time

print(f"Offset: {offset:.3f}s | Confianza: {confidence:.1f}x")
```

**Resultado de este video:**

```
Offset: 6.801s | Confianza: 7.5x
→ SM7B empezó 6.801s DESPUÉS que la Sony
→ Añadir 6.801s de silencio al inicio del audio SM7B
```

**Interpretación:** OBS empezó a grabar ~6.8 segundos después que la cámara Sony. Para sincronizar, necesitamos retrasar el audio del SM7B 6.801 segundos (añadir silencio al inicio).

---

### 4. Combinar video + audio sincronizado

**Problema:** Tenemos el offset (6.801s). Ahora hay que juntar el video de la Sony con el audio del SM7B, aplicando ese delay.

**Razonamiento:** Usamos el filtro `adelay` de ffmpeg que añade milisegundos de silencio al inicio de un stream de audio. Copiamos el video sin re-encodear (`-c:v copy`) porque no queremos tocar la calidad del video — solo estamos reemplazando el audio. El audio sí se re-encodea a AAC porque necesitamos aplicar el filtro de delay.

```bash
ffmpeg -i fuente/video.MP4 -i fuente/audio_stereo_v2.wav \
  -filter_complex "[1:a]adelay=6801|6801[delayed_audio]" \
  -map 0:v -map "[delayed_audio]" \
  -c:v copy -c:a aac -b:a 192k \
  -shortest \
  -y fuente/1_video_sincronizado.mp4
```

| Flag                                    | Qué hace                                                                   |
| --------------------------------------- | -------------------------------------------------------------------------- |
| `-i video.MP4`                          | Input 0: video de la Sony (usamos su video)                                |
| `-i audio_stereo_v2.wav`                | Input 1: audio del SM7B (usamos su audio)                                  |
| `[1:a]adelay=6801\|6801[delayed_audio]` | Toma el audio del input 1, le añade 6801ms de delay a ambos canales (L\|R) |
| `-map 0:v`                              | Usa el video del input 0 (Sony)                                            |
| `-map "[delayed_audio]"`                | Usa el audio delayed del SM7B                                              |
| `-c:v copy`                             | Copia el video sin re-encodear (cero pérdida de calidad, ultra rápido)     |
| `-c:a aac -b:a 192k`                    | Encodea el audio a AAC 192kbps (buena calidad para edición)                |
| `-shortest`                             | Corta cuando el stream más corto termine (el video de Sony es más corto)   |

**Resultado:** `video_sincronizado.mp4` (8.8 GB, 25:11) — video de Sony A6400 + audio de SM7B perfectamente sincronizados.

**Tiempo de procesamiento:** ~22 segundos en Apple Silicon (el video se copia sin tocar, solo se procesa el audio).

---

## Resumen de Archivos Generados

| Archivo                         | Paso | Tamaño |
| ------------------------------- | ---- | ------ |
| `fuente/audio_extraido.aac`     | 1    | 30 MB  |
| `fuente/audio_stereo_v2.wav`    | 2    | 280 MB |
| `fuente/video_sincronizado.mp4` | 4    | 8.8 GB |

Archivos temporales (en `tmp/` dentro del folder del video, se pueden borrar):

- `tmp/sony_chunk.wav` — chunk de Sony para correlación
- `tmp/sm7b_chunk.wav` — chunk de SM7B para correlación

## Dependencias

- `ffmpeg` — manipulación de audio/video
- `python3` + `numpy` + `scipy` — cross-correlation para detección de offset
