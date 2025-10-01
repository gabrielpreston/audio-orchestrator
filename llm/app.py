from flask import Flask, request, jsonify
import os
import subprocess
import logging
import time
import uuid

# Minimal LLM service: health + respond
app = Flask(__name__)

# Configuration via env
LLAMA_BIN = os.environ.get('LLAMA_BIN', '/app/llama.cpp/build/bin/llama-cli')
MODEL_PATH = os.environ.get('MODEL_PATH', '/app/models/llama2-7b.gguf')


# Basic structured logger helper to follow project conventions.
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'info').upper()
logger = logging.getLogger('llm')
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))


def log_kv(level, msg, **fields):
    """Log a message with key=value pairs appended for easy parsing.
    This keeps logs readable while providing structured data.
    """
    kv = ' '.join([f"{k}={repr(v)}" for k, v in fields.items()])
    full = f"{msg} {kv}" if kv else msg
    if level == 'info':
        logger.info(full)
    elif level == 'debug':
        logger.debug(full)
    elif level == 'warn' or level == 'warning':
        logger.warning(full)
    elif level == 'error':
        logger.error(full)
    else:
        logger.info(full)


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


@app.route('/respond', methods=['POST'])
def respond():
    """Accept JSON {"transcript": str, "max_tokens": int, "temperature": float}
    and return JSON {"output": str} or error details.
    """
    data = request.json or {}
    transcript = data.get('transcript', '')
    if not transcript:
        return jsonify({'error': 'missing_transcript'}), 400

    max_tokens = int(data.get('max_tokens', 128))
    temperature = float(data.get('temperature', 0.2))

    if not os.path.exists(MODEL_PATH):
        log_kv('error', 'respond: model missing', model_path=MODEL_PATH)
        return jsonify({'error': 'model_not_found', 'model_path': MODEL_PATH}), 500

    if not os.path.exists(LLAMA_BIN) or not os.access(LLAMA_BIN, os.X_OK):
        log_kv('error', 'respond: llama binary missing', llama_bin=LLAMA_BIN)
        return jsonify({'error': 'llama_bin_not_found', 'llama_bin': LLAMA_BIN}), 500

    # Build command. Use a list to avoid shell quoting issues.
    cmd = [LLAMA_BIN, '-m', MODEL_PATH, '-p', transcript, '-n', str(max_tokens), '--temp', str(temperature)]

    # Correlation id for tracing across logs
    cid = str(uuid.uuid4())
    log_kv('info', 'respond: started', correlation_id=cid, prompt_len=len(transcript), model=MODEL_PATH, llama_bin=LLAMA_BIN)

    start = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        duration = time.time() - start
        log_kv('warn', 'respond: timeout', correlation_id=cid, duration_ms=int(duration*1000))
        return jsonify({'error': 'timeout'}), 504
    except Exception as e:
        duration = time.time() - start
        log_kv('error', 'respond: exec failed', correlation_id=cid, duration_ms=int(duration*1000), exc=str(e))
        return jsonify({'error': 'exec_failed', 'detail': str(e)}), 500

    duration = time.time() - start
    if proc.returncode != 0:
        log_kv('error', 'respond: inference failed', correlation_id=cid, returncode=proc.returncode, duration_ms=int(duration*1000), stderr=proc.stderr[:1024])
        return jsonify({'error': 'inference_failed', 'stderr': proc.stderr}), 500

    # Success
    log_kv('info', 'respond: success', correlation_id=cid, returncode=proc.returncode, duration_ms=int(duration*1000), out_len=len(proc.stdout))
    return jsonify({'output': proc.stdout})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
