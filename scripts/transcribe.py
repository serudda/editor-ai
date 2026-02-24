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


def format_ts(seconds):
    """Formatear segundos a M:SS.xx"""
    m = int(seconds // 60)
    s = seconds % 60
    if s == int(s):
        return f"{m}:{int(s):02d}"
    return f"{m}:{s:05.2f}"


def merge_segments(segments, max_duration=20.0):
    """Reagrupa segmentos de Whisper en frases completas.
    
    Whisper corta segmentos por tiempo, no por gramática. Esto produce frases
    cortadas a mitad de oración. Esta función junta segmentos consecutivos hasta
    encontrar un final natural de frase (., ?, !, :) o hasta alcanzar max_duration.
    
    Resultado: bloques de ~5-20s con frases completas, sin palabras cortadas.
    """
    import re
    
    if not segments:
        return []
    
    # Patrones que indican final de frase
    end_pattern = re.compile(r'[.?!:。？！]$')
    
    merged = []
    current_start = segments[0].get("start", 0)
    current_texts = []
    current_end = segments[0].get("end", 0)
    
    for i, seg in enumerate(segments):
        text = seg.get("text", "").strip()
        end = seg.get("end", 0)
        start = seg.get("start", 0)
        
        # Mirar si el SIGUIENTE segmento es muy corto (remate de frase)
        next_is_short = False
        if i + 1 < len(segments):
            next_seg = segments[i + 1]
            next_dur = next_seg.get("end", 0) - next_seg.get("start", 0)
            next_is_short = next_dur < 3.0
        
        # Si agregar este segmento excedería max_duration, cerrar el actual
        # PERO no cortar si el segmento actual es un remate corto del anterior
        seg_duration = end - start if start > 0 else end
        is_short_tail = seg_duration < 3.0 and current_texts
        
        if current_texts and (end - current_start) > max_duration and not is_short_tail:
            merged.append({
                "start": current_start,
                "end": current_end,
                "text": " ".join(current_texts)
            })
            current_start = start
            current_texts = []
        
        current_texts.append(text)
        current_end = end
        
        # Si termina en puntuación final Y el siguiente no es un remate corto, cerrar
        if end_pattern.search(text) and not next_is_short:
            merged.append({
                "start": current_start,
                "end": current_end,
                "text": " ".join(current_texts)
            })
            current_start = end
            current_texts = []
    
    # Último bloque si quedó algo
    if current_texts:
        merged.append({
            "start": current_start,
            "end": current_end,
            "text": " ".join(current_texts)
        })
    
    return merged


def generate_clean_transcription(data, video_name, output_path):
    """Genera transcription_limpia.md — transcripción legible con timestamps.
    
    Este archivo es la BASE para todos los overlays (text, logos, broll, images).
    Cada paso copia este archivo y agrega sus propias marcas.
    
    Proceso:
    1. Toma los segmentos de Whisper (que cortan a mitad de frase)
    2. Los reagrupa en frases completas (~5-20s, cortando en puntuación)
    3. Genera un markdown legible con timestamps e instrucciones
    """
    segments = data.get("segments", [])
    words = data.get("words", [])
    duration_s = data.get("duration", 0)

    # Reagrupar segmentos en frases completas
    merged = merge_segments(segments, max_duration=20.0)
    
    lines = []
    lines.append(f"# Transcripción Limpia — {video_name}")
    lines.append(f"#")
    lines.append(f"# Generado automáticamente por transcribe.py (Paso 5)")
    lines.append(f"# Duración: {format_ts(duration_s)} ({int(duration_s)}s)")
    lines.append(f"# Palabras: {len(words)} | Segmentos originales: {len(segments)} | Reagrupados: {len(merged)}")
    lines.append(f"#")
    lines.append(f"# No editar directamente. Regenerar: python3 scripts/transcribe.py $VIDEO --clean-only")
    lines.append("")

    for seg in merged:
        start = seg["start"]
        end = seg["end"]
        text = seg["text"]
        duration = end - start

        lines.append(f"[{format_ts(start)} - {format_ts(end)}] ({duration:.1f}s) {text}")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Paso 5 — Transcripción Word-Level (Whisper API)")
    parser.add_argument("video_dir", help="Carpeta del video")
    parser.add_argument("--input", default="4_video_jumpcut.mp4", help="Video de entrada (en fuente/video/)")
    parser.add_argument("--output", default="transcription_original.json", help="Archivo de salida (en fuente/transcription/)")
    parser.add_argument("--model", default="whisper-1", help="Modelo de Whisper")
    parser.add_argument("--language", default="es", help="Idioma del audio")
    parser.add_argument("--audio-only", action="store_true", help="Solo extraer audio, no transcribir")
    parser.add_argument("--clean-only", action="store_true", help="Solo regenerar transcription_limpia.md desde el JSON existente")
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

    # Modo --clean-only: solo regenerar transcription_limpia.md
    if args.clean_only:
        if not output_path.exists():
            print(f"❌ No existe {output_path.name}. Corre primero la transcripción completa.", file=sys.stderr)
            sys.exit(1)
        data = json.loads(output_path.read_text())
        limpia_path = transcripcion_dir / "transcription_limpia.md"
        generate_clean_transcription(data, video_path.name, limpia_path)
        print(f"✅ Transcripción limpia regenerada: {limpia_path.relative_to(video_dir)}")
        return

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
        print(f"\n✅ Transcripción guardada en: {output_path.relative_to(video_dir)}")

        # Stats
        duration_s = data.get("duration", 0)
        if duration_s:
            mins = int(duration_s // 60)
            secs = int(duration_s % 60)
            print(f"   ⏱️  Duración: {mins}:{secs:02d}")

        # Generar transcripción limpia
        limpia_path = transcripcion_dir / "transcription_limpia.md"
        generate_clean_transcription(data, video_path.name, limpia_path)
        print(f"✅ Transcripción limpia: {limpia_path.relative_to(video_dir)}")

    if args.dry_run:
        print("\n🏁 [DRY RUN] No se ejecutó nada.")


if __name__ == "__main__":
    main()
