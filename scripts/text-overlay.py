#!/usr/bin/env python3
"""
Paso 7 — Text Overlay (Black Card)

Lee `fuente/transcription/overlay-text.md` del folder del video para saber
qué frases mostrar como text cards (fondo negro + texto blanco centrado).

Requiere ffmpeg compilado con --enable-libfreetype (drawtext filter).

Uso:
  python3 text-overlay.py <carpeta-del-video>
  python3 text-overlay.py <carpeta-del-video> --dry-run
  python3 text-overlay.py <carpeta-del-video> --print-cmd

Documentación completa: ../7_text-overlay.md
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


def find_phrase_timestamps(phrase_text, words):
    """Busca una frase en la transcripción word-level y retorna (start, end).
    
    Usa fuzzy matching para tolerar diferencias menores entre el texto
    del segmento y las palabras individuales de Whisper.
    """
    # Normalizar la frase del segmento
    phrase_words = re.findall(r'\w+', phrase_text.lower())
    if not phrase_words:
        return None, None
    
    # Buscar la mejor coincidencia en la lista de palabras
    word_texts = [w['word'].lower().strip(' .,!?¿¡') for w in words]
    
    best_score = 0
    best_start_idx = 0
    best_end_idx = 0
    
    # Ventana deslizante
    window_size = len(phrase_words)
    for i in range(len(word_texts) - window_size + 1):
        window = word_texts[i:i + window_size]
        # Comparar como strings unidos
        window_str = ' '.join(window)
        phrase_str = ' '.join(phrase_words)
        score = SequenceMatcher(None, phrase_str, window_str).ratio()
        
        if score > best_score:
            best_score = score
            best_start_idx = i
            best_end_idx = i + window_size - 1
    
    if best_score < 0.5:
        return None, None
    
    return words[best_start_idx]['start'], words[best_end_idx]['end']


def parse_overlay_text_md(filepath):
    """Parsear overlay-text.md y extraer frases marcadas con >>> y bloques ===."""
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    cards = []
    current_segment_text = None
    current_start = None
    current_end = None
    in_block = False  # Dentro de un bloque ===
    block_id = 0
    
    i = 0
    while i < len(lines):
        line = lines[i].rstrip('\n')
        stripped = line.strip()
        
        # Detectar === (inicio/fin de bloque)
        if stripped == '===' or stripped == '= = =':
            if not in_block:
                in_block = True
                block_id += 1
            else:
                in_block = False
            i += 1
            continue
        
        # Parsear línea de segmento: [MM:SS.xx - MM:SS.xx] (dur) texto
        ts_match = re.match(r'\[(\d+:\d+(?:\.\d+)?)\s*-\s*(\d+:\d+(?:\.\d+)?)\]\s*(?:\(\d+\.?\d*s\)\s*)?(.*)', line)
        if ts_match:
            current_start = parse_timestamp(ts_match.group(1))
            current_end = parse_timestamp(ts_match.group(2))
            current_segment_text = ts_match.group(3).strip()
            i += 1
            continue
        
        # Parsear marca >>> o > > > (Obsidian convierte >>> en blockquotes)
        is_marker = stripped.startswith('>>>') or stripped.startswith('> > >')
        if is_marker:
            if current_segment_text is None:
                i += 1
                continue
            
            # Extraer texto después del marcador
            marker_text = stripped
            if marker_text.startswith('> > >'):
                marker_text = marker_text[5:].strip()
            else:
                marker_text = marker_text[3:].strip()
            
            # Recoger texto de display (puede ser multi-línea)
            display_text = marker_text
            i += 1
            while i < len(lines):
                next_line = lines[i].rstrip('\n')
                next_stripped = next_line.strip()
                # Si es continuación con > > >
                if next_stripped.startswith('> > >'):
                    display_text += '\n' + next_stripped[5:].strip()
                    i += 1
                    continue
                # Si es línea vacía, comentario, nuevo segmento, ===, o otro >>>, parar
                if not next_stripped or next_stripped.startswith('#') or re.match(r'\[(\d+:\d+)', next_line) or next_stripped == '===' or next_stripped == '= = =' or next_stripped.startswith('>>>'):
                    break
                display_text += '\n' + next_stripped
                i += 1
            
            cards.append({
                'segment_text': current_segment_text,
                'segment_start': current_start,
                'segment_end': current_end,
                'display_text': display_text,
                'block_id': block_id if in_block else None,
            })
            continue
        
        i += 1
    
    return cards


def escape_drawtext(text):
    """Escapar texto para drawtext de ffmpeg dentro de un .sh."""
    # ffmpeg drawtext necesita escapar: ', \, :, ;
    text = text.replace('\\', '\\\\')
    text = text.replace("'", "'\\''")
    text = text.replace(':', '\\:')
    text = text.replace(';', '\\;')
    text = text.replace('%', '\\%')
    # $ se interpreta como variable en bash dentro de double quotes
    text = text.replace('$', '\\$')
    return text


def main():
    parser = argparse.ArgumentParser(description="Paso 7 — Text Overlay (Black Card)")
    parser.add_argument("video_dir", help="Carpeta del video")
    parser.add_argument("--video", default="6_video_limpio_logos.mp4", help="Video de entrada (default: 6_video_limpio_logos.mp4)")
    parser.add_argument("--output", default=None, help="Video de salida")
    parser.add_argument("--font", default="/System/Library/Fonts/Helvetica.ttc", help="Ruta a la fuente")
    parser.add_argument("--fontsize", type=int, default=64, help="Tamaño de fuente (default: 64)")
    parser.add_argument("--min-duration", type=float, default=0.0, help="Duración mínima en pantalla en segundos (default: 0 = dura lo que la frase)")
    parser.add_argument("--pad-before", type=float, default=0.3, help="Padding antes de la frase (default: 0.3s)")
    parser.add_argument("--pad-after", type=float, default=0.0, help="Padding después de la frase (default: 0 = corta al terminar)")
    parser.add_argument("--crf", type=int, default=18, help="Calidad CRF (default: 18)")
    parser.add_argument("--preset", default="fast", help="Preset de encoding (default: fast)")
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar detecciones")
    parser.add_argument("--print-cmd", action="store_true", help="Solo imprimir el comando")
    
    args = parser.parse_args()
    
    video_dir = os.path.expanduser(args.video_dir)
    video_path = os.path.join(video_dir, "fuente", "video", args.video)
    overlay_md = os.path.join(video_dir, "fuente", "transcription", "overlay-text.md")
    transcription_json = os.path.join(video_dir, "fuente", "transcription", "transcription_original.json")
    video_out_dir = os.path.join(video_dir, "fuente", "video")
    tmp_dir = os.path.join(video_dir, "tmp")
    
    os.makedirs(tmp_dir, exist_ok=True)
    
    if args.output:
        output_path = os.path.join(video_out_dir, args.output)
    else:
        output_path = os.path.join(video_out_dir, "7_video_text_overlay.mp4")
    
    if not os.path.isfile(video_path):
        print(f"❌ Video no encontrado: {video_path}")
        sys.exit(1)
    if not os.path.isfile(overlay_md):
        print(f"❌ overlay-text.md no encontrado: {overlay_md}")
        sys.exit(1)
    if not os.path.isfile(transcription_json):
        print(f"❌ transcription_original.json no encontrado: {transcription_json}")
        sys.exit(1)
    
    # Cargar transcripción word-level
    with open(transcription_json) as f:
        transcription = json.load(f)
    words = transcription.get('words', [])
    
    # Parsear marcas
    cards = parse_overlay_text_md(overlay_md)
    
    print(f"📹 Video: {video_path}")
    print(f"📋 Overlay: {overlay_md}")
    print(f"📤 Output: {output_path}")
    print(f"⚙️  Font: {args.font} @ {args.fontsize}px")
    print(f"⚙️  Min duration: {args.min_duration}s | Pad: -{args.pad_before}s / +{args.pad_after}s")
    print(f"\n📊 {len(cards)} text cards encontradas\n")
    
    if not cards:
        print("⚠️  No hay frases marcadas con >>>")
        return
    
    # Refinar timestamps con word-level
    # Para cada card, buscar el DISPLAY TEXT en la transcripción word-level
    for card in cards:
        # Buscar el texto de display en el word-level (lo que realmente se dijo)
        word_start, word_end = find_phrase_timestamps(card['display_text'], words)
        if word_start is not None:
            card['start'] = max(0.01, word_start - args.pad_before)
            speech_duration = word_end - word_start + args.pad_before + args.pad_after
            actual_duration = max(speech_duration, args.min_duration)
            card['end'] = card['start'] + actual_duration
            card['source'] = 'word-level (display)'
        else:
            # Fallback: buscar el texto del segmento
            word_start2, word_end2 = find_phrase_timestamps(card['segment_text'], words)
            if word_start2 is not None:
                card['start'] = max(0.01, word_start2 - args.pad_before)
                speech_duration = word_end2 - word_start2 + args.pad_before + args.pad_after
                actual_duration = max(speech_duration, args.min_duration)
                card['end'] = card['start'] + actual_duration
                card['source'] = 'word-level (segment)'
            else:
                card['start'] = max(0.01, card['segment_start'] - args.pad_before)
                speech_duration = card['segment_end'] - card['segment_start'] + args.pad_before + args.pad_after
                actual_duration = max(speech_duration, args.min_duration)
                card['end'] = card['start'] + actual_duration
                card['source'] = 'segment fallback'
    
    # Para bloques: asegurar que cards consecutivas no tengan gaps
    # (el negro debe ser continuo)
    block_ids = set(c['block_id'] for c in cards if c['block_id'] is not None)
    for bid in block_ids:
        block_cards = [c for c in cards if c['block_id'] == bid]
        for j in range(1, len(block_cards)):
            prev = block_cards[j - 1]
            curr = block_cards[j]
            # Si hay gap entre cards del mismo bloque, extender la anterior
            if curr['start'] > prev['end']:
                prev['end'] = curr['start']
            # Si se solapan, ajustar la anterior para que termine donde empieza la siguiente
            elif curr['start'] < prev['end']:
                prev['end'] = curr['start']
    
    for card in cards:
        duration = card['end'] - card['start']
        display_preview = card['display_text'].replace('\n', ' / ')
        block_info = f" [block {card['block_id']}]" if card['block_id'] else ""
        print(f"   [{format_time(card['start'])} - {format_time(card['end'])}] ({duration:.1f}s) [{card['source']}]{block_info}")
        print(f"   → \"{display_preview}\"")
        print()
    
    if args.dry_run:
        print("🏁 Dry run — no se generó video.")
        return
    
    # Generar archivos de texto para cada card (textfile= maneja newlines nativamente)
    cards_dir = os.path.join(tmp_dir, "text_cards")
    os.makedirs(cards_dir, exist_ok=True)
    
    filters = []
    
    for idx, card in enumerate(cards):
        start = card['start']
        end = card['end']
        
        # Escribir texto a archivo, escapando % para drawtext
        card_file = os.path.join(cards_dir, f"card_{idx:03d}.txt")
        escaped_text = card['display_text'].replace('%', '\\%')
        with open(card_file, 'w') as f:
            f.write(escaped_text)
        
        # Fondo negro
        filters.append(
            f"drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:"
            f"enable='between(t,{start:.2f},{end:.2f})'"
        )
        
        # Texto blanco centrado
        filters.append(
            f"drawtext=fontfile='{args.font}':"
            f"textfile='{card_file}':"
            f"fontcolor=white:fontsize={args.fontsize}:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:"
            f"enable='between(t,{start:.2f},{end:.2f})'"
        )
    
    fc = ','.join(filters)
    
    # Escribir .sh
    sh_file = os.path.join(tmp_dir, "text_overlay_cmd.sh")
    with open(sh_file, 'w') as f:
        f.write("#!/bin/bash\nset -e\n")
        f.write(f'ffmpeg -i "{video_path}" '
                f'-vf "{fc}" '
                f'-c:v libx264 -crf {args.crf} -preset {args.preset} '
                f'-c:a copy -y "{output_path}"\n')
    os.chmod(sh_file, 0o755)
    
    if args.print_cmd:
        print(f"📋 Comando en: {sh_file}\n")
        with open(sh_file) as f:
            print(f.read())
        return
    
    print(f"🎬 Aplicando {len(cards)} text cards...")
    print(f"📝 Script: {sh_file}\n")
    
    result = subprocess.run(["bash", sh_file])
    
    if result.returncode != 0:
        print(f"\n❌ Error (código {result.returncode})")
        sys.exit(1)
    
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\n✅ Listo: {output_path} ({size_mb:.0f} MB)")


if __name__ == "__main__":
    main()
