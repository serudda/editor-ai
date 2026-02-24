# Paso 7 — Text Overlay (Black Cards)

**Problema:** En ciertos momentos del video, Sergio quiere interrumpir la imagen con un fondo negro completo y mostrar una frase en texto blanco centrado — estilo Dan Koe. El audio sigue sonando. Funciona especialmente bien con datos duros, afirmaciones fuertes, o frases de impacto.

**Razonamiento:** En vez de hacer esto manualmente en DaVinci (crear clip negro, agregar texto, posicionar, repetir × N), el script lee un archivo markdown donde Sergio marca las frases, calcula timestamps precisos con word-level matching, y genera un solo comando ffmpeg con `drawbox` (fondo negro) + `drawtext` (texto blanco centrado).

**Prerequisito:**
- Paso 5 completado (`transcription_original.json` + `transcription_limpia.md`)
- Paso 6 completado (`6_video_limpio_logos.mp4` como input)
- ffmpeg compilado con `--enable-libfreetype` (necesario para `drawtext`)

---

## Flujo completo

### 1. 🌑 `overlay-text.md` se crea automáticamente

Al correr `text-overlay.py --dry-run`, si `overlay-text.md` no existe, el script lo copia de `transcription_limpia.md` y le agrega instrucciones.

```bash
python3 scripts/text-overlay.py $VIDEO --dry-run
```

### 2. 🎬 Sergio marca frases con `>>>`

Abre `overlay-text.md` en Antigravity y agrega `>>>` debajo de las frases que quiere como text card:

```markdown
[0:32.96 - 0:34.72] (1.8s) Porque me estaba volviendo obsoleto.
>>> Porque me estaba
volviendo obsoleto
```

**Reglas del marcado:**
- `>>>` activa la frase como text card
- El texto después de `>>>` es **EXACTAMENTE** lo que aparece en pantalla
- Saltos de línea = saltos de línea en pantalla
- Sergio puede editar el texto de display libremente (mayúsculas, signos, abreviaciones)
- El script busca ese texto en la transcripción word-level para el timing (fuzzy matching, threshold 0.5)

### 3. Bloques continuos con `===`

Para varias frases seguidas donde el negro NO desaparece entre ellas:

```markdown
===
>>> El 50% de los trabajos de oficina
van a desaparecer en menos de 5 años
>>> y no lo digo yo, lo dice
Darío Amodei, el CEO de Antropic
===
```

- `===` abre y cierra un bloque
- Cada `>>>` dentro es un cambio de texto (el negro se mantiene)
- El script ajusta tiempos para que no haya gaps entre cards del mismo bloque

| Situación | Usar |
|-----------|------|
| Frase de impacto aislada | Card suelta (`>>>` sin `===`) |
| Dato + fuente seguidos | Bloque `===` |
| Ráfaga de datos (3+ frases) | Bloque `===` |

### 4. 🌑 Sinistra corre dry-run

```bash
python3 scripts/text-overlay.py $VIDEO --dry-run
```

Verificar: timestamps correctos, duraciones razonables, fuente dice `word-level`.

### 5. 🎬 Sergio corre el render

```bash
python3 scripts/text-overlay.py $VIDEO
```

### 6. 🎬 Sergio revisa

```bash
open $VIDEO/fuente/video/7_video_text_overlay.mp4
```

---

## Timing de las cards

```
start = timestamp_primera_palabra - pad_before (0.3s)
end   = timestamp_última_palabra + pad_after (0.0s)
```

- **pad_after = 0:** La card desaparece al terminar la frase. Más dinámico.
- **min_duration = 0:** Dura lo que dura la frase. Si es corta, Sergio escoge frases más largas.

**Fallback para timestamps:**
1. Buscar `display_text` en word-level → más preciso
2. Buscar `segment_text` en word-level
3. Timestamps del segmento Whisper como último recurso

---

## Implementación técnica

Cada card genera dos filtros ffmpeg en `-vf`:

```
drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='between(t,START,END)'
drawtext=fontfile=FONT:textfile=CARD_FILE:fontcolor=white:fontsize=SIZE:x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,START,END)'
```

| Filtro | Función |
|--------|---------|
| `drawbox` | Fondo negro full screen |
| `drawtext` | Texto blanco centrado horizontal y vertical |
| `enable='between(t,S,E)'` | Activa solo entre timestamps S y E |
| `textfile=` | Lee texto de archivo externo (maneja newlines nativamente) |

Archivos de texto en `$VIDEO/tmp/text_cards/card_NNN.txt`, uno por card.

---

## ⚠️ Bugs conocidos

### 1. `%` rompe drawtext silenciosamente (Resuelto)

`%` en el texto hace que `drawtext` no renderice sin error. ffmpeg lo interpreta como función (`%{pts}`, etc.).

**Solución:** El script reemplaza `%` por `％` (fullwidth U+FF05). Se ve igual en pantalla.

**Lo que NO funciona:** `%%`, `%%%%`, `\%` en text=. Solo `％` funciona en ambos modos.

### 2. Newline muestra cuadrito con Source Serif (Pendiente)

`textfile=` con Source Serif muestra □ en los saltos de línea. Helvetica no tiene este problema.

**Opciones si aparece:**
- Usar otra fuente
- Poner todo en una sola línea
- Cambiar a `text=` con `\\n` (más frágil)

### 3. ffmpeg sin drawtext

El ffmpeg estándar de Homebrew NO incluye `drawtext`.

```bash
brew uninstall --ignore-dependencies ffmpeg
brew tap homebrew-ffmpeg/ffmpeg
brew install homebrew-ffmpeg/ffmpeg/ffmpeg
```

Verificar: `ffmpeg -filters 2>/dev/null | grep drawtext`

---

## Tuning

| Quiero... | Cambiar... |
|-----------|-----------|
| Cards más largas en pantalla | `--pad-after 0.5` |
| Negro aparezca antes | `--pad-before 0.5` |
| Duración mínima fija | `--min-duration 3.0` |
| Texto más grande / chico | `--fontsize 80` / `--fontsize 48` |
| Otra fuente | `--font /path/to/font.ttf` |
| Mejor calidad (más lento) | `--crf 15 --preset medium` |
| Render rápido para probar | `--crf 28 --preset ultrafast` |

---

## Flags

| Flag | Default | Qué hace |
|------|---------|----------|
| `--video` | `6_video_limpio_logos.mp4` | Video de entrada |
| `--output` | `7_video_text_overlay.mp4` | Video de salida |
| `--font` | `recursos/fuentes/default.ttf` | Ruta a la fuente (Source Serif Bold) |
| `--fontsize` | `64` | Tamaño de fuente en px |
| `--min-duration` | `0.0` | Segundos mínimos en pantalla |
| `--pad-before` | `0.3` | Padding antes de la frase (s) |
| `--pad-after` | `0.0` | Padding después de la frase (s) |
| `--crf` | `18` | Calidad de video |
| `--preset` | `fast` | Preset de encoding |
| `--dry-run` | — | Solo muestra detecciones |

---

## Archivos involucrados

```
$VIDEO/
├── fuente/
│   ├── transcription/
│   │   ├── transcription_original.json   ← Word-level Whisper (Paso 5)
│   │   ├── transcription_limpia.md       ← Base legible (Paso 5)
│   │   └── overlay-text.md               ← Copia de limpia + marcas >>> (Sergio edita)
│   └── video/
│       ├── 6_video_limpio_logos.mp4       ← Input (con logos)
│       └── 7_video_text_overlay.mp4       ← Output
└── tmp/
    └── text_cards/
        └── card_NNN.txt                   ← Texto de cada card
```

---

## Dependencias

- `ffmpeg` con `--enable-libfreetype` — filtros `drawbox` + `drawtext`
- `python3` — parsing, fuzzy matching, generación de comandos
