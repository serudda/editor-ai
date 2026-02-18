# Reducir ruido visual (denoising) sin perder nitidez

**Problema:** El lente Sigma 16mm f/1.4 DC genera un desenfoque de fondo hermoso, pero necesita mucha luz. En ambientes oscuros (como este video), el sensor de la Sony A6400 compensa subiendo el ISO, lo que introduce **ruido visual** — puntos/granitos que se ven flotando en la imagen, especialmente en las zonas oscuras y el fondo.

**Por qué no simplemente subir la luz:** Sergio quería un ambiente oscuro intencionalmente para el mood del video. Más luz = menos ruido, pero también mata la estética. La solución es grabar como quieras y limpiar el ruido en post.

**Opciones evaluadas:**

| Filtro        | Tipo                                                            | Resultado                                                        |
| ------------- | --------------------------------------------------------------- | ---------------------------------------------------------------- |
| `nlmeans s=7` | Espacial (compara patches dentro del mismo frame)               | Elimina ruido pero **pierde nitidez** — la imagen queda "lavada" |
| `nlmeans s=4` | Espacial (menos agresivo)                                       | Mejor balance, pero sigue suavizando detalles                    |
| `hqdn3d` ✅   | **Temporal** (compara el mismo píxel entre frames consecutivos) | **Mejor opción** — elimina ruido preservando nitidez             |

**Por qué `hqdn3d` es superior para este caso:**

Los filtros espaciales (como `nlmeans`) miran un frame aislado y promedian píxeles cercanos que se parecen. Esto inevitablemente suaviza detalles finos (pestañas, textura de ropa, pelo) porque no puede distinguir al 100% entre "detalle real" y "ruido".

`hqdn3d` (High Quality 3D Denoiser) trabaja en **3 dimensiones**: X, Y (espacial) + T (tiempo). Compara el mismo píxel a lo largo de varios frames consecutivos. La clave:

- **El ruido es aleatorio** → cambia entre frames. Un píxel ruidoso tiene un valor distinto en cada frame.
- **Los detalles son consistentes** → un borde o textura real tiene el mismo valor en frames consecutivos.
- Al promediar temporalmente, el ruido se cancela y los detalles sobreviven.

Es como tomar varias fotos de lo mismo y promediarlas — el ruido desaparece, la imagen real se refuerza.

**Comando:**

```bash
ffmpeg -i fuente/video_sincronizado.mp4 \
  -vf "hqdn3d=3:3:4:4" \
  -c:v libx264 -crf 18 -preset medium \
  -c:a copy \
  -y fuente/video_denoised.mp4
```

**Ejemplo real:**

```bash
cd ~/Documents/Edicion/Serudda/serudda-videos/2026-02-11_mejor-epoca-para-ti && ffmpeg -i fuente/video_sincronizado.mp4 -vf "hqdn3d=3:3:4:4" -c:v libx264 -crf 18 -preset medium -c:a copy -y fuente/video_denoised.mp4
```

| Flag                   | Qué hace                                                                                            |
| ---------------------- | --------------------------------------------------------------------------------------------------- |
| `-vf "hqdn3d=3:3:4:4"` | Aplica el denoiser 3D. Los 4 valores son: luma_spatial:chroma_spatial:luma_temporal:chroma_temporal |
| `3` (luma_spatial)     | Fuerza de denoising espacial para brillo. 3 = suave (rango 0-25, default 4)                         |
| `3` (chroma_spatial)   | Fuerza espacial para color. 3 = suave                                                               |
| `4` (luma_temporal)    | Fuerza temporal para brillo. 4 = moderada — aquí está la magia, promedia entre frames               |
| `4` (chroma_temporal)  | Fuerza temporal para color. 4 = moderada                                                            |
| `-c:v libx264 -crf 18` | Re-encodea el video con H.264. CRF 18 = calidad visualmente lossless                                |
| `-preset medium`       | Balance entre velocidad de encoding y compresión                                                    |
| `-c:a copy`            | Copia el audio sin tocar (ya está sincronizado del paso 4)                                          |

**Tuning de los parámetros:**

- **Valores más altos** (ej: `hqdn3d=6:6:8:8`) = más agresivo, más suave, puede generar "ghosting" en movimientos rápidos
- **Valores más bajos** (ej: `hqdn3d=2:2:3:3`) = más conservador, deja más grano pero cero artefactos
- **Los valores temporales (3° y 4°) son los más importantes** — son los que limpian el ruido sin matar detalles
- **Ghosting:** Si el sujeto se mueve muy rápido, la promediación temporal puede dejar "fantasmas". Para este video (Sergio sentado hablando) no es problema.

**Nota sobre CRF 18:** Constant Rate Factor controla la calidad del encoding. 0 = lossless, 18 = visualmente idéntico al original, 23 = default, 28+ = se nota la pérdida. Usamos 18 porque ya estamos re-encodeando (no podemos usar `-c:v copy` al aplicar filtros) y queremos mínima pérdida adicional.

**Nota sobre `-c:v copy` vs re-encoding:** A diferencia del paso 4 donde copiamos el video sin tocar, aquí **obligatoriamente** hay que re-encodear porque estamos modificando los píxeles del video. Aplicar un filtro = generar frames nuevos = hay que comprimirlos de nuevo. Por eso CRF 18 es importante — minimiza la pérdida de esa recompresión.

---

## Resumen de Archivos Generados

| Archivo                         | Paso | Tamaño                            |
| ------------------------------- | ---- | --------------------------------- |
| `fuente/audio_extraido.aac`     | 1    | 30 MB                             |
| `fuente/audio_stereo_v2.wav`    | 2    | 280 MB                            |
| `fuente/video_sincronizado.mp4` | 4    | 8.8 GB                            |
| `fuente/video_denoised.mp4`     | 5    | ~1.5 GB (re-encoded H.264 CRF 18) |

Archivos temporales (en `/tmp/`, se pueden borrar):

- `/tmp/sony_chunk.wav` — chunk de Sony para correlación
- `/tmp/sm7b_chunk.wav` — chunk de SM7B para correlación

## Dependencias

- `ffmpeg` — manipulación de audio/video
- `python3` + `numpy` + `scipy` — cross-correlation para detección de offset
