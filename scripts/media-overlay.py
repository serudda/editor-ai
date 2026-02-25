#!/usr/bin/env python3
"""
Paso 7 — Media Overlay

Lee `fuente/transcription/overlay-media.md` del folder del video para saber
qué imágenes o videos superponer fullscreen mientras la voz sigue sonando.

Requiere ffmpeg.

Uso:
  python3 media-overlay.py <carpeta-del-video>
  python3 media-overlay.py <carpeta-del-video> --dry-run

Documentación completa: ../7_media-overlay.md
"""

import argparse
import json
import os
import re
import subprocess
import sys
from difflib import SequenceMatcher


def parse_timestamp(ts):
    """Convertir MM:SS.xx o H:MM:SS.xx a segundos."""
    parts = ts.strip().split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    return 0.0


def format_time(seconds):
    m, s = divmod(seconds, 60)
    m = int(m)
    if s == int(s):
        return f"{m}:{int(s):02d}"
    return f"{m}:{s:05.2f}"


def find_word_timestamp(target_phrase, words, segment_start=None, segment_end=None):
    """Busca una palabra o frase en la transcripción word-level y retorna (start, end).
    
    Soporta:
    - Una sola palabra: @"confirmaron" → match fuzzy de la mejor palabra
    - Frase multi-palabra: @"El 50" → busca palabras consecutivas, retorna start de la primera
    
    Si se proporcionan segment_start/segment_end, limita la búsqueda a ese rango.
    """
    # Filtrar palabras al rango del segmento
    filtered = []
    for i, w in enumerate(words):
        if segment_start is not None and w['start'] < segment_start - 1.0:
            continue
        if segment_end is not None and w['end'] > segment_end + 1.0:
            continue
        filtered.append((i, w))
    
    if not filtered:
        return None, None
    
    # Tokenizar la frase objetivo
    target_tokens = re.findall(r'\w+', target_phrase.lower())
    if not target_tokens:
        return None, None
    
    if len(target_tokens) == 1:
        # Búsqueda de palabra individual (fuzzy)
        target_clean = target_tokens[0]
        best_score = 0
        best_start = None
        best_end = None
        
        for _, w in filtered:
            word_clean = w['word'].lower().strip(' .,!?¿¡"\'')
            score = SequenceMatcher(None, target_clean, word_clean).ratio()
            if score > best_score:
                best_score = score
                best_start = w['start']
                best_end = w['end']
        
        if best_score < 0.6:
            return None, None
        return best_start, best_end
    
    # Búsqueda de frase multi-palabra (ventana deslizante)
    window_size = len(target_tokens)
    best_score = 0
    best_start = None
    best_end = None
    
    for i in range(len(filtered) - window_size + 1):
        window = filtered[i:i + window_size]
        window_tokens = [w['word'].lower().strip(' .,!?¿¡"\'') for _, w in window]
        
        # Score: promedio de similarity por posición
        total_score = 0
        for t_tok, w_tok in zip(target_tokens, window_tokens):
            total_score += SequenceMatcher(None, t_tok, w_tok).ratio()
        avg_score = total_score / window_size
        
        if avg_score > best_score:
            best_score = avg_score
            best_start = window[0][1]['start']
            best_end = window[-1][1]['end']
    
    if best_score < 0.6:
        return None, None
    
    return best_start, best_end


def parse_duration_str(s):
    """Parsear duración como '5s' o '10s' a float."""
    s = s.strip().lower()
    if s.endswith('s'):
        return float(s[:-1])
    return float(s)


def get_media_duration(filepath):
    """Obtener duración de un archivo multimedia con ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", filepath
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return float(result.stdout.strip())


def is_video_file(filepath):
    """Determinar si un archivo es video (vs imagen)."""
    ext = os.path.splitext(filepath)[1].lower()
    return ext in ['.mp4', '.mov', '.mkv', '.avi', '.webm']


def get_video_info(video_path):
    """Obtener resolución y framerate del video."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    info = json.loads(result.stdout)
    
    video_stream = None
    for s in info.get('streams', []):
        if s['codec_type'] == 'video' and video_stream is None:
            video_stream = s
    
    width = int(video_stream['width']) if video_stream else 1920
    height = int(video_stream['height']) if video_stream else 1080
    
    fps_str = video_stream.get('r_frame_rate', '30/1') if video_stream else '30/1'
    if '/' in fps_str:
        num, den = fps_str.split('/')
        fps = float(num) / float(den)
    else:
        fps = float(fps_str)
    
    return {'width': width, 'height': height, 'fps': fps}


def parse_overlay_media_md(filepath):
    """Parsear overlay-media.md y extraer medios marcados con >>>."""
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    overlays = []
    current_segment_text = None
    current_start = None
    current_end = None
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Parsear línea de segmento
        ts_match = re.match(r'\[(\d+:\d+(?:\.\d+)?)\s*-\s*(\d+:\d+(?:\.\d+)?)\]\s*(?:\(\d+\.?\d*s\)\s*)?(.*)', line)
        if ts_match:
            current_start = parse_timestamp(ts_match.group(1))
            current_end = parse_timestamp(ts_match.group(2))
            current_segment_text = ts_match.group(3).strip()
            continue
        
        # Parsear marca >>> o > > >
        is_marker = stripped.startswith('>>>') or stripped.startswith('> > >')
        if is_marker:
            if current_segment_text is None:
                continue
            
            marker_text = stripped
            if marker_text.startswith('> > >'):
                marker_text = marker_text[5:].strip()
            else:
                marker_text = marker_text[3:].strip()
            
            # Parsear: archivo.ext | @"palabra" | duración (opcional)
            parts = [p.strip() for p in marker_text.split('|')]
            if len(parts) < 2:
                print(f"⚠️  Línea {i+1}: formato incorrecto, se espera 'archivo.ext | @\"palabra\"'")
                continue
            
            media_file = parts[0]
            
            # Extraer palabra del @"..."
            word_match = re.match(r'@["\u201c](.+?)["\u201d]', parts[1])
            if not word_match:
                print(f"⚠️  Línea {i+1}: no se encontró @\"palabra\" en '{parts[1]}'")
                continue
            
            target_word = word_match.group(1)
            
            # Duración opcional (3er parámetro)
            duration_override = None
            if len(parts) >= 3:
                try:
                    duration_override = parse_duration_str(parts[2])
                except ValueError:
                    print(f"⚠️  Línea {i+1}: duración inválida '{parts[2]}', ignorando")
            
            overlays.append({
                'media_file': media_file,
                'target_word': target_word,
                'duration_override': duration_override,
                'segment_text': current_segment_text,
                'segment_start': current_start,
                'segment_end': current_end,
                'line_num': i + 1,
            })
    
    return overlays


def main():
    parser = argparse.ArgumentParser(description="Paso 7 — Media Overlay")
    parser.add_argument("video_dir", help="Carpeta del video")
    parser.add_argument("--video", default="6_video_limpio_logos.mp4", help="Video de entrada (default: 6_video_limpio_logos.mp4)")
    parser.add_argument("--output", default="7_video_media_overlay.mp4", help="Video de salida")
    parser.add_argument("--fade", type=float, default=0.3, help="Fade in/out en segundos (default: 0.3)")
    parser.add_argument("--crf", type=int, default=18, help="Calidad CRF (default: 18)")
    parser.add_argument("--preset", default="fast", help="Preset de encoding (default: fast)")
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar detecciones")
    
    args = parser.parse_args()
    
    video_dir = os.path.expanduser(args.video_dir)
    video_path = os.path.join(video_dir, "fuente", "video", args.video)
    overlay_md = os.path.join(video_dir, "fuente", "transcription", "overlay-media.md")
    transcription_json = os.path.join(video_dir, "fuente", "transcription", "transcription_original.json")
    media_dir = os.path.join(video_dir, "fuente", "overlays")
    output_path = os.path.join(video_dir, "fuente", "video", args.output)
    
    if not os.path.isfile(video_path):
        print(f"❌ Video no encontrado: {video_path}")
        sys.exit(1)
    
    if not os.path.isfile(overlay_md):
        # Crear desde transcription_limpia.md
        limpia_md = os.path.join(video_dir, "fuente", "transcription", "transcription_limpia.md")
        if os.path.isfile(limpia_md):
            header = """# Media Overlay
#
# Copiado de transcription_limpia.md — marca medios con >>>.
#
# INSTRUCCIONES:
# Para superponer una imagen o video fullscreen (tu voz sigue sonando),
# agrega >>> debajo del segmento.
#
# Formato: >>> archivo.ext | @"palabra" | duración (opcional)
#
# - archivo.ext = imagen o video en fuente/overlays/
# - @"palabra" = aparece cuando se dice esa palabra
# - duración = opcional, ej: 5s (default: hasta fin del segmento, o duración del video)
#
# El audio del video base sigue sonando (el audio del overlay se ignora).
#
# Ejemplo:
# [4:37.35 - 4:57.15] (19.8s) en 2022 la IA no podía hacer una multiplicación...
# >>> ai-timeline.png | @"multiplicación" | 19s
#
# [3:22.11 - 3:44.25] (22.1s) OpenAI confirmaron en su documentación oficial...
# >>> screenshot-codex.png | @"documentación" | 5s

"""
            with open(limpia_md, 'r') as f:
                limpia_lines = f.readlines()
            
            content_lines = []
            past_header = False
            for line in limpia_lines:
                if not past_header and line.startswith('#'):
                    continue
                if not past_header and line.strip() == '':
                    continue
                past_header = True
                content_lines.append(line)
            
            with open(overlay_md, 'w') as f:
                f.write(header)
                f.writelines(content_lines)
            
            print(f"📋 overlay-media.md creado desde transcription_limpia.md")
            print(f"   → Abrilo y marcá medios con >>> antes de renderizar\n")
            if args.dry_run:
                return
        else:
            print(f"❌ No existe overlay-media.md ni transcription_limpia.md")
            sys.exit(1)
    
    if not os.path.isfile(transcription_json):
        print(f"❌ transcription_original.json no encontrado: {transcription_json}")
        sys.exit(1)
    
    # Cargar transcripción word-level
    with open(transcription_json) as f:
        transcription = json.load(f)
    words = transcription.get('words', [])
    
    # Parsear marcas
    overlays = parse_overlay_media_md(overlay_md)
    
    print(f"📹 Video: {video_path}")
    print(f"📋 Overlay: {overlay_md}")
    print(f"📤 Output: {output_path}")
    print(f"🖼️  Media dir: {media_dir}")
    print(f"⚙️  Fade: {args.fade}s")
    print(f"\n📊 {len(overlays)} media overlays encontrados\n")
    
    if not overlays:
        print("⚠️  No hay medios marcados con >>>")
        # Si no hay overlays, copiar video de entrada a salida
        if not args.dry_run:
            import shutil
            shutil.copy2(video_path, output_path)
            print(f"📋 Sin overlays — copiado input a {output_path}")
        return
    
    # Obtener info del video base
    base_info = get_video_info(video_path)
    
    # Resolver timestamps y validar archivos
    all_valid = True
    for ov in overlays:
        # Buscar timestamp de la palabra
        word_start, word_end = find_word_timestamp(
            ov['target_word'], words,
            segment_start=ov['segment_start'],
            segment_end=ov['segment_end']
        )
        
        if word_start is not None:
            ov['start'] = word_start
            ov['source'] = 'word-level'
        else:
            ov['start'] = ov['segment_start']
            ov['source'] = 'segment fallback'
            print(f"⚠️  Línea {ov['line_num']}: palabra \"{ov['target_word']}\" no encontrada, usando inicio del segmento")
        
        # Verificar que el archivo existe
        media_path = os.path.join(media_dir, ov['media_file'])
        if os.path.isfile(media_path):
            ov['media_path'] = media_path
            ov['is_video'] = is_video_file(media_path)
            
            if ov['is_video']:
                ov['media_duration'] = get_media_duration(media_path)
            else:
                ov['media_duration'] = None
        else:
            ov['media_path'] = None
            ov['is_video'] = False
            ov['media_duration'] = None
            all_valid = False
            print(f"❌ Línea {ov['line_num']}: archivo no encontrado: {media_path}")
        
        # Calcular duración final del overlay
        if ov['duration_override'] is not None:
            ov['duration'] = ov['duration_override']
        elif ov['is_video'] and ov['media_duration']:
            ov['duration'] = ov['media_duration']
        else:
            # Default: hasta el final del segmento
            ov['duration'] = ov['segment_end'] - ov['start']
        
        ov['end'] = ov['start'] + ov['duration']
    
    # Mostrar resumen
    for ov in overlays:
        status = "✅" if ov['media_path'] else "❌"
        media_type = "🎥" if ov['is_video'] else "🖼️"
        print(f"   {status} {media_type} [{format_time(ov['start'])} - {format_time(ov['end'])}] ({ov['duration']:.1f}s) [{ov['source']}]")
        print(f"      → {ov['media_file']} | @\"{ov['target_word']}\"")
        print()
    
    if args.dry_run:
        print("🏁 Dry run — no se generó video.")
        return
    
    if not all_valid:
        print("❌ Hay archivos faltantes. Corrige antes de renderizar.")
        sys.exit(1)
    
    # Construir comando ffmpeg con filter_complex
    # Cada media es un input adicional
    inputs = ["-i", video_path]
    for ov in overlays:
        inputs += ["-i", ov['media_path']]
        # Si es video overlay, también necesitamos loop para imágenes
    
    filter_parts = []
    current_stream = "[0:v]"
    
    for idx, ov in enumerate(overlays):
        input_idx = idx + 1  # 0 es el video base
        start = ov['start']
        end = ov['end']
        
        if ov['is_video']:
            # Video overlay: scale to fill, trim to duration, overlay fullscreen
            filter_parts.append(
                f"[{input_idx}:v]scale={base_info['width']}:{base_info['height']}:"
                f"force_original_aspect_ratio=decrease,"
                f"pad={base_info['width']}:{base_info['height']}:(ow-iw)/2:(oh-ih)/2,"
                f"setpts=PTS-STARTPTS+{start}/TB"
                f"[media{idx}]"
            )
        else:
            # Image overlay: scale to fill, loop for duration
            filter_parts.append(
                f"[{input_idx}:v]scale={base_info['width']}:{base_info['height']}:"
                f"force_original_aspect_ratio=decrease,"
                f"pad={base_info['width']}:{base_info['height']}:(ow-iw)/2:(oh-ih)/2,"
                f"format=rgba"
                f"[media{idx}]"
            )
        
        # Overlay on current stream
        filter_parts.append(
            f"{current_stream}[media{idx}]overlay=0:0:"
            f"enable='between(t,{start:.2f},{end:.2f})'"
            f"[v{idx}]"
        )
        current_stream = f"[v{idx}]"
    
    filter_complex = ";".join(filter_parts)
    
    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", current_stream,
        "-map", "0:a",
        "-c:v", "libx264", "-crf", str(args.crf), "-preset", args.preset,
        "-c:a", "copy",
        output_path
    ]
    
    print(f"🎬 Aplicando {len(overlays)} media overlays...")
    print(f"📤 Output: {output_path}\n")
    
    result = subprocess.run(cmd)
    
    if result.returncode != 0:
        print(f"\n❌ Error (código {result.returncode})")
        sys.exit(1)
    
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\n✅ Listo: {output_path} ({size_mb:.0f} MB)")


if __name__ == "__main__":
    main()
