#!/usr/bin/env python3
"""
Reducir Ruido Visual — Aplicar denoising temporal con hqdn3d.

Uso:
  python3 denoise.py <carpeta-del-video>
  python3 denoise.py <carpeta-del-video> --strength medium
  python3 denoise.py <carpeta-del-video> --strength heavy --crf 20
  python3 denoise.py <carpeta-del-video> --custom 5:5:6:6

Presets de fuerza:
  light   → hqdn3d=2:2:3:3  (conservador, deja algo de grano)
  medium  → hqdn3d=3:3:4:4  (default, buen balance)
  heavy   → hqdn3d=6:6:8:8  (agresivo, puede generar ghosting en movimiento)

Espera:
  fuente/video/1_video_sincronizado.mp4  ← Input (del Paso 1)

Genera:
  fuente/video/2_video_denoised.mp4      ← Output limpio

Documentación completa: ../2_reducir-ruido-visual.md
"""

import argparse
import os
import subprocess
import sys

PRESETS = {
    "light": "2:2:3:3",
    "medium": "3:3:4:4",
    "heavy": "6:6:8:8",
}


def main():
    parser = argparse.ArgumentParser(description="Reducir ruido visual con hqdn3d.")
    parser.add_argument("video_dir", help="Carpeta del video")
    parser.add_argument("--input", default="1_video_sincronizado.mp4", help="Video de entrada (default: 1_video_sincronizado.mp4)")
    parser.add_argument("--output", default="2_video_denoised.mp4", help="Video de salida (default: 2_video_denoised.mp4)")
    parser.add_argument("--strength", default="medium", choices=["light", "medium", "heavy"],
                        help="Preset de fuerza (default: medium)")
    parser.add_argument("--custom", default=None,
                        help="Valores custom para hqdn3d (ej: 5:5:6:6)")
    parser.add_argument("--crf", type=int, default=18, help="Calidad CRF (default: 18)")
    parser.add_argument("--preset", default="medium", help="Preset de encoding ffmpeg (default: medium)")

    args = parser.parse_args()

    video_dir = os.path.expanduser(args.video_dir)
    input_path = os.path.join(video_dir, "fuente", "video", args.input)
    output_path = os.path.join(video_dir, "fuente", "video", args.output)

    if not os.path.isfile(input_path):
        print(f"❌ Video no encontrado: {input_path}")
        sys.exit(1)

    hqdn3d_values = args.custom if args.custom else PRESETS[args.strength]

    print(f"📹 Input: {input_path}")
    print(f"📤 Output: {output_path}")
    print(f"⚙️  hqdn3d={hqdn3d_values} | crf={args.crf} | preset={args.preset}")
    print()
    print("🔇 Aplicando denoising temporal...")

    cmd = [
        "ffmpeg", "-i", input_path,
        "-vf", f"hqdn3d={hqdn3d_values}",
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
