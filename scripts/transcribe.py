#!/usr/bin/env python3
"""
Paso 5 — Transcripción Word-Level (Whisper API)

Extrae audio del video post-jump-cut y lo transcribe con timestamps
a nivel de palabra. Genera transcription_original.json como fuente de verdad.

Uso:
    python3 transcribe.py ~/ruta/al/folder-del-video
    python3 transcribe.py ~/ruta/al/folder --input 4_video_jumpcut.mp4
    python3 transcribe.py ~/ruta/al/folder --audio-only
    python3 transcribe.py ~/ruta/al/folder --dry-run
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def get_api_key():
    """Busca OPENAI_API_KEY en entorno o en .env de workspace."""
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key

    env_path = Path.home() / ".openclaw" / "workspace" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("OPENAI_API_KEY="):
                return line.split("=", 1)[1].strip()

    return None


def extract_audio(video_path: Path, audio_path: Path, dry_run: bool = False):
    """Extrae audio del video como OGG comprimido."""
    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-vn",                    # sin video
        "-ac", "1",               # mono (Whisper no necesita estéreo)
        "-ar", "16000",           # 16kHz (suficiente para speech)
        "-c:a", "libopus",        # Opus = excelente compresión
        "-b:a", "48k",            # 48kbps (calidad suficiente para STT)
        "-y", str(audio_path)
    ]

    print(f"📎 Extrayendo audio: {video_path.name} → {audio_path.name}")

    if dry_run:
        print(f"   [DRY RUN] {' '.join(cmd)}")
        return

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Error extrayendo audio:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    size_mb = audio_path.stat().st_size / (1024 * 1024)
    print(f"   ✅ Audio extraído: {audio_path.name} ({size_mb:.1f} MB)")


def transcribe_audio(audio_path: Path, api_key: str, model: str, language: str, dry_run: bool = False):
    """Envía audio a Whisper API con word-level timestamps."""
    import urllib.request
    import urllib.error

    url = "https://api.openai.com/v1/audio/transcriptions"

    print(f"🎤 Transcribiendo con Whisper ({model}, idioma: {language})...")

    if dry_run:
        print(f"   [DRY RUN] POST {url}")
        print(f"   model={model}, language={language}, timestamp_granularities=[word, segment]")
        return None

    # Construir multipart form data manualmente
    boundary = "----TranscribePy"
    audio_data = audio_path.read_bytes()
    filename = audio_path.name

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: audio/ogg\r\n\r\n"
    ).encode() + audio_data + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="model"\r\n\r\n'
        f"{model}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="language"\r\n\r\n'
        f"{language}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="response_format"\r\n\r\n'
        f"verbose_json\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="timestamp_granularities[]"\r\n\r\n'
        f"word\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="timestamp_granularities[]"\r\n\r\n'
        f"segment\r\n"
        f"--{boundary}--\r\n"
    ).encode()

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        print(f"❌ Whisper API error {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error llamando a Whisper API: {e}", file=sys.stderr)
        sys.exit(1)

    word_count = len(data.get("words", []))
    segment_count = len(data.get("segments", []))
    print(f"   ✅ Transcripción completa: {word_count} palabras, {segment_count} segmentos")

    return data


def main():
    parser = argparse.ArgumentParser(description="Paso 5 — Transcripción Word-Level (Whisper API)")
    parser.add_argument("video_dir", help="Carpeta del video")
    parser.add_argument("--input", default="4_video_jumpcut.mp4", help="Video de entrada (en fuente/video/)")
    parser.add_argument("--output", default="transcription_original.json", help="Archivo de salida (en fuente/transcription/)")
    parser.add_argument("--model", default="whisper-1", help="Modelo de Whisper")
    parser.add_argument("--language", default="es", help="Idioma del audio")
    parser.add_argument("--audio-only", action="store_true", help="Solo extraer audio, no transcribir")
    parser.add_argument("--dry-run", action="store_true", help="Mostrar qué haría sin ejecutar")

    args = parser.parse_args()

    video_dir = Path(args.video_dir).expanduser().resolve()
    if not video_dir.is_dir():
        print(f"❌ No existe la carpeta: {video_dir}", file=sys.stderr)
        sys.exit(1)

    video_path = video_dir / "fuente" / "video" / args.input
    if not video_path.exists() and not args.dry_run:
        print(f"❌ No existe el video: {video_path}", file=sys.stderr)
        sys.exit(1)

    # Crear directorios
    transcripcion_dir = video_dir / "fuente" / "transcription"
    tmp_dir = video_dir / "tmp"

    if not args.dry_run:
        transcripcion_dir.mkdir(parents=True, exist_ok=True)
        tmp_dir.mkdir(parents=True, exist_ok=True)

    audio_path = tmp_dir / "audio_for_whisper.ogg"
    output_path = transcripcion_dir / args.output

    print(f"📁 Video dir: {video_dir}")
    print(f"🎬 Input: {video_path.name}")
    print(f"📄 Output: {output_path.relative_to(video_dir)}")
    print()

    # Paso 1: Extraer audio
    extract_audio(video_path, audio_path, dry_run=args.dry_run)

    if args.audio_only:
        print(f"\n🏁 Audio extraído en: {audio_path}")
        return

    # Paso 2: Transcribir
    api_key = get_api_key()
    if not api_key and not args.dry_run:
        print("❌ No se encontró OPENAI_API_KEY en el entorno ni en ~/.openclaw/workspace/.env", file=sys.stderr)
        print("   Exportala con: export OPENAI_API_KEY=sk-...", file=sys.stderr)
        sys.exit(1)

    data = transcribe_audio(audio_path, api_key, args.model, args.language, dry_run=args.dry_run)

    if data and not args.dry_run:
        output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        print(f"\n🏁 Transcripción guardada en: {output_path.relative_to(video_dir)}")

        # Stats
        duration_s = data.get("duration", 0)
        if duration_s:
            mins = int(duration_s // 60)
            secs = int(duration_s % 60)
            print(f"   ⏱️  Duración: {mins}:{secs:02d}")

    if args.dry_run:
        print("\n🏁 [DRY RUN] No se ejecutó nada.")


if __name__ == "__main__":
    main()
