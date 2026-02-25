#!/usr/bin/env python3
"""
Paso 9 — Inserts

Lee `fuente/transcription/overlay-inserts.md` del folder del video para saber
dónde insertar clips. Corta el video base en esos puntos, inserta los
clips completos (con su audio), y concatena todo.

Requiere ffmpeg.

Uso:
  python3 inserts.py <carpeta-del-video>
  python3 inserts.py <carpeta-del-video> --dry-run

Documentación completa: ../9_inserts.md
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


def format_time_ffmpeg(seconds):
    """Formato HH:MM:SS.mmm para ffmpeg."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def find_word_end_timestamp(target_word, words, segment_start=None, segment_end=None):
    """Busca una palabra en la transcripción word-level y retorna word.end.
    
    Si se proporcionan segment_start/segment_end, limita la búsqueda a ese rango.
    Usa fuzzy matching para tolerar diferencias menores.
    """
    target_clean = target_word.lower().strip(' .,!?¿¡"\'')
    
    best_score = 0
    best_end = None
    
    for w in words:
        # Filtrar por rango del segmento si se proporcionó
        if segment_start is not None and w['start'] < segment_start - 1.0:
            continue
        if segment_end is not None and w['end'] > segment_end + 1.0:
            continue
        
        word_clean = w['word'].lower().strip(' .,!?¿¡"\'')
        score = SequenceMatcher(None, target_clean, word_clean).ratio()
        
        if score > best_score:
            best_score = score
            best_end = w['end']
    
    if best_score < 0.6:
        return None
    
    return best_end


def parse_overlay_inserts_md(filepath):
    """Parsear overlay-inserts.md y extraer inserciones marcadas con >>>."""
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    inserts = []
    current_segment_text = None
    current_start = None
    current_end = None
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Parsear línea de segmento: [MM:SS.xx - MM:SS.xx] (dur) texto
        ts_match = re.match(r'\[(\d+:\d+(?:\.\d+)?)\s*-\s*(\d+:\d+(?:\.\d+)?)\]\s*(?:\(\d+\.?\d*s\)\s*)?(.*)', line)
        if ts_match:
            current_start = parse_timestamp(ts_match.group(1))
            current_end = parse_timestamp(ts_match.group(2))
            current_segment_text = ts_match.group(3).strip()
            continue
        
        # Parsear marca >>> o > > > (Obsidian convierte >>> en blockquotes)
        is_marker = stripped.startswith('>>>') or stripped.startswith('> > >')
        if is_marker:
            if current_segment_text is None:
                continue
            
            marker_text = stripped
            if marker_text.startswith('> > >'):
                marker_text = marker_text[5:].strip()
            else:
                marker_text = marker_text[3:].strip()
            
            # Parsear: archivo.mp4 | @"palabra"
            parts = [p.strip() for p in marker_text.split('|')]
            if len(parts) < 2:
                print(f"⚠️  Línea {i+1}: formato incorrecto, se espera 'archivo.mp4 | @\"palabra\"'")
                continue
            
            clip_file = parts[0]
            
            # Extraer palabra del @"..."
            word_match = re.match(r'@["\u201c](.+?)["\u201d]', parts[1])
            if not word_match:
                print(f"⚠️  Línea {i+1}: no se encontró @\"palabra\" en '{parts[1]}'")
                continue
            
            target_word = word_match.group(1)
            
            inserts.append({
                'clip_file': clip_file,
                'target_word': target_word,
                'segment_text': current_segment_text,
                'segment_start': current_start,
                'segment_end': current_end,
                'line_num': i + 1,
            })
    
    return inserts


def get_video_info(video_path):
    """Obtener resolución, framerate y sample rate del video."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    info = json.loads(result.stdout)
    
    video_stream = None
    audio_stream = None
    for s in info.get('streams', []):
        if s['codec_type'] == 'video' and video_stream is None:
            video_stream = s
        elif s['codec_type'] == 'audio' and audio_stream is None:
            audio_stream = s
    
    width = int(video_stream['width']) if video_stream else 1920
    height = int(video_stream['height']) if video_stream else 1080
    
    # Framerate
    fps_str = video_stream.get('r_frame_rate', '30/1') if video_stream else '30/1'
    if '/' in fps_str:
        num, den = fps_str.split('/')
        fps = float(num) / float(den)
    else:
        fps = float(fps_str)
    
    # Audio sample rate
    sample_rate = int(audio_stream.get('sample_rate', 44100)) if audio_stream else 44100
    channels = int(audio_stream.get('channels', 2)) if audio_stream else 2
    
    return {
        'width': width,
        'height': height,
        'fps': fps,
        'sample_rate': sample_rate,
        'channels': channels,
    }


def main():
    parser = argparse.ArgumentParser(description="Paso 9 — Inserts")
    parser.add_argument("video_dir", help="Carpeta del video")
    parser.add_argument("--video", default="8_video_text_overlay.mp4", help="Video de entrada")
    parser.add_argument("--output", default="9_video_inserts.mp4", help="Video de salida")
    parser.add_argument("--crf", type=int, default=18, help="Calidad CRF (default: 18)")
    parser.add_argument("--preset", default="fast", help="Preset de encoding (default: fast)")
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar detecciones")
    
    args = parser.parse_args()
    
    video_dir = os.path.expanduser(args.video_dir)
    video_path = os.path.join(video_dir, "fuente", "video", args.video)
    overlay_md = os.path.join(video_dir, "fuente", "transcription", "overlay-inserts.md")
    transcription_json = os.path.join(video_dir, "fuente", "transcription", "transcription_original.json")
    clips_dir = os.path.join(video_dir, "fuente", "inserts")
    output_path = os.path.join(video_dir, "fuente", "video", args.output)
    tmp_dir = os.path.join(video_dir, "tmp", "inserts")
    
    os.makedirs(tmp_dir, exist_ok=True)
    
    if not os.path.isfile(video_path):
        print(f"❌ Video no encontrado: {video_path}")
        sys.exit(1)
    
    if not os.path.isfile(overlay_md):
        # Crear desde transcription_limpia.md
        limpia_md = os.path.join(video_dir, "fuente", "transcription", "transcription_limpia.md")
        if os.path.isfile(limpia_md):
            header = """# Inserts
#
# Copiado de transcription_limpia.md — marca puntos de inserción con >>>.
#
# INSTRUCCIONES:
# Para insertar un clip, agrega >>> debajo del segmento.
# Formato: >>> archivo.mp4 | @"palabra"
#
# - archivo.mp4 = clip en fuente/inserts/ (entra completo, con su audio)
# - @"palabra" = el clip se inserta DESPUÉS de esa palabra
#
# El script busca la palabra en la transcripción word-level para el timestamp exacto.
# El clip entra completo. Si solo quieres una parte, editalo antes.
#
# Ejemplo:
# [0:32.96 - 0:34.72] (1.8s) Porque me estaba volviendo obsoleto.
# >>> sam-altman.mp4 | @"obsoleto"

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
            
            print(f"📋 overlay-inserts.md creado desde transcription_limpia.md")
            print(f"   → Abrilo y marcá puntos de inserción con >>> antes de renderizar\n")
            if args.dry_run:
                return
        else:
            print(f"❌ No existe overlay-inserts.md ni transcription_limpia.md")
            sys.exit(1)
    
    if not os.path.isfile(transcription_json):
        print(f"❌ transcription_original.json no encontrado: {transcription_json}")
        sys.exit(1)
    
    # Cargar transcripción word-level
    with open(transcription_json) as f:
        transcription = json.load(f)
    words = transcription.get('words', [])
    
    # Parsear marcas
    inserts = parse_overlay_inserts_md(overlay_md)
    
    print(f"📹 Video: {video_path}")
    print(f"📋 Overlay: {overlay_md}")
    print(f"📤 Output: {output_path}")
    print(f"🎬 Inserts dir: {clips_dir}")
    print(f"\n📊 {len(inserts)} inserciones encontradas\n")
    
    if not inserts:
        print("⚠️  No hay inserciones marcadas con >>>")
        return
    
    # Resolver timestamps con word-level
    for ins in inserts:
        word_end = find_word_end_timestamp(
            ins['target_word'], words,
            segment_start=ins['segment_start'],
            segment_end=ins['segment_end']
        )
        
        if word_end is not None:
            ins['cut_at'] = word_end
            ins['source'] = 'word-level'
        else:
            # Fallback: usar el final del segmento
            ins['cut_at'] = ins['segment_end']
            ins['source'] = 'segment fallback'
            print(f"⚠️  Línea {ins['line_num']}: palabra \"{ins['target_word']}\" no encontrada en word-level, usando final del segmento")
        
        # Verificar que el clip existe
        clip_path = os.path.join(clips_dir, ins['clip_file'])
        if os.path.isfile(clip_path):
            ins['clip_path'] = clip_path
            # Obtener duración del clip
            probe_cmd = [
                "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", clip_path
            ]
            result = subprocess.run(probe_cmd, capture_output=True, text=True)
            ins['clip_duration'] = float(result.stdout.strip())
        else:
            ins['clip_path'] = None
            ins['clip_duration'] = 0
            print(f"❌ Línea {ins['line_num']}: Clip no encontrado: {clip_path}")
    
    # Ordenar por timestamp de corte
    inserts.sort(key=lambda x: x['cut_at'])
    
    # Mostrar resumen
    total_clip_duration = 0
    all_valid = True
    for ins in inserts:
        status = "✅" if ins['clip_path'] else "❌"
        print(f"   {status} [{format_time(ins['cut_at'])}] después de \"{ins['target_word']}\" [{ins['source']}]")
        print(f"      → {ins['clip_file']} ({ins['clip_duration']:.1f}s)")
        print()
        total_clip_duration += ins['clip_duration']
        if not ins['clip_path']:
            all_valid = False
    
    print(f"📊 Duración total de clips a insertar: {total_clip_duration:.1f}s")
    
    if args.dry_run:
        print("\n🏁 Dry run — no se generó video.")
        return
    
    if not all_valid:
        print("\n❌ Hay clips faltantes. Corrige antes de renderizar.")
        sys.exit(1)
    
    # Obtener info del video base
    base_info = get_video_info(video_path)
    print(f"\n📐 Video base: {base_info['width']}x{base_info['height']} @ {base_info['fps']:.2f}fps, audio {base_info['sample_rate']}Hz {base_info['channels']}ch")
    
    # Limpiar tmp
    for f in os.listdir(tmp_dir):
        os.remove(os.path.join(tmp_dir, f))
    
    # 1. Cortar video base en segmentos
    segments = []
    prev_cut = 0.0
    
    for idx, ins in enumerate(inserts):
        cut_at = ins['cut_at']
        
        # Segmento del video base: prev_cut → cut_at
        if cut_at > prev_cut:
            seg_file = os.path.join(tmp_dir, f"segment_{idx:03d}.mp4")
            duration = cut_at - prev_cut
            cmd = [
                "ffmpeg", "-y", "-ss", format_time_ffmpeg(prev_cut),
                "-i", video_path, "-t", str(duration),
                "-c:v", "libx264", "-crf", str(args.crf), "-preset", args.preset,
                "-c:a", "aac", "-ar", str(base_info['sample_rate']),
                "-ac", str(base_info['channels']),
                "-video_track_timescale", "15360",
                seg_file
            ]
            print(f"✂️  Cortando segmento {idx}: {format_time(prev_cut)} → {format_time(cut_at)} ({duration:.1f}s)")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"❌ Error cortando segmento {idx}:\n{result.stderr[-500:]}")
                sys.exit(1)
            segments.append(seg_file)
        
        # Normalizar clip
        # Detectar si el clip tiene audio
        probe_audio = subprocess.run(
            ["ffprobe", "-v", "quiet", "-select_streams", "a",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0",
             ins['clip_path']],
            capture_output=True, text=True
        )
        has_audio = bool(probe_audio.stdout.strip())
        
        clip_norm = os.path.join(tmp_dir, f"insert_{idx:03d}.mp4")
        cmd = ["ffmpeg", "-y", "-i", ins['clip_path']]
        
        # Si no tiene audio, generar silencio
        if not has_audio:
            cmd += ["-f", "lavfi", "-i", f"anullsrc=r={base_info['sample_rate']}:cl={'stereo' if base_info['channels'] == 2 else 'mono'}"]
            cmd += ["-shortest"]
        
        cmd += [
            "-vf", f"scale={base_info['width']}:{base_info['height']}:force_original_aspect_ratio=decrease,pad={base_info['width']}:{base_info['height']}:(ow-iw)/2:(oh-ih)/2",
            "-r", str(base_info['fps']),
            "-c:v", "libx264", "-crf", str(args.crf), "-preset", args.preset,
            "-c:a", "aac", "-ar", str(base_info['sample_rate']),
            "-ac", str(base_info['channels']),
            "-video_track_timescale", "15360",
            clip_norm
        ]
        print(f"🎬 Normalizando clip: {ins['clip_file']} ({ins['clip_duration']:.1f}s)")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Error normalizando clip {ins['clip_file']}:\n{result.stderr[-500:]}")
            sys.exit(1)
        segments.append(clip_norm)
        
        prev_cut = cut_at
    
    # Último segmento: desde el último corte hasta el final
    last_seg = os.path.join(tmp_dir, f"segment_{len(inserts):03d}.mp4")
    cmd = [
        "ffmpeg", "-y", "-ss", format_time_ffmpeg(prev_cut),
        "-i", video_path,
        "-c:v", "libx264", "-crf", str(args.crf), "-preset", args.preset,
        "-c:a", "aac", "-ar", str(base_info['sample_rate']),
        "-ac", str(base_info['channels']),
        "-video_track_timescale", "15360",
        last_seg
    ]
    print(f"✂️  Cortando segmento final: {format_time(prev_cut)} → final")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Error cortando segmento final:\n{result.stderr[-500:]}")
        sys.exit(1)
    segments.append(last_seg)
    
    # 2. Generar concat list
    concat_file = os.path.join(tmp_dir, "concat_list.txt")
    with open(concat_file, 'w') as f:
        for seg in segments:
            f.write(f"file '{seg}'\n")
    
    print(f"\n📋 Concat list ({len(segments)} segmentos):")
    for seg in segments:
        print(f"   {os.path.basename(seg)}")
    
    # 3. Concatenar
    print(f"\n🔗 Concatenando...")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c", "copy",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Error concatenando:\n{result.stderr[-500:]}")
        sys.exit(1)
    
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\n✅ Listo: {output_path} ({size_mb:.0f} MB)")


if __name__ == "__main__":
    main()
