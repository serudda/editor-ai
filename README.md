# Video: "La Mejor Época Para Ti" — Post-Producción

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
ffmpeg -i fuente/audio.mkv -vn -c:a copy fuente/audio_extraido.aac
```

| Flag           | Qué hace                                                          |
| -------------- | ----------------------------------------------------------------- |
| `-i audio.mkv` | Archivo de entrada (grabación OBS)                                |
| `-vn`          | Descarta el video (fondo negro, no lo necesitamos)                |
| `-c:a copy`    | Copia el audio tal cual, sin re-encodear. Cero pérdida de calidad |

**Resultado:** `audio_extraido.aac` (30 MB, 25:27 de duración) — audio puro del SM7B.

**Verificación:** Se reprodujo el archivo para confirmar que el audio se escucha correctamente.

---

### 2. Convertir audio mono → estéreo

**Problema:** Al reproducir `audio_extraido.aac`, el audio solo se escuchaba por el lado izquierdo de los audífonos. El lado derecho estaba en silencio.

**Diagnóstico:** El SM7B es un micrófono mono (una sola cápsula, una sola señal). OBS lo grabó como "estéreo" técnicamente (2 canales), pero solo llenó el canal izquierdo (c0). El canal derecho (c1) quedó vacío/silencioso.

**Razonamiento:** No necesitamos hacer nada fancy — la señal mono es idéntica para ambos oídos. Solo hay que duplicar el canal izquierdo al derecho. Usamos el filtro `pan` de ffmpeg que permite reasignar canales. La salida es WAV (sin compresión) porque este archivo va directo a DaVinci Resolve para edición, y en edición siempre se trabaja con formatos sin pérdida.

```bash
ffmpeg -i fuente/audio_extraido.aac \
  -af "pan=stereo|c0=c0|c1=c0" \
  -c:a pcm_s16le \
  fuente/audio_stereo.wav
```

| Flag                             | Qué hace                                                                                                                           |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `-af "pan=stereo\|c0=c0\|c1=c0"` | Crea salida estéreo: canal izq (c0) = canal original izq (c0), canal der (c1) = también canal original izq (c0). Duplica la señal. |
| `-c:a pcm_s16le`                 | Codifica como WAV 16-bit sin compresión (máxima calidad para editar en DaVinci)                                                    |

**Resultado:** `audio_stereo.wav` (280 MB, 25:27, 48kHz estéreo) — audio por ambos lados.

**Por qué WAV y no AAC:** En edición de video se trabaja con audio sin compresión (WAV/PCM) para evitar artefactos de generación. AAC comprime → DaVinci decodifica → al exportar comprime de nuevo = doble pérdida. Con WAV la cadena es: original → WAV (sin pérdida) → DaVinci → export final (una sola compresión).

---

### 3. (Pendiente de documentar)

<!-- Siguiente paso: sincronización video + audio -->
