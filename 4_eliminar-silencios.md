# Jump cuts automáticos — Eliminar silencios del teleprompter

**Problema:** El video fue grabado leyendo un teleprompter. El patrón es: frase → pausa (Sergio lee la siguiente línea) → frase → pausa. Esas pausas son silencios muertos que no aportan nada al video final. Cortarlos manualmente en DaVinci Resolve tomaría horas — son cientos de cortes.

**Razonamiento:** La clave es que las pausas del teleprompter tienen una firma acústica muy clara: **silencio**. Si podemos detectar automáticamente dónde hay silencio y dónde hay voz, podemos cortar los silencios y pegar solo las partes con voz. Esto se llama **jump cut automation**.

**¿Qué es un jump cut?** Es un corte donde el video salta de un momento a otro sin transición. En YouTube es el estándar — casi todos los creadores lo usan para eliminar pausas, muletillas y errores. El espectador está tan acostumbrado que ni lo nota.

**El balance crítico: ¿cuánto silencio cortar?**

No todos los silencios son iguales:

- **< 0.8s:** Respiraciones y micro-pausas naturales del habla. **NO cortar** — si las quitas, suena robótico e irrespirable.
- **0.8 - 1.5s:** Pausas cortas entre ideas. **NO cortar** — son pausas naturales que dan ritmo al discurso.
- **> 1.5s:** Pausas del teleprompter (leyendo la siguiente línea). **SÍ cortar** — son tiempo muerto.

Además, al cortar no queremos que una frase termine y la siguiente empiece _inmediatamente_. Eso suena atropellado. Dejamos un **padding** de 0.3 segundos a cada lado del corte — suficiente para que se sienta natural pero sin la pausa larga original.

---

#### Paso 7a — Detectar silencios con ffmpeg

ffmpeg tiene un filtro llamado `silencedetect` que analiza el audio y reporta cada segmento de silencio con su timestamp de inicio, fin y duración.

```bash
ffmpeg -i fuente/video/3_video_color_grade.mp4 \
  -af "silencedetect=noise=-30dB:d=0.8" \
  -f null - 2>&1 | grep "silence_" > tmp/silences.txt
```

| Flag                      | Qué hace                                                                                                                                                                                                                |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `-af "silencedetect=..."` | Aplica el filtro de detección de silencios al audio                                                                                                                                                                     |
| `noise=-30dB`             | Threshold de silencio. Todo lo que esté a -30dB o menos se considera "silencio". -30dB es un buen punto para un mic de estudio (SM7B) — captura las pausas reales sin confundir susurros o ruido de fondo con silencio. |
| `d=0.8`                   | Duración mínima en segundos para que cuente como silencio. Cualquier silencio menor a 0.8s se ignora (son respiraciones).                                                                                               |
| `-f null -`               | No genera archivo de salida — solo queremos el log de detección.                                                                                                                                                        |
| `grep "silence_"`         | Filtra solo las líneas de detección de silencio del output de ffmpeg.                                                                                                                                                   |

**Sobre el threshold -30dB:**

- -20dB = muy permisivo, solo detecta silencios totales
- -30dB = buen balance para mic de estudio en ambiente controlado ✅
- -40dB = muy sensible, puede cortar partes de voz suave
- El SM7B tiene piso de ruido muy bajo, así que -30dB funciona bien

**Output de ejemplo:**

```
silence_start: 40.508750
silence_end: 48.398375 | silence_duration: 7.889625
silence_start: 55.294000
silence_end: 72.893604 | silence_duration: 17.599604
```

**Resultado de este video:** 219 silencios detectados, de los cuales 159 son mayores a 1.5s (los que cortamos).

---

#### Paso 7b — Calcular segmentos de voz (Python)

Con la lista de silencios, invertimos la lógica: en vez de "dónde hay silencio", calculamos "dónde hay voz" — esos son los segmentos que queremos mantener.

```python
import re, os

# 1. Parsear el output de silencedetect
with open('tmp/silences.txt') as f:
    lines = f.readlines()

silences = []
current_start = None
for line in lines:
    m_start = re.search(r'silence_start:\s*([\d.]+)', line)
    m_end = re.search(r'silence_end:\s*([\d.]+)\s*\|\s*silence_duration:\s*([\d.]+)', line)
    if m_start:
        current_start = float(m_start.group(1))
    if m_end:
        end = float(m_end.group(1))
        dur = float(m_end.group(2))
        if current_start is not None:
            silences.append((current_start, end, dur))
        current_start = None

# 2. Configuración
MIN_SILENCE = 1.5   # Solo cortar silencios mayores a 1.5 segundos
PADDING = 0.3       # Dejar 0.3s de "aire" antes y después de cada corte
VIDEO_DURATION = 1511.51  # Duración del video (de ffprobe)

# 3. Filtrar solo silencios largos
long_silences = [(s, e, d) for s, e, d in silences if d > MIN_SILENCE]

# 4. Calcular segmentos a mantener (inversión de silencios)
cuts = []
prev_end = 0
for s_start, s_end, s_dur in long_silences:
    seg_end = s_start + PADDING  # Mantener 0.3s después del inicio del silencio
    if seg_end > prev_end + 0.1:  # Evitar segmentos vacíos
        cuts.append((prev_end, seg_end))
    prev_end = s_end - PADDING  # Empezar 0.3s antes del fin del silencio

# Último segmento hasta el final del video
if prev_end < VIDEO_DURATION:
    cuts.append((prev_end, VIDEO_DURATION))
```

**Visualización de lo que hace el padding:**

```
Original:   [===FRASE 1===]----silencio 5s----[===FRASE 2===]
                           ^                  ^
                     silence_start        silence_end

Con padding: [===FRASE 1===][0.3s]  ✂️  [0.3s][===FRASE 2===]
                                   corte
```

El padding de 0.3s asegura que:

- La última sílaba de la frase anterior no se corta
- La primera sílaba de la siguiente frase no se come
- Hay un micro-silencio entre frases que suena natural

**Resultados de este video:**

| Métrica                        | Valor         |
| ------------------------------ | ------------- |
| Silencios totales detectados   | 219           |
| Silencios > 1.5s (cortados)    | 159           |
| Silencios ≤ 1.5s (conservados) | 60            |
| Tiempo total recortado         | 8.1 minutos   |
| Duración original              | 25:11 (1511s) |
| Duración resultante            | 17:10 (1030s) |
| Segmentos de voz generados     | 160           |

---

#### Paso 7c — Extraer y concatenar segmentos

**¿Por qué no usar un solo comando ffmpeg?**

El approach ideal sería usar `trim` + `concat` en un solo filtro complejo:

```
[0:v]trim=start=0:end=5,setpts=PTS-STARTPTS[v0];
[0:v]trim=start=8:end=15,setpts=PTS-STARTPTS[v1];
...concatenar todo...
```

Esto funciona para pocos segmentos, pero con 160 segmentos ffmpeg necesita mantener todos en memoria simultáneamente y **se queda sin RAM** (el proceso fue matado por el OS con SIGTERM). En un video 1080p60fps, cada segmento decodificado consume mucha memoria.

**Solución: extraer cada segmento por separado y concatenar al final.**

Es más lento pero funciona con cualquier cantidad de segmentos y cualquier cantidad de RAM.

**Formato intermedio: MPEG-TS (.ts)**

Usamos MPEG Transport Stream como formato intermedio porque:

- Soporta **concatenación binaria** — los archivos .ts se pueden pegar uno detrás de otro sin re-encodear
- MP4 NO soporta esto — su estructura de metadatos (moov atom) no es concatenable
- Al final, el concat de .ts → .mp4 es instantáneo (`-c copy`, sin re-encoding)

**Script generado:**

```bash
#!/bin/bash
set -e
SRC="fuente/video/3_video_color_grade.mp4"
DIR=tmp/jc_segments
mkdir -p $DIR

# Extraer cada segmento como .ts
# -ss antes de -i = seek rápido (input seeking, usa keyframes)
# Cada segmento se re-encodea individualmente
ffmpeg -ss 0.000 -i "$SRC" -t 30.770 -c:v libx264 -crf 18 -preset fast -c:a aac -b:a 192k -f mpegts -y $DIR/seg_0000.ts
ffmpeg -ss 30.571 -i "$SRC" -t 5.531 -c:v libx264 -crf 18 -preset fast -c:a aac -b:a 192k -f mpegts -y $DIR/seg_0001.ts
# ... (160 segmentos total)
ffmpeg -ss 1499.123 -i "$SRC" -t 12.387 -c:v libx264 -crf 18 -preset fast -c:a aac -b:a 192k -f mpegts -y $DIR/seg_0159.ts

# Generar lista de concat
# Formato: file 'ruta_al_segmento.ts'
for i in $(seq -f "%04g" 0 159); do
  echo "file 'seg_${i}.ts'" >> $DIR/list.txt
done

# Concatenar todos los .ts en un .mp4 final
# -c copy = no re-encodea, solo empaqueta
ffmpeg -f concat -safe 0 -i $DIR/list.txt -c copy -y 4_video_jumpcut.mp4
```

| Flag                   | Qué hace                                                              |
| ---------------------- | --------------------------------------------------------------------- |
| `-ss {start}`          | Seek al inicio del segmento (antes de `-i` = input seeking, rápido)   |
| `-t {duration}`        | Duración del segmento a extraer                                       |
| `-c:v libx264 -crf 18` | Re-encodea video a H.264 CRF 18 (visualmente lossless)                |
| `-preset fast`         | Preset rápido — prioriza velocidad sobre compresión (son 160 encodes) |
| `-c:a aac -b:a 192k`   | Audio AAC 192kbps                                                     |
| `-f mpegts`            | Output en formato MPEG Transport Stream (concatenable)                |
| `-f concat`            | Modo concatenación de ffmpeg                                          |
| `-safe 0`              | Permite rutas relativas en la lista                                   |
| `-c copy`              | Copia streams sin re-encodear (instantáneo)                           |

**¿Por qué `-preset fast` en vez de `medium`?**

Con 160 segmentos individuales, la velocidad importa. `fast` vs `medium` produce archivos ~10% más grandes pero encodea ~40% más rápido. Como el CRF es 18 (alta calidad), la diferencia visual es imperceptible.

**Tiempo de procesamiento:** ~20 minutos en Apple Silicon para 160 segmentos de un video 1080p60.

---

#### Tuning de los jump cuts

Si quieres ajustar el comportamiento para futuros videos:

| Quiero...                                   | Cambiar...                                                                 |
| ------------------------------------------- | -------------------------------------------------------------------------- |
| Cortar solo pausas muy largas (conservador) | `MIN_SILENCE = 3.0` (solo 62 cortes en este video)                         |
| Cortar pausas más cortas (agresivo)         | `MIN_SILENCE = 1.0` (más cortes, video más compacto)                       |
| Más aire entre frases                       | `PADDING = 0.5` (medio segundo de respiración)                             |
| Cortes más tight/rápidos                    | `PADDING = 0.15` (casi inmediato, estilo MrBeast)                          |
| Cortar hasta muletillas                     | `noise=-25dB` + `d=0.3` (muy agresivo, no recomendado sin revisión manual) |

#### Técnicas de corte avanzadas (para DaVinci Resolve)

Los jump cuts automáticos son el 80% del trabajo mecánico. Para el 20% creativo, estas técnicas se aplican mejor manualmente en DaVinci:

| Técnica                       | Qué es                                                         | Cuándo usarla                                                                                                 |
| ----------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| **Jump cut** (lo que hicimos) | Corte directo, sin transición                                  | Default para eliminar pausas. Rápido, limpio.                                                                 |
| **J-cut**                     | El audio del SIGUIENTE clip empieza antes del corte de video   | Transiciones entre ideas. El espectador "oye" la siguiente idea antes de "verla". Suena fluido y profesional. |
| **L-cut**                     | El audio del clip ANTERIOR continúa después del corte de video | Para mantener continuidad. El video ya cambió pero la voz sigue. Común en documentales.                       |
| **Breathing room**            | Silencio intencional de 0.5-1s entre secciones                 | Separar bloques temáticos. Le da al espectador tiempo de procesar antes de la siguiente idea.                 |

---

## Resumen de Archivos Generados

| Archivo                                 | Paso | Tamaño                                      |
| --------------------------------------- | ---- | ------------------------------------------- |
| `fuente/audio/1_audio_extraido.aac`       | 1    | 30 MB                                       |
| `fuente/audio/1_audio_stereo.wav`      | 2    | 280 MB                                      |
| `fuente/video/1_video_sincronizado.mp4` | 4    | 8.8 GB                                      |
| `fuente/video/2_video_denoised.mp4`     | 5    | ~1.5 GB (re-encoded H.264 CRF 18)           |
| `fuente/video/3_video_color_grade.mp4`  | 6    | ~1.5 GB (re-encoded H.264 CRF 18)           |
| `fuente/video/4_video_jumpcut.mp4`      | 7    | ~800 MB (17:10, 160 segmentos concatenados) |

Archivos temporales (en `tmp/` dentro del folder del video, se pueden borrar):

- `tmp/sony_chunk.wav` — chunk de Sony para correlación
- `tmp/sm7b_chunk.wav` — chunk de SM7B para correlación

## Dependencias

- `ffmpeg` — manipulación de audio/video
- `python3` + `numpy` + `scipy` — cross-correlation para detección de offset
