#!/usr/bin/env python3
"""
Logo Overlay — Superponer logos en un video basado en detecciones.

Lee `fuente/transcripcion/logo-overlay.md` del folder del video para saber
qué logos aplicar y en qué momentos. Los logos se buscan en `fuente/logos/`.

Uso:
  python3 logo-overlay.py <carpeta-del-video>
  python3 logo-overlay.py <carpeta-del-video> --video 4_video_jumpcut.mp4
  python3 logo-overlay.py <carpeta-del-video> --size 150 --padding 50
  python3 logo-overlay.py <carpeta-del-video> --dry-run
  python3 logo-overlay.py <carpeta-del-video> --print-cmd

Estructura esperada:
  <carpeta-del-video>/
    fuente/
      video/4_video_jumpcut.mp4           ← Input
      transcripcion/logo-overlay.md     ← Detecciones (✅/❌)
      logos/*.png                       ← Logos descargados
    output/
      4_video_jumpcut_logos.mp4           ← Output

Documentación completa: ../5_logo-overlay.md
"""

import argparse
import os
import re
import subprocess
import sys


def parse_timestamp(ts):
    """Convertir MM:SS o H:MM:SS a segundos."""
    parts = ts.strip().split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return 0


def parse_logo_overlay_md(filepath):
    """
    Parsear logo-overlay.md y extraer detecciones marcadas con ✅.
    Returns list of (start_sec, end_sec, logo_name, stack_level)
    """
    with open(filepath, "r") as f:
        lines = f.readlines()

    detections = []
    current_start = None
    current_end = None

    for line in lines:
        ts_match = re.match(r'\[(\d+:\d+)\s*-\s*(\d+:\d+)\]', line)
        if ts_match:
            current_start = parse_timestamp(ts_match.group(1))
            current_end = parse_timestamp(ts_match.group(2))
            continue

        logo_match = re.match(r'\s*→\s*(\S+)\.png\s*\|\s*(✅|❌)', line)
        if logo_match and current_start is not None:
            logo_file = logo_match.group(1)
            approved = logo_match.group(2) == "✅"

            if approved:
                stack_level = 0
                for prev_start, prev_end, _, _ in detections:
                    if current_start < prev_end and current_end > prev_start:
                        stack_level += 1
                detections.append((current_start, current_end, logo_file, stack_level))

    return detections


def build_ffmpeg_cmd(video_path, output_path, logo_dir, detections, size, padding, fade, crf, preset):
    """Build the ffmpeg command for single-pass overlay."""
    inputs = ["-i", video_path]
    logo_map = {}

    for _, _, logo, _ in detections:
        if logo not in logo_map:
            logo_map[logo] = len(logo_map) + 1
            inputs.extend(["-i", os.path.join(logo_dir, f"{logo}.png")])

    filters = []
    chain = "0:v"

    for i, (start, end, logo, stack_level) in enumerate(detections):
        idx = logo_map[logo]
        y_offset = (size + 10) * stack_level
        sl = f"s{i}"
        vl = f"v{i}"

        filters.append(
            f"[{idx}:v]scale={size}:{size}:force_original_aspect_ratio=decrease,"
            f"format=rgba,"
            f"fade=t=in:st={start}:d={fade}:alpha=1,"
            f"fade=t=out:st={end - fade}:d={fade}:alpha=1[{sl}]"
        )

        pos_y = f"H-{size}-{padding}" if stack_level == 0 else f"H-{size}-{padding}-{y_offset}"
        filters.append(
            f"[{chain}][{sl}]overlay=W-{size}-{padding}:{pos_y}:"
            f"enable='between(t,{start},{end})'[{vl}]"
        )
        chain = vl

    fc = ";\n".join(filters)
    cmd = [
        "ffmpeg", *inputs,
        "-filter_complex", fc,
        "-map", f"[{chain}]", "-map", "0:a",
        "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
        "-c:a", "copy",
        "-y", output_path
    ]
    return cmd


def format_time(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def main():
    parser = argparse.ArgumentParser(description="Logo Overlay — Superponer logos en un video.")
    parser.add_argument("video_dir", help="Carpeta del video")
    parser.add_argument("--video", default="4_video_jumpcut.mp4", help="Video de entrada en fuente/video/ (default: 4_video_jumpcut.mp4)")
    parser.add_argument("--output", default=None, help="Video de salida en output/ (default: <video>_logos.mp4)")
    parser.add_argument("--size", type=int, default=120, help="Tamaño del logo en px (default: 120)")
    parser.add_argument("--padding", type=int, default=40, help="Padding del borde en px (default: 40)")
    parser.add_argument("--fade", type=float, default=0.3, help="Fade in/out en segundos (default: 0.3)")
    parser.add_argument("--crf", type=int, default=18, help="Calidad CRF (default: 18)")
    parser.add_argument("--preset", default="fast", help="Preset de encoding (default: fast)")
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar detecciones, no generar video")
    parser.add_argument("--print-cmd", action="store_true", help="Solo imprimir el comando ffmpeg")

    args = parser.parse_args()

    video_dir = os.path.expanduser(args.video_dir)
    video_path = os.path.join(video_dir, "fuente", "video", args.video)
    logo_overlay_md = os.path.join(video_dir, "fuente", "transcripcion", "logo-overlay.md")
    logo_dir = os.path.join(video_dir, "fuente", "logos")
    output_dir = os.path.join(video_dir, "output")

    os.makedirs(output_dir, exist_ok=True)

    if args.output:
        output_path = os.path.join(output_dir, args.output)
    else:
        base = args.video.replace(".mp4", "")
        output_path = os.path.join(output_dir, f"{base}_logos.mp4")

    if not os.path.isfile(video_path):
        print(f"❌ Video no encontrado: {video_path}")
        sys.exit(1)
    if not os.path.isfile(logo_overlay_md):
        print(f"❌ logo-overlay.md no encontrado: {logo_overlay_md}")
        print("   Pídele a Sinistra que genere la transcripción y detecciones primero.")
        sys.exit(1)

    detections = parse_logo_overlay_md(logo_overlay_md)

    print(f"📹 Video: {video_path}")
    print(f"📋 Detecciones: {logo_overlay_md}")
    print(f"🖼️  Logos: {logo_dir}")
    print(f"📤 Output: {output_path}")
    print()
    print(f"📊 {len(detections)} logos aprobados (✅)")
    print()

    for start, end, logo, stack in detections:
        stack_info = f" (stacked +{stack})" if stack > 0 else ""
        print(f"   [{format_time(start)} - {format_time(end)}] {logo}.png{stack_info}")

    missing = []
    for _, _, logo, _ in detections:
        path = os.path.join(logo_dir, f"{logo}.png")
        if not os.path.exists(path):
            missing.append(f"{logo}.png")
    if missing:
        unique_missing = sorted(set(missing))
        print(f"\n❌ Logos faltantes en {logo_dir}:")
        for m in unique_missing:
            print(f"   - {m}")
        sys.exit(1)

    if args.dry_run:
        print("\n🏁 Dry run — no se generó video.")
        return

    print()
    print(f"⚙️  Config: size={args.size}px | padding={args.padding}px | fade={args.fade}s | crf={args.crf}")

    cmd = build_ffmpeg_cmd(video_path, output_path, logo_dir, detections,
                           args.size, args.padding, args.fade, args.crf, args.preset)

    if args.print_cmd:
        print("\n📋 Comando ffmpeg:\n")
        print(" \\\n  ".join(str(c) for c in cmd))
        return

    print()
    print(f"🎬 Aplicando {len(detections)} logos en single pass...")
    print(f"   ⚠️  Esto puede tardar 10-20 min para un video de 17 min.")
    print()

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Error:")
        print(result.stderr[-1000:])
        sys.exit(1)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"✅ Listo: {output_path} ({size_mb:.0f} MB)")


if __name__ == "__main__":
    main()
