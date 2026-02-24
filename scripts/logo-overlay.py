#!/usr/bin/env python3
"""
Paso 6 — Logo Overlay

Lee `fuente/transcription/overlay-logos.md` del folder del video para saber
qué logos aplicar y en qué momentos. Los logos se buscan en el repo central:
  ~/Documents/Edicion/Serudda/recursos/logos/{brand}/{brand}.png

Uso:
  python3 logo-overlay.py <carpeta-del-video>
  python3 logo-overlay.py <carpeta-del-video> --dry-run

Documentación completa: ../6_logo-overlay.md
"""

import argparse
import os
import re
import subprocess
import sys


def parse_timestamp(ts):
    """Convertir MM:SS.xx o H:MM:SS.xx a segundos (con decimales)."""
    parts = ts.strip().split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    return 0.0


def parse_overlay_md(filepath, logo_duration=3.0):
    """Parsear overlay-logos.md y extraer detecciones marcadas con ✅.
    
    Acepta dos formatos:
    
    Formato nuevo (con transcripción limpia como base):
        [0:00 - 0:17.56] (17.6s) El 50% de los trabajos... Antropic...
        → anthropic.png | 0:08.60 | ✅
    
    Formato viejo (solo detecciones):
        [0:08.60 - 0:11.60] "contexto"
          → anthropic.png | ✅
    """
    with open(filepath, "r") as f:
        lines = f.readlines()

    detections = []
    current_start = None
    current_end = None

    for line in lines:
        ts_match = re.match(r'\[(\d+:\d+(?:\.\d+)?)\s*-\s*(\d+:\d+(?:\.\d+)?)\]', line)
        if ts_match:
            current_start = parse_timestamp(ts_match.group(1))
            current_end = parse_timestamp(ts_match.group(2))
            continue

        # Formato nuevo: → logo.png | MM:SS.xx | ✅/❌
        logo_match_new = re.match(r'\s*→\s*(\S+)\.png\s*\|\s*(\d+:\d+(?:\.\d+)?)\s*\|\s*(✅|❌)', line)
        if logo_match_new:
            logo_file = logo_match_new.group(1)
            logo_start = parse_timestamp(logo_match_new.group(2))
            approved = logo_match_new.group(3) == "✅"

            if approved:
                logo_end = logo_start + logo_duration
                stack_level = 0
                for prev_start, prev_end, _, _ in detections:
                    if logo_start < prev_end and logo_end > prev_start:
                        stack_level += 1
                detections.append((logo_start, logo_end, logo_file, stack_level))
            continue

        # Formato viejo: → logo.png | ✅/❌
        logo_match_old = re.match(r'\s*→\s*(\S+)\.png\s*\|\s*(✅|❌)', line)
        if logo_match_old and current_start is not None:
            logo_file = logo_match_old.group(1)
            approved = logo_match_old.group(2) == "✅"

            if approved:
                stack_level = 0
                for prev_start, prev_end, _, _ in detections:
                    if current_start < prev_end and current_end > prev_start:
                        stack_level += 1
                detections.append((current_start, current_end, logo_file, stack_level))

    return detections


def format_time(seconds):
    m, s = divmod(seconds, 60)
    m = int(m)
    if s == int(s):
        return f"{m}:{int(s):02d}"
    return f"{m}:{s:05.2f}"


def main():
    parser = argparse.ArgumentParser(description="Paso 6 — Logo Overlay")
    parser.add_argument("video_dir", help="Carpeta del video")
    parser.add_argument("--video", default="5_video_limpio.mp4", help="Video de entrada (default: 5_video_limpio.mp4)")
    parser.add_argument("--output", default=None, help="Video de salida (default: <video>_logos.mp4)")
    parser.add_argument("--size", type=int, default=250, help="Tamaño del logo en px (default: 250)")
    parser.add_argument("--padding", type=int, default=40, help="Padding del borde (default: 40)")
    parser.add_argument("--padding-x", type=int, default=160, help="Padding horizontal (default: 160)")
    parser.add_argument("--padding-y", type=int, default=80, help="Padding vertical (default: 80)")
    parser.add_argument("--position", default="top-left", choices=["top-left", "top-right", "bottom-left", "bottom-right"], help="Posición del logo (default: top-left)")
    parser.add_argument("--fade", type=float, default=0.0, help="[DESACTIVADO] Fade causa logos invisibles en overlays encadenados. Se ignora.")
    parser.add_argument("--crf", type=int, default=18, help="Calidad CRF (default: 18)")
    parser.add_argument("--preset", default="fast", help="Preset de encoding (default: fast)")
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar detecciones")

    args = parser.parse_args()

    video_dir = os.path.expanduser(args.video_dir)
    video_path = os.path.join(video_dir, "fuente", "video", args.video)
    overlay_md = os.path.join(video_dir, "fuente", "transcription", "overlay-logos.md")
    logo_dir = os.path.expanduser("~/Documents/Edicion/Serudda/recursos/logos")
    output_dir = os.path.join(video_dir, "output")
    tmp_dir = os.path.join(video_dir, "tmp")

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(tmp_dir, exist_ok=True)

    video_out_dir = os.path.join(video_dir, "fuente", "video")
    if args.output:
        output_path = os.path.join(video_out_dir, args.output)
    else:
        output_path = os.path.join(video_out_dir, "6_video_limpio_logos.mp4")

    if not os.path.isfile(video_path):
        print(f"❌ Video no encontrado: {video_path}")
        sys.exit(1)
    if not os.path.isfile(overlay_md):
        print(f"❌ overlay-logos.md no encontrado: {overlay_md}")
        sys.exit(1)

    detections = parse_overlay_md(overlay_md)

    print(f"📹 Video: {video_path}")
    print(f"📋 Detecciones: {overlay_md}")
    print(f"🖼️  Logos: {logo_dir}")
    print(f"📤 Output: {output_path}")
    print(f"\n📊 {len(detections)} logos aprobados (✅)\n")

    for start, end, logo, stack in detections:
        stack_info = f" (stacked +{stack})" if stack > 0 else ""
        print(f"   [{format_time(start)} - {format_time(end)}] {logo}.png{stack_info}")

    # Verificar logos existen (repo central: {brand}/{brand}.png)
    missing = set()
    for _, _, logo, _ in detections:
        path = os.path.join(logo_dir, logo, f"{logo}.png")
        if not os.path.exists(path):
            missing.add(f"{logo}/{logo}.png")
    if missing:
        print(f"\n❌ Logos faltantes en {logo_dir}:")
        for m in sorted(missing):
            print(f"   - {m}")
        sys.exit(1)

    if args.dry_run:
        print("\n🏁 Dry run — no se generó video.")
        return

    # --- Generar comando ffmpeg como .sh ---

    # Inputs
    input_parts = [f'ffmpeg -i "{video_path}"']
    logo_index = {}
    for _, _, logo, _ in detections:
        if logo not in logo_index:
            logo_index[logo] = len(logo_index) + 1
            input_parts.append(f'-i "{os.path.join(logo_dir, logo, logo + ".png")}"')

    # Filter complex
    filters = []
    chain = "0:v"
    for i, (start, end, logo, stack_level) in enumerate(detections):
        idx = logo_index[logo]
        sl = f"s{i}"
        vl = f"v{i}"
        y_offset = (args.size + 10) * stack_level
        pad_x = args.padding_x if args.padding_x is not None else args.padding
        pad_y = args.padding_y if args.padding_y is not None else args.padding

        # Posición según --position
        if args.position == "top-left":
            pos_x = str(pad_x)
            pos_y = str(pad_y + y_offset) if stack_level == 0 else f"{pad_y}+{y_offset}"
        elif args.position == "top-right":
            pos_x = f"W-{args.size}-{pad_x}"
            pos_y = str(pad_y + y_offset) if stack_level == 0 else f"{pad_y}+{y_offset}"
        elif args.position == "bottom-left":
            pos_x = str(pad_x)
            pos_y = f"H-{args.size}-{pad_y}" if stack_level == 0 else f"H-{args.size}-{pad_y}-{y_offset}"
        else:  # bottom-right
            pos_x = f"W-{args.size}-{pad_x}"
            pos_y = f"H-{args.size}-{pad_y}" if stack_level == 0 else f"H-{args.size}-{pad_y}-{y_offset}"

        # ⚠️ NO usar fade con alpha=1 en overlays encadenados — hace los logos invisibles.
        # Ver 6_logo-overlay.md → "NOTA IMPORTANTE" para detalles.
        filters.append(
            f"[{idx}:v]scale={args.size}:{args.size}:force_original_aspect_ratio=decrease,"
            f"format=rgba[{sl}]"
        )
        filters.append(
            f"[{chain}][{sl}]overlay={pos_x}:{pos_y}:"
            f"enable='between(t,{start},{end})'[{vl}]"
        )
        chain = vl

    fc = ";".join(filters)

    # Escribir .sh
    sh_file = os.path.join(tmp_dir, "logo_overlay_cmd.sh")
    with open(sh_file, "w") as f:
        f.write("#!/bin/bash\nset -e\n")
        f.write(" ".join(input_parts))
        f.write(f' -filter_complex "{fc}"')
        f.write(f' -map "[{chain}]" -map 0:a')
        f.write(f" -c:v libx264 -crf {args.crf} -preset {args.preset}")
        f.write(f' -c:a copy -y "{output_path}"\n')
    os.chmod(sh_file, 0o755)

    _px = args.padding_x if args.padding_x is not None else args.padding
    _py = args.padding_y if args.padding_y is not None else args.padding
    print(f"\n⚙️  Config: size={args.size}px | padding-x={_px}px | padding-y={_py}px | crf={args.crf}")
    print(f"\n🎬 Aplicando {len(detections)} logos...")
    print(f"   ⚠️  Tarda ~7-10 min para un video de 17 min.\n")
    print(f"📝 Script: {sh_file}\n")

    result = subprocess.run(["bash", sh_file])

    if result.returncode != 0:
        print(f"\n❌ Error (código {result.returncode})")
        print(f"   Revisa: cat {sh_file}")
        sys.exit(1)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\n✅ Listo: {output_path} ({size_mb:.0f} MB)")


if __name__ == "__main__":
    main()
