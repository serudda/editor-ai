#!/usr/bin/env python3
"""
Color Grade Cinematográfico — Aplicar tono cálido + look profesional.

Uso:
  python3 color-grade.py <carpeta-del-video>
  python3 color-grade.py <carpeta-del-video> --warmth 0.05
  python3 color-grade.py <carpeta-del-video> --no-vignette
  python3 color-grade.py <carpeta-del-video> --saturation 1.15

Aplica por capas:
  1. Curves — Levantar negros, comprimir highlights, teal & orange
  2. Color balance — Ajuste fino por zona (sombras/midtonos/highlights)
  3. Eq — Saturación y contraste global
  4. Vignette — Oscurecer bordes (opcional)

Espera:
  fuente/video/2_video_denoised.mp4      ← Input (del Paso 2)

Genera:
  fuente/video/3_video_color_grade.mp4   ← Output con color grade

Documentación completa: ../3_color-grade-cinematografico.md
"""

import argparse
import os
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description="Color grade cinematográfico.")
    parser.add_argument("video_dir", help="Carpeta del video")
    parser.add_argument("--input", default="2_video_denoised.mp4", help="Video de entrada (default: 2_video_denoised.mp4)")
    parser.add_argument("--output", default="3_video_color_grade.mp4", help="Video de salida (default: 3_video_color_grade.mp4)")
    parser.add_argument("--warmth", type=float, default=0.05,
                        help="Calidez en midtonos rojos (default: 0.05, rango 0.0-0.10)")
    parser.add_argument("--saturation", type=float, default=1.1,
                        help="Saturación global (default: 1.1)")
    parser.add_argument("--contrast", type=float, default=1.02,
                        help="Contraste global (default: 1.02)")
    parser.add_argument("--black-lift", type=float, default=0.04,
                        help="Cuánto levantar los negros (default: 0.04, rango 0.0-0.10)")
    parser.add_argument("--highlight-compress", type=float, default=0.92,
                        help="Compresión de highlights (default: 0.92, más bajo = más compresión)")
    parser.add_argument("--teal-shadows", type=float, default=0.06,
                        help="Azul/teal en sombras (default: 0.06)")
    parser.add_argument("--no-vignette", action="store_true",
                        help="Desactivar viñeta")
    parser.add_argument("--vignette-strength", default="PI/6",
                        help="Fuerza de viñeta (default: PI/6, más bajo = más fuerte)")
    parser.add_argument("--crf", type=int, default=18, help="Calidad CRF (default: 18)")
    parser.add_argument("--preset", default="medium", help="Preset de encoding (default: medium)")

    args = parser.parse_args()

    video_dir = os.path.expanduser(args.video_dir)
    input_path = os.path.join(video_dir, "fuente", "video", args.input)
    output_path = os.path.join(video_dir, "fuente", "video", args.output)

    if not os.path.isfile(input_path):
        print(f"❌ Video no encontrado: {input_path}")
        sys.exit(1)

    bl = args.black_lift
    hc = args.highlight_compress
    ts = args.teal_shadows
    w = args.warmth

    # Build filter chain
    filters = []

    # 1. Curves
    curves = (
        f"curves="
        f"master='0/{bl} 0.25/0.22 0.5/0.50 0.75/0.73 1/{hc}':"
        f"red='0/{bl} 0.5/{0.50 + w} 1/{hc + 0.01}':"
        f"green='0/{bl - 0.01} 0.5/0.50 1/{hc}':"
        f"blue='0/{ts} 0.5/0.49 1/{hc - 0.02}'"
    )
    filters.append(curves)

    # 2. Color balance
    colorbalance = (
        f"colorbalance="
        f"rs=0.03:gs=-0.02:bs=-0.04:"
        f"rm={w}:gm=0.01:bm=-0.02:"
        f"rh=-0.03:gh=-0.01:bh=0.02"
    )
    filters.append(colorbalance)

    # 3. Eq
    filters.append(f"eq=saturation={args.saturation}:contrast={args.contrast}")

    # 4. Vignette
    if not args.no_vignette:
        filters.append(f"vignette={args.vignette_strength}")

    vf = ",\n    ".join(filters)

    print(f"📹 Input: {input_path}")
    print(f"📤 Output: {output_path}")
    print(f"⚙️  warmth={w} | saturation={args.saturation} | black-lift={bl} | vignette={'off' if args.no_vignette else args.vignette_strength}")
    print()
    print("🎨 Aplicando color grade...")

    cmd = [
        "ffmpeg", "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264", "-crf", str(args.crf), "-preset", args.preset,
        "-c:a", "copy",
        "-y", output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ Error:")
        print(result.stderr[-1000:])
        sys.exit(1)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\n✅ Listo: {output_path} ({size_mb:.0f} MB)")


if __name__ == "__main__":
    main()
