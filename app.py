import asyncio
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import uuid
import webbrowser
from concurrent.futures import ThreadPoolExecutor

import edge_tts
from flask import Flask, jsonify, render_template, request, send_file
from PIL import Image, ImageOps, UnidentifiedImageError

ROOT = Path(__file__).resolve().parent
ENGINE = Path(os.environ.get('SADTALKER_DIR', ROOT / 'vendor' / 'SadTalker')).resolve()
ENGINE_PYTHON = os.environ.get('SADTALKER_PYTHON', str(ROOT / '.engine' / 'Scripts' / 'python.exe'))
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 12 * 1024 * 1024
pool = ThreadPoolExecutor(max_workers=1)
jobs = {}
lock = threading.Lock()
VOICES = {'es-ES-ElviraNeural': 'Elvira · España', 'es-ES-AlvaroNeural': 'Álvaro · España', 'es-MX-DaliaNeural': 'Dalia · México', 'es-MX-JorgeNeural': 'Jorge · México'}


def readiness():
    missing = []
    if not (ENGINE / 'inference.py').exists():
        missing.append('Falta instalar SadTalker.')
    if not Path(ENGINE_PYTHON).is_file() or (not os.environ.get('SADTALKER_PYTHON') and not (ROOT / '.engine' / 'ready').exists()):
        missing.append('Falta el entorno de SadTalker.')
    if not all((ENGINE / 'checkpoints' / name).exists() for name in ('SadTalker_V0.0.2_256.safetensors', 'mapping_00109-model.pth.tar')):
        missing.append('Falta descargar el modelo de SadTalker.')
    if not shutil.which('ffmpeg'):
        missing.append('Falta FFmpeg en PATH.')
    return missing


def update(job_id, **values):
    with lock:
        jobs[job_id].update(values)


def generate(job_id, text, voice, motion):
    folder = DATA / job_id
    try:
        update(job_id, status='working', message='Creando la voz…')
        asyncio.run(edge_tts.Communicate(text, voice, rate='-5%').save(str(folder / 'voice.mp3')))
        subprocess.run(['ffmpeg', '-y', '-i', str(folder / 'voice.mp3'), '-ar', '16000', '-ac', '1', str(folder / 'voice.wav')], check=True, capture_output=True, timeout=120)
        update(job_id, message='Animando el rostro. Puede tardar varios minutos…')
        command = [ENGINE_PYTHON, str(ENGINE / 'inference.py'), '--source_image', str(folder / 'portrait.png'), '--driven_audio', str(folder / 'voice.wav'), '--result_dir', str(folder / 'results'), '--checkpoint_dir', str(ENGINE / 'checkpoints'), '--size', '256', '--batch_size', '1', '--preprocess', 'full', '--expression_scale', '1.0']
        if motion == 'subtle':
            command.append('--still')
        with (folder / 'engine.log').open('w', encoding='utf-8') as log:
            subprocess.run(command, cwd=ENGINE, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=3600)
        videos = list((folder / 'results').glob('*.mp4'))
        if not videos:
            raise RuntimeError('No se ha generado un vídeo. Comprueba que la foto tiene una cara visible.')
        update(job_id, message='Preparando el MP4 para descargar…')
        subprocess.run(['ffmpeg', '-y', '-i', str(max(videos, key=lambda p: p.stat().st_mtime)), '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-movflags', '+faststart', str(folder / 'video.mp4')], check=True, capture_output=True, timeout=300)
        update(job_id, status='done', message='Tu vídeo está listo.', video=f'/api/jobs/{job_id}/video')
    except subprocess.TimeoutExpired:
        update(job_id, status='error', message='La generación ha superado el tiempo máximo. Prueba con un texto más corto.')
    except Exception as error:
        with (folder / 'error.log').open('w', encoding='utf-8') as log:
            log.write(str(error))
        update(job_id, status='error', message='No se pudo generar el vídeo. Revisa la conexión para la voz, la foto y el registro en data/' + job_id + '. Si falta memoria, cierra otras aplicaciones que usen la GPU.')


@app.get('/')
def index():
    return render_template('index.html', voices=VOICES)


@app.get('/api/health')
def health():
    missing = readiness()
    return jsonify(ready=not missing, message='Listo para generar' if not missing else ' '.join(missing))


@app.post('/api/jobs')
def create_job():
    text = request.form.get('text', '')
    voice = request.form.get('voice', '')
    motion = request.form.get('motion', 'natural')
    upload = request.files.get('image')
    if not text.strip() or len(text) > 1500 or voice not in VOICES or motion not in ('natural', 'subtle') or upload is None:
        return jsonify(message='Selecciona una imagen, una voz y un texto de entre 1 y 1500 caracteres.'), 400
    missing = readiness()
    if missing:
        return jsonify(message=' '.join(missing) + ' Ejecuta instalar.ps1.'), 503
    with lock:
        if any(job['status'] in ('queued', 'working') for job in jobs.values()):
            return jsonify(message='Hay un vídeo en proceso. Espera a que termine.'), 409
        job_id = uuid.uuid4().hex
        jobs[job_id] = dict(status='queued', message='Preparando…')
    folder = DATA / job_id
    folder.mkdir()
    try:
        with Image.open(upload.stream) as source:
            if source.format not in ('JPEG', 'PNG', 'WEBP'):
                raise ValueError('Formato no admitido')
            image = ImageOps.exif_transpose(source).convert('RGB')
            image.thumbnail((2048, 2048))
            image.save(folder / 'portrait.png')
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        update(job_id, status='error', message='Imagen no válida.')
        return jsonify(message='Usa una imagen JPG, PNG o WebP válida.'), 400
    pool.submit(generate, job_id, text, voice, motion)
    return jsonify(id=job_id), 202


@app.get('/api/jobs/<job_id>')
def job_status(job_id):
    with lock:
        job = jobs.get(job_id)
        return (jsonify(dict(job)), 200) if job else (jsonify(message='Vídeo no encontrado.'), 404)


@app.get('/api/jobs/<job_id>/video')
def video(job_id):
    with lock:
        job = jobs.get(job_id)
    if not job or job['status'] != 'done':
        return jsonify(message='El vídeo todavía no está disponible.'), 404
    return send_file(DATA / job_id / 'video.mp4', mimetype='video/mp4', as_attachment=request.args.get('download') == '1', download_name='mi-video.mp4', conditional=True)


@app.errorhandler(413)
def too_large(_error):
    return jsonify(message='La imagen debe ocupar menos de 12 MB.'), 413


if __name__ == '__main__':
    if '--open' in sys.argv:
        timer = threading.Timer(1.5, lambda: webbrowser.open('http://127.0.0.1:7860'))
        timer.daemon = True
        timer.start()
    app.run(host='127.0.0.1', port=7860, debug=False)
