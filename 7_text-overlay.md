# Paso 7 — Text Overlay (Black Cards)

**Problema:** En ciertos momentos del video, Sergio quiere interrumpir la imagen con un fondo negro completo y mostrar una frase en texto blanco centrado — estilo Dan Koe. El audio sigue sonando. Es una técnica de énfasis: fuerza al espectador a enfocarse en la frase. Funciona especialmente bien con datos duros, afirmaciones fuertes, o frases de impacto.

**Razonamiento:** En vez de hacer esto manualmente en DaVinci (crear clip negro, agregar texto, posicionar, repetir × N), el script lee un archivo markdown donde Sergio marca las frases, calcula timestamps precisos con word-level matching, y genera un solo comando ffmpeg con `drawbox` (fondo negro) + `drawtext` (texto blanco centrado).

**Prerequisito:**
- Paso 5 completado (`transcription_original.json` con word-level timestamps)
- Paso 6 completado (`6_video_limpio_logos.mp4` como input)
- ffmpeg compilado con `--enable-libfreetype` (necesario para el filtro `drawtext`)

---

## Flujo completo

### 1. 🌑 Sinistra genera `overlay-text.md`

Lee `transcription_original.json` (Whisper word-level) y genera un archivo legible con la transcripción segmentada por frases, con timestamps.

**Archivo:** `fuente/transcription/overlay-text.md`

**⚠️ FUENTE DE VERDAD:** Siempre es la transcripción Whisper del video limpio, **NUNCA** el guión original del teleprompter. Sergio improvisa al grabar — agrega, elimina, reordena y repite frases. El guión no refleja lo que realmente se dice en el video.

**Formato del archivo generado:**

```markdown
# Overlay Text — 5_video_limpio.mp4
# INSTRUCCIONES:
# Para marcar una text card, agrega >>> debajo.
# El texto después de >>> es lo que aparece en pantalla.

[0:00.00 - 0:16.86] (16.9s) El 50% de los trabajos de oficina van a desaparecer en menos de 5 años, y no lo digo yo, lo dice Darío Amodei...

[0:18.00 - 0:32.38] (14.4s) Yo lo viví en carne propia, hace 3 meses renuncié al trabajo...

[0:32.96 - 0:34.72] (1.8s) Porque me estaba volviendo obsoleto.
```

Cada bloque tiene:
- `[MM:SS.xx - MM:SS.xx]` — rango del segmento Whisper
- `(Ns)` — duración del segmento
- El texto tal como se dijo (de Whisper, no del guión)

### 2. 🎬 Sergio marca frases con `>>>`

Abre `overlay-text.md` en Obsidian y agrega `>>>` debajo de las frases que quiere como text card:

```markdown
[0:32.96 - 0:34.72] (1.8s) Porque me estaba volviendo obsoleto.
>>> Porque me estaba
volviendo obsoleto
```

**Reglas del marcado:**
- `>>>` activa la frase como text card
- El texto después de `>>>` es **EXACTAMENTE** lo que aparece en pantalla
- Saltos de línea = saltos de línea en pantalla (para controlar cómo se divide)
- Si una línea no tiene `>>>`, se ignora completamente
- Sergio puede editar el texto de display libremente (mayúsculas, signos, abreviaciones)
- El script busca ese texto en la transcripción word-level para el timing — no necesita coincidir letra por letra (fuzzy matching con threshold 0.5)

**⚠️ Obsidian convierte `>>>` en `> > >`** (lo trata como blockquote anidado triple). El parser acepta ambos formatos. Lo mismo con `===` → `= = =`.

### 3. Bloques continuos con `===`

Para varias frases seguidas donde el negro NO debe desaparecer entre ellas (el fondo se mantiene negro, solo cambia el texto):

```markdown
[0:00.00 - 0:16.86] (16.9s) El 50% de los trabajos de oficina van a desaparecer...
===
>>> El 50% de los trabajos de oficina
van a desaparecer en menos de 5 años
>>> y no lo digo yo, lo dice
Darío Amodei, el CEO de Antropic
>>> una de las empresas más importantes
de inteligencia artificial del mundo
===
```

**Cómo funcionan los bloques:**
- `===` abre y cierra un bloque
- Cada `>>>` dentro del bloque es un cambio de texto (el negro no desaparece entre cards)
- El script ajusta automáticamente los tiempos para que no haya gaps entre cards del mismo bloque
- Si una card termina en `t=4.42` y la siguiente empieza en `t=4.50`, el script extiende la anterior hasta `4.50` para que el negro sea continuo
- Si hay overlap, recorta la anterior

**¿Cuándo usar bloques vs cards sueltas?**

| Situación | Usar |
|-----------|------|
| Frase de impacto aislada | Card suelta (`>>>` sin `===`) |
| Dato + fuente (ej: "50%... lo dice Amodei") | Bloque `===` (negro continuo, texto cambia) |
| Ráfaga de datos (3+ frases seguidas) | Bloque `===` |
| Dos frases separadas por >5s de otro contenido | Cards sueltas individuales |

### 4. 🌑 Sinistra corre dry-run

```bash
python3 scripts/text-overlay.py $VIDEO --dry-run
```

Muestra cada card con su timestamp calculado, duración, y fuente del match:

```
📊 4 text cards encontradas

   [0:00 - 0:04.42] (4.4s) [word-level (display)] [block 1]
   → "El 50% de los trabajos de oficina / van a desaparecer en menos de 5 años"

   [0:04.42 - 0:09.00] (4.6s) [word-level (display)] [block 1]
   → "y no lo digo yo, lo dice / Darío Amodei, el CEO de Antropic"

   [0:32.66 - 0:34.72] (2.1s) [word-level (display)]
   → "Porque me estaba / volviendo obsoleto"
```

**Qué verificar en el dry-run:**
- ¿Los timestamps coinciden con el momento en que se dice la frase?
- ¿Las duraciones se ven razonables? (no cards de 0.1s ni de 30s)
- ¿La fuente dice `word-level`? Si dice `segment fallback`, el fuzzy match falló — revisar el texto del `>>>`

### 5. 🌑 Sinistra genera el comando

```bash
python3 scripts/text-overlay.py $VIDEO --print-cmd
```

Esto genera:
1. Archivos de texto individuales en `$VIDEO/tmp/text_cards/card_NNN.txt` (uno por card, con `%` escapado)
2. Script bash en `$VIDEO/tmp/text_overlay_cmd.sh` con el comando ffmpeg completo

### 6. 🎬 Sergio corre el render

```bash
bash $VIDEO/tmp/text_overlay_cmd.sh
```

**⚠️ REGLA:** Sinistra NUNCA corre el render directamente. El timeout de 7 minutos del agente mata procesos largos. Siempre pasarle el comando a Sergio.

**Tiempo estimado:** ~10-15 min para un video de 12 min en Apple Silicon con `--preset fast`.

### 7. 🎬 Sergio revisa el resultado

```bash
open $VIDEO/fuente/video/7_video_text_overlay.mp4
```

**Qué revisar:**
- ¿El texto aparece en el momento correcto?
- ¿Es legible? (tamaño, fuente)
- ¿Desaparece cuando termina la frase? (no se queda de más)
- ¿Las transiciones negro↔video son limpias?
- ¿Los bloques `===` se sienten continuos? (no parpadea el negro)

---

## Timing de las cards

```
start = timestamp_primera_palabra - pad_before
end   = timestamp_última_palabra + pad_after
```

**Defaults actuales:**
- **pad_before:** 0.3s → el negro aparece un pelín antes de que empiece a hablar
- **pad_after:** 0.0s → la card desaparece inmediatamente al terminar la frase
- **min_duration:** 0.0s → sin mínimo, dura lo que dura la frase

**¿Por qué pad_after = 0?** Porque se siente más dinámico. En cuanto Sergio termina la frase, aparece él en pantalla. Si la frase es muy corta, la solución es que Sergio escoja frases más largas — no que el script agregue tiempo artificial.

**Cadena de fallback para timestamps:**
1. Buscar el `display_text` (lo de pantalla) en word-level → más preciso
2. Buscar el `segment_text` (frase completa del bloque) en word-level
3. Usar timestamps del segmento Whisper como último recurso

**Fuzzy matching:** Usa `difflib.SequenceMatcher` con threshold 0.5. Tolera diferencias menores entre el texto marcado y lo que Whisper transcribió (acentos, puntuación, mayúsculas). Si el score es < 0.5, pasa al siguiente fallback.

---

## Implementación técnica: drawbox + drawtext

Cada text card genera **dos filtros ffmpeg encadenados** en el `-vf`:

```
drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='between(t,START,END)'
drawtext=fontfile=FONT:textfile=CARD_FILE:fontcolor=white:fontsize=SIZE:x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,START,END)'
```

**¿Qué hace cada parte?**

| Filtro | Función |
|--------|---------|
| `drawbox` | Pinta un rectángulo negro de tamaño `iw×ih` (full screen) con `t=fill` (relleno sólido) |
| `drawtext` | Renderiza texto blanco centrado horizontal (`x=(w-text_w)/2`) y vertical (`y=(h-text_h)/2`) |
| `enable='between(t,S,E)'` | Activa el filtro solo entre los timestamps S y E. Fuera de ese rango, el filtro no existe. |
| `textfile=` | Lee el texto de un archivo externo. Maneja newlines nativamente (vs `text=` que no). |

**¿Por qué `textfile=` en vez de `text=`?**

- `text=` NO maneja newlines dentro del filtro. Hay que escapar `\n` pasando por Python → bash → ffmpeg, y las capas de escape son frágiles.
- `textfile=` lee un archivo `.txt` directo. Los saltos de línea del archivo = saltos de línea en pantalla. Mucho más simple.

**Los archivos de texto se generan en:** `$VIDEO/tmp/text_cards/card_NNN.txt`

Cada archivo contiene el texto de display con `%` escapado como `\%` (ver Bugs Conocidos).

---

## ⚠️ Bugs conocidos y soluciones

### 1. `%` rompe drawtext SILENCIOSAMENTE (Resuelto Feb 24, 2026)

**El bug más insidioso de todo el pipeline.** Nos costó ~1 hora de debugging.

**Problema:** El carácter `%` en el texto (ej: "50%") hace que el filtro `drawtext` entero no renderice — pero **NO muestra ningún error**. ffmpeg interpreta `%` como inicio de una función de expansión de texto (`%{pts}`, `%{n}`, `%{frame_num}`, etc.). Si no encuentra una función válida después del `%`, el filtro falla silenciosamente. El `drawbox` sí funciona (mismo `enable=`), así que ves **pantalla negra sin texto** — parece que el texto no se generó, pero en realidad es el `%` que rompió el drawtext.

**Síntoma:** Pantalla negra donde debería haber texto. El audio se escucha debajo. Las cards SIN `%` en su texto funcionan perfectamente.

**Solución:** Escapar `%` como `\%` en el contenido del archivo de texto.

```python
escaped_text = card['display_text'].replace('%', '\\%')
with open(card_file, 'w') as f:
    f.write(escaped_text)
```

**Lo que NO funciona (probado):**
- `%%` en textfile → NO renderiza
- `%%` en text= → NO renderiza  
- `%%%%` en text= → NO renderiza
- Solo `\%` funciona, tanto en `textfile=` como en `text=`

**El script ya maneja esto automáticamente.** Sergio puede escribir `%` normal en `overlay-text.md`.

### 2. Guión original ≠ Realidad (Descubierto Feb 24, 2026)

**Problema:** Usar el guión del teleprompter (`guion final.txt`) como fuente para generar `overlay-text.md` produce overlays desalineados. Sergio improvisa al grabar: agrega frases, elimina otras, cambia el orden, repite ideas.

**Síntomas:**
- Texto aparece cuando Sergio habla de otra cosa
- Caracteres faltantes (ej: "$,000" en vez de "$7,000" — la frase del guión no coincidía)
- Cards en negro sin texto (el fuzzy match no encuentra la frase porque nunca se dijo tal cual)

**Solución:** Siempre generar `overlay-text.md` desde `transcription_original.json` (Whisper). Nunca desde el guión.

### 3. Obsidian blockquote conversion

Obsidian convierte automáticamente:
- `>>>` → `> > >` (blockquote triple anidado)
- `===` → `= = =`

El parser acepta ambos formatos. No hay que hacer nada especial.

### 4. ffmpeg sin drawtext (libfreetype)

El ffmpeg de Homebrew estándar (`brew install ffmpeg`) NO incluye el filtro `drawtext` porque no compila con libfreetype.

**Solución:**
```bash
brew uninstall --ignore-dependencies ffmpeg
brew tap homebrew-ffmpeg/ffmpeg
brew install homebrew-ffmpeg/ffmpeg/ffmpeg
```

**Verificar:**
```bash
ffmpeg -filters 2>/dev/null | grep drawtext
# Debe mostrar: T.. drawtext  V->V  Draw text string or text from specified file.
```

Si no aparece, el `drawtext` en el `-vf` produce error y el video no se genera.

---

## Tuning de las text cards

| Quiero... | Cambiar... |
|-----------|-----------|
| Cards más largas en pantalla | `--pad-after 0.5` (0.5s extra después de la frase) |
| Negro aparezca antes | `--pad-before 0.5` (0.5s antes, default 0.3s) |
| Duración mínima fija | `--min-duration 3.0` (nunca menos de 3s en pantalla) |
| Texto más grande | `--fontsize 80` (default 64) |
| Texto más chico | `--fontsize 48` |
| Otra fuente | `--font /path/to/font.ttf` |
| Mejor calidad (más lento) | `--crf 15 --preset medium` |
| Render rápido para probar | `--crf 28 --preset ultrafast` |

---

## Flags

| Flag | Default | Qué hace |
|------|---------|----------|
| `--video` | `6_video_limpio_logos.mp4` | Video de entrada |
| `--output` | `7_video_text_overlay.mp4` | Video de salida |
| `--font` | `/System/Library/Fonts/Helvetica.ttc` | Ruta a la fuente |
| `--fontsize` | `64` | Tamaño de fuente en px |
| `--min-duration` | `0.0` | Segundos mínimos en pantalla (0 = dura lo que la frase) |
| `--pad-before` | `0.3` | Padding antes de la frase (s) |
| `--pad-after` | `0.0` | Padding después de la frase (0 = corta al terminar) |
| `--crf` | `18` | Calidad de video (menor = mejor, 18 ≈ visualmente lossless) |
| `--preset` | `fast` | Preset de encoding ffmpeg |
| `--dry-run` | — | Solo muestra detecciones, no genera nada |
| `--print-cmd` | — | Genera el `.sh` e imprime, no ejecuta |

---

## Archivos involucrados

```
$VIDEO/
├── fuente/
│   ├── transcription/
│   │   ├── transcription_original.json   ← INPUT (word-level Whisper, del Paso 5)
│   │   └── overlay-text.md               ← Transcripción con marcas >>> (Sergio edita)
│   └── video/
│       ├── 6_video_limpio_logos.mp4       ← Video de entrada (con logos del Paso 6)
│       └── 7_video_text_overlay.mp4       ← OUTPUT — Video con text cards
└── tmp/
    ├── text_overlay_cmd.sh                ← Comando ffmpeg generado
    └── text_cards/
        ├── card_000.txt                   ← Texto escapado de cada card
        ├── card_001.txt
        └── ...
```

---

## Dependencias

- `ffmpeg` con `--enable-libfreetype` — filtros `drawbox` + `drawtext`
- `python3` — parsing de overlay-text.md, fuzzy matching, generación de comandos
- Librería estándar: `difflib.SequenceMatcher` (no requiere pip install)
- Librería estándar: `json`, `re`, `os`, `subprocess`, `argparse`
