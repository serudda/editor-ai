#!/usr/bin/env python3
"""
Jump Cut Automático — Eliminar silencios de un video.

Detecta silencios con ffmpeg, calcula segmentos de voz,
extrae cada segmento como .ts y los concatena en un .mp4 final.

Uso:
  python3 jump-cut.py video.mp4
  python3 jump-cut.py video.mp4 --padding 0.5 --min-silence 2.0
  python3 jump-cut.py video.mp4 --noise -25 --min-detect 0.5 --dry-run

Flags:
  --padding       Segundos de "aire" antes/después de cada corte (default: 0.3)
  --min-silence   Solo cortar silencios mayores a este valor en segundos (default: 1.5)
  --noise         Threshold de silencio en dB (default: -30)
  --min-detect    Duración mínima para detectar como silencio (default: 0.8)
  --crf           Calidad de video, menor = mejor (default: 18)
  --preset        Preset de encoding ffmpeg (default: fast)
  --output        Nombre del archivo de salida (default: 4_video_jumpcut.mp4)
  --dry-run       Solo muestra estadísticas, no genera video

Documentación completa: ../4_eliminar-silencios.md
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile


def get_duration(video_path):
    """Obtener duración del video con ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", video_path],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())


def detect_silences(video_path, noise_db, min_detect):
    """Detectar silencios con ffmpeg silencedetect."""
    print(f"🔍 Detectando silencios (noise={noise_db}dB, min={min_detect}s)...")
    result = subprocess.run(
        ["ffmpeg", "-i", video_path,
         "-af", f"silencedetect=noise={noise_db}dB:d={min_detect}",
         "-f", "null", "-"],
        capture_output=True, text=True
    )
    
    output = result.stderr
    silences = []
    current_start = None
    
    for line in output.split("\n"):
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
    
    return silences


def calculate_segments(silences, min_silence, padding, video_duration):
    """Calcular segmentos de voz (inversión de silencios largos)."""
    long_silences = [(s, e, d) for s, e, d in silences if d > min_silence]
    
    cuts = []
    prev_end = 0
    for s_start, s_end, s_dur in long_silences:
        seg_end = s_start + padding
        if seg_end > prev_end + 0.1:
            cuts.append((prev_end, seg_end))
        prev_end = s_end - padding
    
    if prev_end < video_duration:
        cuts.append((prev_end, video_duration))
    
    return cuts, long_silences


def extract_and_concat(video_path, segments, output_path, crf, preset):
    """Extraer segmentos como .ts y concatenar en .mp4."""
    # Use tmp/ inside the video project folder
    video_parent = os.path.dirname(video_path) or "."
    if "fuente" in video_parent:
        project_dir = os.path.normpath(os.path.join(video_parent, "..", ".."))
    else:
        project_dir = video_parent
    tmpdir = os.path.join(project_dir, "tmp", "jc_segments")
    os.makedirs(tmpdir, exist_ok=True)
    total = len(segments)
    
    print(f"✂️  Extrayendo {total} segmentos...")
    for i, (start, end) in enumerate(segments):
        duration = end - start
        seg_path = os.path.join(tmpdir, f"seg_{i:04d}.ts")
        subprocess.run(
            ["ffmpeg", "-ss", f"{start:.3f}", "-i", video_path,
             "-t", f"{duration:.3f}",
             "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
             "-c:a", "aac", "-b:a", "192k",
             "-f", "mpegts", "-y", seg_path],
            capture_output=True
        )
        # Progress bar
        pct = (i + 1) / total * 100
        bar = "█" * int(pct / 2) + "░" * (50 - int(pct / 2))
        print(f"\r  [{bar}] {pct:.0f}% ({i+1}/{total})", end="", flush=True)
    
    print()  # New line after progress bar
    
    # Generate concat list
    list_path = os.path.join(tmpdir, "list.txt")
    with open(list_path, "w") as f:
        for i in range(total):
            f.write(f"file 'seg_{i:04d}.ts'\n")
    
    # Concatenate
    print(f"🔗 Concatenando → {output_path}")
    subprocess.run(
        ["ffmpeg", "-f", "concat", "-safe", "0",
         "-i", list_path, "-c", "copy", "-y", output_path],
        capture_output=True
    )
    
    # Cleanup segments (keep tmp/ folder)
    for f in os.listdir(tmpdir):
        os.remove(os.path.join(tmpdir, f))
    os.rmdir(tmpdir)


def format_time(seconds):
    """Formatear segundos como MM:SS."""
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def main():
    parser = argparse.ArgumentParser(
        description="Jump Cut Automático — Eliminar silencios de un video."
    )
    parser.add_argument("video", help="Ruta al video de entrada")
    parser.add_argument("--padding", type=float, default=0.3,
                        help="Segundos de aire antes/después del corte (default: 0.3)")
    parser.add_argument("--min-silence", type=float, default=1.5,
                        help="Solo cortar silencios mayores a N segundos (default: 1.5)")
    parser.add_argument("--noise", type=int, default=-30,
                        help="Threshold de silencio en dB (default: -30)")
    parser.add_argument("--min-detect", type=float, default=0.8,
                        help="Duración mínima para detectar silencio (default: 0.8)")
    parser.add_argument("--crf", type=int, default=18,
                        help="Calidad de video CRF (default: 18)")
    parser.add_argument("--preset", default="fast",
                        help="Preset de encoding (default: fast)")
    parser.add_argument("--output", default=None,
                        help="Archivo de salida (default: 4_video_jumpcut.mp4)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo mostrar estadísticas, no generar video")
    
    args = parser.parse_args()
    
    if not os.path.isfile(args.video):
        print(f"❌ Archivo no encontrado: {args.video}")
        sys.exit(1)
    
    # Output path: if video is inside fuente/video/, output goes to fuente/video/
    if args.output:
        output_path = args.output
    else:
        base_dir = os.path.dirname(args.video) or "."
        output_path = os.path.join(base_dir, "4_video_jumpcut.mp4")

    # Determine tmp dir (inside the video project folder)
    # If video is at .../fuente/video/x.mp4, tmp is at .../tmp/
    if "fuente" in base_dir:
        project_dir = os.path.normpath(os.path.join(base_dir, "..", ".."))
    else:
        project_dir = base_dir
    
    # Get duration
    duration = get_duration(args.video)
    print(f"📹 Video: {args.video}")
    print(f"⏱️  Duración: {format_time(duration)} ({duration:.1f}s)")
    print()
    
    # Detect silences
    silences = detect_silences(args.video, args.noise, args.min_detect)
    print(f"   Silencios detectados: {len(silences)}")
    
    # Calculate segments
    segments, long_silences = calculate_segments(
        silences, args.min_silence, args.padding, duration
    )
    
    # Stats
    time_cut = sum(d for _, _, d in long_silences) - (args.padding * 2 * len(long_silences))
    result_duration = duration - time_cut
    
    print()
    print("📊 Estadísticas:")
    print(f"   Silencios > {args.min_silence}s (cortados): {len(long_silences)}")
    print(f"   Silencios ≤ {args.min_silence}s (conservados): {len(silences) - len(long_silences)}")
    print(f"   Segmentos de voz: {len(segments)}")
    print(f"   Tiempo recortado: ~{format_time(time_cut)}")
    print(f"   Duración estimada: {format_time(duration)} → {format_time(result_duration)}")
    print()
    print(f"⚙️  Config: padding={args.padding}s | min-silence={args.min_silence}s | noise={args.noise}dB | crf={args.crf}")
    
    if args.dry_run:
        print()
        print("🏁 Dry run — no se generó video.")
        return
    
    print()
    extract_and_concat(args.video, segments, output_path, args.crf, args.preset)
    
    # Final size
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"✅ Listo: {output_path} ({size_mb:.0f} MB)")


if __name__ == "__main__":
    main()
