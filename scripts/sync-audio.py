#!/usr/bin/env python3
"""
Sincronizar Audio y Video — Extraer audio SM7B, convertir a estéreo,
detectar offset con cross-correlation, y combinar con video de cámara.

Uso:
  python3 sync-audio.py <carpeta-del-video>
  python3 sync-audio.py <carpeta-del-video> --sony-start 30 --sony-duration 60
  python3 sync-audio.py <carpeta-del-video> --dry-run

Espera esta estructura en el folder:
  fuente/
    video/0_video_original.MP4   ← Video de la cámara (Sony A6400)
    audio/0_audio_original.mkv            ← Grabación OBS (SM7B + video negro)

Genera:
  fuente/audio/1_audio_extraido.aac    ← Audio puro del SM7B
  fuente/audio/1_audio_stereo.wav      ← Audio estéreo (ambos canales)
  fuente/video/1_video_sincronizado.mp4 ← Video + audio sincronizados
  tmp/sony_chunk.wav                  ← Chunk temporal para correlación
  tmp/sm7b_chunk.wav                  ← Chunk temporal para correlación

Documentación completa: ../1_sincronizar-audio-y-video.md
"""

import argparse
import os
import subprocess
import sys

def run(cmd, desc=""):
    """Run a shell command, print description, and check for errors."""
    if desc:
        print(f"  {desc}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Error: {result.stderr[-500:]}")
        sys.exit(1)
    return result


def main():
    parser = argparse.ArgumentParser(description="Sincronizar audio SM7B con video de cámara.")
    parser.add_argument("video_dir", help="Carpeta del video")
    parser.add_argument("--video-file", default="0_video_original.MP4", help="Nombre del video de cámara (default: 0_video_original.MP4)")
    parser.add_argument("--audio-file", default="0_audio_original.mkv", help="Nombre del audio OBS (default: 0_audio_original.mkv)")
    parser.add_argument("--sony-start", type=int, default=30, help="Segundo de inicio para el chunk de Sony (default: 30)")
    parser.add_argument("--sony-duration", type=int, default=60, help="Duración del chunk de Sony en segundos (default: 60)")
    parser.add_argument("--sm7b-duration", type=int, default=90, help="Duración del chunk SM7B en segundos (default: 90)")
    parser.add_argument("--dry-run", action="store_true", help="Solo detectar offset, no generar video")

    args = parser.parse_args()

    video_dir = os.path.expanduser(args.video_dir)
    video_path = os.path.join(video_dir, "fuente", "video", args.video_file)
    audio_path = os.path.join(video_dir, "fuente", "audio", args.audio_file)
    tmp_dir = os.path.join(video_dir, "tmp")

    os.makedirs(tmp_dir, exist_ok=True)

    # Validate inputs
    if not os.path.isfile(video_path):
        print(f"❌ Video no encontrado: {video_path}")
        sys.exit(1)
    if not os.path.isfile(audio_path):
        print(f"❌ Audio no encontrado: {audio_path}")
        sys.exit(1)

    audio_dir = os.path.join(video_dir, "fuente", "audio")
    video_out_dir = os.path.join(video_dir, "fuente", "video")

    audio_extracted = os.path.join(audio_dir, "1_audio_extraido.aac")
    audio_stereo = os.path.join(audio_dir, "1_audio_stereo.wav")
    video_synced = os.path.join(video_out_dir, "1_video_sincronizado.mp4")
    sony_chunk = os.path.join(tmp_dir, "sony_chunk.wav")
    sm7b_chunk = os.path.join(tmp_dir, "sm7b_chunk.wav")

    print(f"📹 Video: {video_path}")
    print(f"🎤 Audio: {audio_path}")
    print()

    # Step 1: Extract audio from OBS file
    print("🔊 Paso 1: Extraer audio del archivo OBS...")
    run(["ffmpeg", "-i", audio_path, "-vn", "-c:a", "copy", "-y", audio_extracted],
        f"→ {audio_extracted}")

    # Step 2: Convert mono to stereo
    print("🔊 Paso 2: Convertir mono → estéreo...")
    run(["ffmpeg", "-i", audio_extracted,
         "-af", "pan=stereo|c0=c0|c1=c0",
         "-c:a", "pcm_s16le",
         "-y", audio_stereo],
        f"→ {audio_stereo}")

    # Step 3: Detect offset via cross-correlation
    print("🔍 Paso 3: Detectar offset (cross-correlation)...")
    print(f"  Extrayendo chunks para comparación...")

    # Extract Sony chunk
    run(["ffmpeg", "-i", video_path, "-vn", "-ac", "1", "-ar", "8000",
         "-ss", str(args.sony_start), "-t", str(args.sony_duration),
         "-y", sony_chunk])

    # Extract SM7B chunk
    run(["ffmpeg", "-i", audio_stereo, "-ac", "1", "-ar", "8000",
         "-t", str(args.sm7b_duration),
         "-y", sm7b_chunk])

    # Cross-correlation in Python
    print("  Calculando cross-correlation...")
    try:
        import numpy as np
        from scipy import signal
        import wave
    except ImportError:
        print("❌ Necesitas numpy y scipy: pip3 install numpy scipy")
        sys.exit(1)

    def read_wav(path):
        with wave.open(path, 'r') as w:
            frames = w.readframes(w.getnframes())
            data = np.frombuffer(frames, dtype=np.int16).astype(np.float64)
            return data, w.getframerate()

    sony, sr = read_wav(sony_chunk)
    sm7b, _ = read_wav(sm7b_chunk)

    win = int(sr * 0.1)
    sony_env = np.convolve(np.abs(sony), np.ones(win) / win, mode='same')
    sm7b_env = np.convolve(np.abs(sm7b), np.ones(win) / win, mode='same')

    corr = signal.correlate(sm7b_env, sony_env, mode='full', method='fft')
    lags = signal.correlation_lags(len(sm7b_env), len(sony_env), mode='full')

    peak_idx = np.argmax(corr)
    lag_samples = lags[peak_idx]
    lag_seconds = lag_samples / sr

    confidence = corr[peak_idx] / np.mean(np.abs(corr))

    sm7b_match_time = lag_seconds
    offset = float(args.sony_start) - sm7b_match_time

    print()
    print(f"📊 Resultado:")
    print(f"   Offset: {offset:.3f}s | Confianza: {confidence:.1f}x")

    if offset > 0:
        print(f"   → SM7B empezó {offset:.3f}s DESPUÉS que la cámara")
        print(f"   → Añadir {offset:.3f}s de silencio al inicio del audio SM7B")
    else:
        print(f"   → SM7B empezó {abs(offset):.3f}s ANTES que la cámara")
        print(f"   → Recortar {abs(offset):.3f}s del inicio del audio SM7B")

    if confidence < 5.0:
        print(f"   ⚠️  Confianza baja ({confidence:.1f}x). Verifica manualmente.")

    if args.dry_run:
        print("\n🏁 Dry run — no se generó video sincronizado.")
        return

    # Step 4: Combine video + synced audio
    print()
    print("🔗 Paso 4: Combinar video + audio sincronizado...")

    delay_ms = int(abs(offset) * 1000)

    if offset > 0:
        # SM7B started later → add delay
        run(["ffmpeg", "-i", video_path, "-i", audio_stereo,
             "-filter_complex", f"[1:a]adelay={delay_ms}|{delay_ms}[delayed_audio]",
             "-map", "0:v", "-map", "[delayed_audio]",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-shortest", "-y", video_synced],
            f"→ {video_synced}")
    else:
        # SM7B started earlier → trim the beginning
        trim_sec = abs(offset)
        run(["ffmpeg", "-i", video_path, "-i", audio_stereo,
             "-filter_complex", f"[1:a]atrim=start={trim_sec},asetpts=PTS-STARTPTS[trimmed_audio]",
             "-map", "0:v", "-map", "[trimmed_audio]",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-shortest", "-y", video_synced],
            f"→ {video_synced}")

    size_mb = os.path.getsize(video_synced) / (1024 * 1024)
    print(f"\n✅ Listo: {video_synced} ({size_mb:.0f} MB)")


if __name__ == "__main__":
    main()
