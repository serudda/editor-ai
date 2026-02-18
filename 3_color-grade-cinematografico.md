# Color grade cinematográfico (tono cálido + look profesional)

**Problema:** El video se ve "plano" — los colores son correctos técnicamente, pero no tienen ese look cinematográfico que se ve en videos profesionales de YouTube. Los YouTubers pro usan filtros físicos en el lente (Black Pro-Mist, variable ND) y/o LUTs en post-producción para darle ese toque. Además, en este video hay un reflejo sutil del teleprompter que queremos disimular.

**Razonamiento:** En vez de usar un LUT genérico (que suelen ser demasiado agresivos — "filtro sepia" que todo lo pone naranja, "filtro frío" que todo lo pone azul), construimos un color grade por capas. Cada capa hace algo específico y sutil. La suma de todas da el look cinematográfico sin que ninguna individualmente sea obvia.

**¿Qué hace que un video se vea "cine" vs "video casero"?**

1. **Negros levantados:** En cine los negros no son puro negro (#000000). Tienen un leve gris/color. Esto da un look "faded" orgánico. Los videos caseros tienen negros aplastados (crushed blacks) que se ven duros.
2. **Highlights comprimidos:** En cine los blancos no son puro blanco. Se comprimen para que nada "explote" de brillo. Bonus: esto disimula reflejos no deseados (como el del teleprompter).
3. **Curva S suave:** Más contraste en midtonos, menos en extremos. Da profundidad sin ser agresivo.
4. **Teal en sombras, naranja/warm en midtonos:** El clásico "teal & orange" del cine. Funciona porque la piel humana es cálida (naranja) y al poner las sombras en el color complementario (teal/cian), la piel resalta naturalmente.
5. **Saturación ligeramente elevada:** Colores más vivos pero sin parecer un filtro de Instagram.
6. **Viñeta:** Oscurece sutilmente los bordes del frame, dirigiendo la atención al centro (donde está el sujeto). Es un truco que se usa en cine desde siempre — los lentes antiguos lo hacían naturalmente.

**Comando:**

```bash
ffmpeg -i fuente/video/video.mp4 \
  -vf "
    curves=
      master='0/0.04 0.25/0.22 0.5/0.50 0.75/0.73 1/0.92':
      red='0/0.04 0.5/0.52 1/0.93':
      green='0/0.03 0.5/0.50 1/0.92':
      blue='0/0.06 0.5/0.49 1/0.90',
    colorbalance=
      rs=0.03:gs=-0.02:bs=-0.04:
      rm=0.05:gm=0.01:bm=-0.02:
      rh=-0.03:gh=-0.01:bh=0.02,
    eq=saturation=1.1:contrast=1.02,
    vignette=PI/6
  " \
  -c:v libx264 -crf 18 -preset medium \
  -c:a copy \
  -y fuente/video/video_final.mp4
```

**Desglose de cada filtro aplicado:**

#### Filtro 1: `curves` — La columna vertebral del grade

El filtro `curves` permite definir puntos en una curva de tono (como las curvas de Photoshop/Lightroom). Cada punto es `input/output` — "cuando el valor original es X, conviértelo a Y".

**Canal master (brillo general):**

| Punto       | Qué hace                                                                                                                                                                                                      |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `0/0.04`    | **Levantar negros.** El negro puro (0) se convierte en 0.04 (~4% de gris). Las sombras más oscuras nunca llegan a negro total. Esto es el look "faded" cinematográfico.                                       |
| `0.25/0.22` | Las sombras medias bajan ligeramente → más contraste en zona oscura (parte baja de la curva S).                                                                                                               |
| `0.5/0.50`  | Midtonos intactos — el punto de anclaje. No movemos el centro.                                                                                                                                                |
| `0.75/0.73` | Highlights medios bajan ligeramente → compresión suave del rango alto.                                                                                                                                        |
| `1/0.92`    | **Comprimir highlights.** El blanco puro (1.0) se convierte en 0.92. Nada llega a ser blanco total. Esto disimula el reflejo del teleprompter y da el look "cinematográfico" donde los highlights son suaves. |

**Canal rojo:**

| Punto      | Qué hace                                                                                                                            |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `0/0.04`   | Rojo en las sombras — empuja las sombras hacia tonos ligeramente cálidos en vez de gris neutro.                                     |
| `0.5/0.52` | **Midtonos +rojo.** Sube el rojo un 2% en tonos medios. Esto calienta la piel (Sergio se ve "vivo", no pálido). Sutil pero crucial. |
| `1/0.93`   | Highlights comprimen el rojo — evita que las zonas brillantes se vean anaranjadas.                                                  |

**Canal verde:**

| Punto      | Qué hace                                                        |
| ---------- | --------------------------------------------------------------- |
| `0/0.03`   | Sombras casi neutras en verde.                                  |
| `0.5/0.50` | Midtonos neutros — no tocamos el verde para no alterar la piel. |
| `1/0.92`   | Highlights comprimen verde igual que los demás canales.         |

**Canal azul:**

| Punto      | Qué hace                                                                                                                                                                                              |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `0/0.06`   | **Azul/teal en sombras.** Es el punto más alto de los 3 canales en sombras. Esto empuja las zonas oscuras hacia el teal/cian — el complemento de la piel cálida. Es el "teal & orange" look del cine. |
| `0.5/0.49` | Midtonos -1% azul — sutilmente más cálidos (menos azul = más cálido).                                                                                                                                 |
| `1/0.90`   | Highlights comprimen más el azul — las zonas brillantes son ligeramente cálidas.                                                                                                                      |

#### Filtro 2: `colorbalance` — Ajuste fino por zona de luminosidad

Después de las curvas, este filtro hace un ajuste fino de color separado por sombras (s), midtonos (m) y highlights (h).

| Parámetro  | Valor             | Qué hace                                                                                        |
| ---------- | ----------------- | ----------------------------------------------------------------------------------------------- |
| `rs=0.03`  | +red shadows      | Calienta las sombras (complementa el teal del filtro anterior)                                  |
| `gs=-0.02` | -green shadows    | Reduce verde en sombras → empuja más hacia magenta/cálido                                       |
| `bs=-0.04` | -blue shadows     | Reduce azul en sombras → más cálido (trabaja con el teal de curves para un balance)             |
| `rm=0.05`  | +red midtones     | **El más importante.** Calienta los midtonos → la piel se ve viva y saludable                   |
| `gm=0.01`  | +green midtones   | Toque mínimo de verde para que no se vea todo rojo                                              |
| `bm=-0.02` | -blue midtones    | Reduce azul en midtonos → refuerza la calidez                                                   |
| `rh=-0.03` | -red highlights   | Enfría ligeramente los highlights → evita que los brillos se vean naranja                       |
| `gh=-0.01` | -green highlights | Sutil                                                                                           |
| `bh=0.02`  | +blue highlights  | Toque de azul/frío en highlights → contraste de temperatura (warm shadows/mid, cool highlights) |

**La lógica de temperatura por zonas:**

- Sombras: teal + warm (profundidad con color)
- Midtonos: warm (piel viva)
- Highlights: ligeramente cool (contraste de temperatura, look profesional)

Este contraste warm/cool es exactamente lo que hacen los coloristas profesionales. No es "todo warm" ni "todo cool" — es la tensión entre ambos lo que da el look cinematográfico.

#### Filtro 3: `eq` — Saturación y contraste global

| Parámetro        | Valor           | Qué hace                                                                                                   |
| ---------------- | --------------- | ---------------------------------------------------------------------------------------------------------- |
| `saturation=1.1` | +10% saturación | Colores ligeramente más vivos. Suficiente para que resalten, no tanto para parecer filtro de Instagram.    |
| `contrast=1.02`  | +2% contraste   | Refuerzo mínimo de contraste global. Las curvas ya manejan el contraste principal; esto es un nudge final. |

#### Filtro 4: `vignette` — Foco visual

| Parámetro | Valor               | Qué hace                                                                                                                                                                                |
| --------- | ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `PI/6`    | Ángulo de la viñeta | Oscurece gradualmente desde el centro hacia los bordes. `PI/6` = suave, apenas perceptible. Los bordes del frame se oscurecen ~15-20%. Dirige la mirada al centro donde está el sujeto. |

**¿Por qué este orden de filtros importa?**

1. **Curves primero:** Establece la base tonal — levanta negros, comprime highlights, define la estructura de color.
2. **Colorbalance segundo:** Ajusta fino sobre la base que ya crearon las curvas. Si lo pusieras primero, las curvas podrían deshacer tu trabajo.
3. **Eq tercero:** Saturación y contraste global como toque final sobre los colores ya establecidos.
4. **Vignette último:** Se aplica sobre la imagen ya corregida en color. Si fuera antes, el oscurecimiento de bordes interactuaría con los filtros de color de formas impredecibles.

**Sobre el reflejo del teleprompter:**

La compresión de highlights (`1/0.92` en curves) no elimina el reflejo, pero lo **atenúa significativamente**. Al limitar que ningún píxel llegue a blanco puro, el destello del teleprompter pierde intensidad y se integra mejor con la imagen. Para eliminarlo completamente se necesitaría tracking + inpainting por IA (Runway, After Effects), lo cual es otra liga.

**Tuning del grade:**

Si quieres ajustar el look para futuros videos:

| Quiero...           | Cambiar...                                                    |
| ------------------- | ------------------------------------------------------------- |
| Más cálido          | `rm=0.07` (subir rojo midtonos)                               |
| Menos cálido        | `rm=0.03` (bajar rojo midtonos)                               |
| Más "faded"/cine    | `0/0.06` en master (levantar más los negros)                  |
| Más contraste       | `0.25/0.18` y `0.75/0.78` en master (S-curve más pronunciada) |
| Más teal en sombras | `0/0.08` en blue channel                                      |
| Menos viñeta        | `PI/4` (más abierta) o quitar el filtro                       |
| Más saturación      | `saturation=1.15`                                             |
| Sin viñeta          | Eliminar `,vignette=PI/6` del comando                         |

---

## Resumen de Archivos Generados

| Archivo                               | Paso | Tamaño                            |
| ------------------------------------- | ---- | --------------------------------- |
| `fuente/audio/audio_extraido.aac`     | 1    | 30 MB                             |
| `fuente/audio/audio_stereo_v2.wav`    | 2    | 280 MB                            |
| `fuente/video/video_sincronizado.mp4` | 4    | 8.8 GB                            |
| `fuente/video/video_denoised.mp4`     | 5    | ~1.5 GB (re-encoded H.264 CRF 18) |
| `fuente/video/video_final.mp4`        | 6    | ~1.5 GB (re-encoded H.264 CRF 18) |

Archivos temporales (en `/tmp/`, se pueden borrar):

- `/tmp/sony_chunk.wav` — chunk de Sony para correlación
- `/tmp/sm7b_chunk.wav` — chunk de SM7B para correlación

## Dependencias

- `ffmpeg` — manipulación de audio/video
- `python3` + `numpy` + `scipy` — cross-correlation para detección de offset
