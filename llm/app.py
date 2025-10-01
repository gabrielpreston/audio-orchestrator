from flask import Flask, request, jsonify
import subprocess
import shlex
import os

app = Flask(__name__)

LLAMA_BIN = os.path.join('/app/llama.cpp', 'main')
# Allow overriding model path via env var. Default to llama2-7b.gguf for compatibility.
MODEL_PATH = os.environ.get('MODEL_PATH', '/app/models/llama2-7b.gguf')


@app.route('/models')
def list_models():
    models_dir = '/app/models'
    try:
        files = os.listdir(models_dir)
    except FileNotFoundError:
        return jsonify({'models': [], 'error': 'models directory not found'}), 200
    ggufs = [f for f in files if f.lower().endswith('.gguf')]
    return jsonify({'models': ggufs})


@app.route('/health')
def health():
    return jsonify({'status':'ok'})


@app.route('/generate', methods=['POST'])
def generate():
    data = request.json or {}
    prompt = data.get('prompt', '')
    max_tokens = int(data.get('max_tokens', 128))
    temp = float(data.get('temperature', 0.2))

    if not os.path.exists(MODEL_PATH):
        return jsonify({'error': 'model not found', 'model_path': MODEL_PATH}), 500

    cmd = f"{LLAMA_BIN} -m {shlex.quote(MODEL_PATH)} -p {shlex.quote(prompt)} -n {max_tokens} -t 4 -c 1024 -b 512 -r '\n' -temp {temp}"
    try:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            return jsonify({'error':'inference_failed', 'stderr': proc.stderr}), 500
        return jsonify({'output': proc.stdout})
    except subprocess.TimeoutExpired:
        return jsonify({'error':'timeout'}), 504


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
