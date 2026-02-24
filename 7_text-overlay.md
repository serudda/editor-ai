# Paso 7 — Text Overlay (Black Card)

**Problema:** En ciertos momentos del video, Sergio quiere interrumpir la imagen con un fondo negro completo y mostrar una frase en texto blanco centrado — estilo Dan Koe. El audio sigue sonando.

**Solución:** Sinistra genera la transcripción legible, Sergio marca frases con `>>>`, el script calcula timestamps word-level y genera el comando ffmpeg con `drawbox` + `drawtext`.

**Prerequisito:** 
- Paso 5 completado (`transcription_original.json` debe existir con word-level timestamps)
- Paso 6 completado (`6_video_limpio_logos.mp4` como input)
- ffmpeg compilado con `--enable-libfreetype` (necesario para `drawtext`)

---

## Flujo completo

### 1. 🌑 Sinistra genera `overlay-text.md`

Lee `transcription_original.json` (Whisper word-level) y genera un archivo legible con la transcripción segmentada por frases, con timestamps.

**Archivo:** `fuente/transcription/overlay-text.md`

**⚠️ FUENTE DE VERDAD:** Siempre es la transcripción Whisper del video limpio, NUNCA el guión original del teleprompter. Sergio improvisa al grabar — agrega, elimina y repite frases. El guión no refleja lo que realmente se dice en el video.

### 2. 🎬 Sergio marca frases con `>>>`

Abre `overlay-text.md` en Obsidian y agrega `>>>` debajo de las frases que quiere como text card:

```markdown
[0:32.96 - 0:34.72] Porque me estaba volviendo obsoleto.
>>> Porque me estaba
volviendo obsoleto

[7:18.93 - 7:21.93] yo personalmente te recomiendo Cloudy son 20 dólares al mes
>>> Claude: $20 al mes
```

**Reglas:**
- `>>>` marca la frase como text card
- El texto después de `>>>` es EXACTAMENTE lo que aparece en pantalla
- Saltos de línea = saltos de línea en pantalla
- Si no tiene `>>>`, se ignora
- Sergio puede editar el texto de display como quiera (mayúsculas, signos, abreviaciones)
- ⚠️ Obsidian convierte `>>>` en `> > >` automáticamente (blockquote). **El parser acepta ambos formatos.**

### 3. Bloques continuos con `===`

Para varias frases seguidas donde el negro NO debe desaparecer entre ellas (el fondo se mantiene, solo cambia el texto):

```markdown
[0:00.00 - 0:16.86] El 50% de los trabajos de oficina van a desaparecer...
===
>>> El 50% de los trabajos de oficina
van a desaparecer en menos de 5 años
>>> y no lo digo yo, lo dice
Darío Amodei, el CEO de Antropic
>>> una de las empresas más importantes
de inteligencia artificial del mundo
===
```

- `===` abre y cierra un bloque
- Dentro del bloque, cada `>>>` es un cambio de texto
- El script ajusta automáticamente los tiempos para que no haya gaps entre cards del mismo bloque
- Obsidian también convierte `===` en `= = =` — ambos formatos funcionan

### 4. 🌑 Sinistra corre el script (dry-run primero)

```bash
python3 scripts/text-overlay.py $VIDEO --dry-run
```

Verifica que los timestamps, duraciones y textos se vean bien.

### 5. 🎬 Generar comando y renderizar

```bash
# Opción A: generar .sh y revisar antes de correr
python3 scripts/text-overlay.py $VIDEO --print-cmd
# Revisar el .sh, luego:
bash $VIDEO/tmp/text_overlay_cmd.sh

# Opción B: correr directo (genera .sh y ejecuta en un paso)
python3 scripts/text-overlay.py $VIDEO
```

**Output:** `fuente/video/7_video_text_overlay.mp4`

**⚠️ REGLA:** Sinistra NUNCA corre el render directamente — siempre le pasa el comando a Sergio. El timeout de 7 minutos del agente mata procesos largos.

---

## Timing de las cards

```
start = timestamp_primera_palabra - pad_before (0.3s)
end   = max(timestamp_última_palabra + pad_after, start + min_duration)
```

- **min_duration:** 3.0s por defecto (tiempo mínimo para que el cerebro lea)
- **pad_before:** 0.3s (el negro aparece un pelín antes de la palabra)
- **pad_after:** 0.5s (se queda un pelín después)
- Si la frase dura más que min_duration, el speech manda
- **start mínimo:** 0.01s (nunca 0.00 — ver Bugs Conocidos)

El script usa **fuzzy matching** (`SequenceMatcher` con threshold 0.5) para buscar las palabras del display text en la transcripción word-level. Esto tolera diferencias menores entre el texto marcado y lo que Whisper transcribió.

**Cadena de fallback para timestamps:**
1. Buscar el `display_text` (lo que aparece en pantalla) en word-level → más preciso
2. Buscar el `segment_text` (la frase completa del bloque) en word-level
3. Usar timestamps del segmento original como último recurso

---

## Implementación técnica: drawbox + drawtext

Cada text card genera **dos filtros ffmpeg encadenados:**

```
drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='between(t,START,END)'
drawtext=fontfile=FONT:textfile=CARD_FILE:fontcolor=white:fontsize=SIZE:x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,START,END)'
```

- `drawbox` pinta el fondo negro full-screen
- `drawtext` centra el texto horizontal y verticalmente
- Ambos usan el mismo `enable=between(t,...)` para aparecer/desaparecer sincronizados
- Se usa `textfile=` (archivo externo) en vez de `text=` para manejar **newlines nativamente**

Los archivos de texto se generan en `$VIDEO/tmp/text_cards/card_NNN.txt`.

---

## ⚠️ Bugs conocidos y soluciones

### 1. `%` rompe drawtext SILENCIOSAMENTE

**Problema:** El carácter `%` en el texto (ej: "50%") hace que `drawtext` falle sin error. ffmpeg interpreta `%` como inicio de una función de expansión (`%{pts}`, `%{n}`, etc.). Si no encuentra una función válida, el filtro entero no renderiza — pero NO muestra error. El `drawbox` sí funciona, así que ves pantalla negra sin texto.

**Solución:** Escapar `%` como `\%` en el contenido del archivo de texto.

```python
escaped_text = card['display_text'].replace('%', '\\%')
```

**Lo que NO funciona:**
- `%%` → NO funciona (ni en `text=` ni en `textfile=`)
- `%%%%` → NO funciona
- Solo `\%` funciona

**El script ya maneja esto automáticamente.** Sergio puede escribir `%` normal en `overlay-text.md`.

### 2. `textfile=` vs `text=`

**Se usa `textfile=`** porque maneja newlines nativamente. Con `text=` hay que escapar newlines como `\\n` y las capas de escape (Python → bash → ffmpeg) son frágiles.

`textfile=` NO tiene problemas con `enable=` — el bug anterior era causado exclusivamente por el `%` sin escapar.

### 3. Otros caracteres especiales

El script escapa automáticamente en `escape_drawtext()` para cuando se use `text=`:
- `\` → `\\`
- `'` → `'\\''`
- `:` → `\:`
- `;` → `\;`
- `%` → `\%`
- `$` → `\$` (para que bash no lo interprete como variable)

Para `textfile=`, solo se escapa `%` → `\%` en el contenido del archivo.

### 4. Obsidian blockquote conversion

Obsidian convierte automáticamente `>>>` en `> > >` (lo trata como blockquote anidado). El parser acepta ambos formatos. Lo mismo con `===` → `= = =`.

### 5. Guión original ≠ Realidad

**NUNCA** usar el guión del teleprompter como fuente de verdad para el contenido de las cards. Sergio improvisa al grabar. La transcripción Whisper word-level del video limpio es la única fuente confiable.

Síntomas de usar el guión como fuente:
- Texto aparece en momentos donde Sergio habla de otra cosa
- Caracteres faltantes (ej: "$,000" en vez de "$7,000")
- Cards en negro sin texto (fuzzy match no encuentra la frase porque nunca se dijo)

---

## Flags

| Flag | Default | Qué hace |
|------|---------|----------|
| `--video` | `6_video_limpio_logos.mp4` | Video de entrada |
| `--output` | `7_video_text_overlay.mp4` | Video de salida |
| `--font` | `/System/Library/Fonts/Helvetica.ttc` | Ruta a la fuente |
| `--fontsize` | `64` | Tamaño de fuente en px |
| `--min-duration` | `3.0` | Segundos mínimos en pantalla |
| `--pad-before` | `0.3` | Padding antes de la frase (s) |
| `--pad-after` | `0.5` | Padding después de la frase (s) |
| `--crf` | `18` | Calidad de video (menor = mejor) |
| `--preset` | `fast` | Preset de encoding ffmpeg |
| `--dry-run` | — | Solo muestra detecciones, no genera nada |
| `--print-cmd` | — | Genera el `.sh` e imprime, no ejecuta |

---

## Archivos involucrados

```
$VIDEO/
├── fuente/
│   ├── transcription/
│   │   ├── transcription_original.json   ← Word-level timestamps (Whisper)
│   │   └── overlay-text.md               ← Transcripción con marcas >>>
│   └── video/
│       ├── 6_video_limpio_logos.mp4       ← Video de entrada (con logos)
│       └── 7_video_text_overlay.mp4       ← Video con text cards (OUTPUT)
└── tmp/
    ├── text_overlay_cmd.sh                ← Comando ffmpeg generado
    └── text_cards/
        ├── card_000.txt                   ← Texto escapado de cada card
        ├── card_001.txt
        └── ...
```

---

## Requisito: ffmpeg con drawtext

El ffmpeg de Homebrew estándar NO incluye `drawtext` (no compila con libfreetype). Hay que instalar desde el tap especial:

```bash
brew uninstall --ignore-dependencies ffmpeg
brew tap homebrew-ffmpeg/ffmpeg
brew install homebrew-ffmpeg/ffmpeg/ffmpeg
```

Verificar que funciona:
```bash
ffmpeg -filters 2>/dev/null | grep drawtext
# Debe mostrar: T.. drawtext V->V Draw text...
```

---

## Dependencias

- `ffmpeg` con `--enable-libfreetype` — drawbox + drawtext filters
- `python3` — script de parsing, fuzzy matching, y generación de comandos
- Librería estándar: `difflib.SequenceMatcher` para fuzzy matching (no requiere pip install)

---

## Ejemplo completo

```bash
VIDEO=~/Documents/Edicion/Serudda/serudda-videos/2026-02-11_mejor-epoca-para-ti

# 1. Dry run — verificar cards
python3 scripts/text-overlay.py $VIDEO --dry-run

# 2. Generar comando
python3 scripts/text-overlay.py $VIDEO --print-cmd

# 3. Revisar el .sh
cat $VIDEO/tmp/text_overlay_cmd.sh

# 4. Renderizar (Sergio corre esto)
bash $VIDEO/tmp/text_overlay_cmd.sh

# 5. Verificar
open $VIDEO/fuente/video/7_video_text_overlay.mp4
```
