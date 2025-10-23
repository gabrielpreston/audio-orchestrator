# Advanced AI Integration - Big Bang Implementation Plan

## Overview

Transform audio-orchestrator with advanced AI capabilities through aggressive 4-6 week implementation focusing on FLAN-T5 integration, Bark TTS with Piper fallback, MetricGAN+ denoising, LangChain orchestration, guardrails, and developer tooling. Move fast, iterate quickly, throw out failing tests.

## Week 1: Foundation & Cleanup

### Dead Code Purge (Days 1-2)

**Remove Deprecated Files:**
- Delete `services/common/service_configs.py` (marked DEPRECATED)
- Update all imports to use `services/common/config/` instead
- Remove TODO comments in:
  - `services/discord/transcription.py`
  - `services/tests/utils/service_helpers.py`
  - `services/orchestrator/agents/conversation_agent.py`

**Documentation Cleanup:**
- Global replace "Discord Voice Lab" → "Audio Orchestrator" in `docs/`
- Update `docs/README.md` with current architecture
- Remove stale roadmap files in `docs/roadmaps/`
- Archive old analysis files in `docs/analysis/archive/`

### FLAN-T5 Service Setup (Days 3-5)

**Create New Service:** `services/llm-flan/`

```python
# services/llm-flan/app.py
from fastapi import FastAPI
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
import torch
import os
from enum import Enum

app = FastAPI()

class ModelSize(Enum):
    BASE = "google/flan-t5-base"      # 1GB RAM
    LARGE = "google/flan-t5-large"    # 8GB RAM
    XL = "google/flan-t5-xl"         # 16GB RAM

# Configurable model selection
MODEL_SIZE = ModelSize(os.getenv("FLAN_T5_MODEL_SIZE", "LARGE"))
MODEL_NAME = MODEL_SIZE.value

# Model loading
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

@app.post("/v1/chat/completions")
async def chat_completions(request: dict):
    # OpenAI-compatible endpoint
    messages = request["messages"]
    prompt = format_instruction_prompt(messages)
    
    inputs = tokenizer(prompt, return_tensors="pt")
    outputs = model.generate(**inputs, max_length=512)
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    return {
        "choices": [{
            "message": {"role": "assistant", "content": response}
        }]
    }

@app.get("/health/ready")
async def health_ready():
    try:
        # Test model loading
        test_input = tokenizer("test", return_tensors="pt")
        test_output = model.generate(**test_input, max_length=10)
        return {"status": "ready", "model": MODEL_NAME}
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}
```

**Dockerfile:**
```dockerfile
# Build stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest AS builder

WORKDIR /app

# Copy service-specific requirements
COPY services/llm-flan/requirements.txt /app/services/llm-flan/requirements.txt
COPY services/requirements-base.txt /app/services/requirements-base.txt
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/llm-flan/requirements.txt

# Runtime stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY services/common /app/services/common
COPY services/llm-flan /app/services/llm-flan
COPY scripts/health_check.py /app/scripts/health_check.py

# Create models directory (models will be downloaded on first run)
RUN mkdir -p /app/models

ENV PORT=8100
ENV FLAN_T5_MODEL_SIZE=google/flan-t5-large

CMD ["uvicorn", "services.llm_flan.app:app", "--host", "0.0.0.0", "--port", "8100"]
```

**Create requirements.txt:** `services/llm-flan/requirements.txt`
```txt
# Include base requirements
-r ../requirements-base.txt

# FLAN-T5 specific dependencies
transformers>=4.57,<5.0
torch>=2.9,<3.0
```

**Update `docker-compose.yml`:**
```yaml
llm-flan:
  build: ./services/llm-flan
  ports: ["8110:8100"]  # External: 8110, Internal: 8100
  env_file:
    - "./.env.common"
    - "./.env.docker"
    - "./services/llm-flan/.env.service"
  environment:
    - MODEL_NAME=${FLAN_T5_MODEL_SIZE:-google/flan-t5-large}
  depends_on:
    audio-processor:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "python", "/app/scripts/health_check.py", "http://localhost:8100/health/ready", "--timeout", "5"]
    interval: 10s
    timeout: 5s
    retries: 3
    start_period: 45s
  deploy:
    resources:
      limits:
        memory: 12G  # Increased for FLAN-T5 Large + overhead
        cpus: "4"
  restart: "unless-stopped"
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "5"
```

**Create Environment File:** `services/llm-flan/.env.service`
```bash
# Model configuration (easy to swap)
FLAN_T5_MODEL_SIZE=google/flan-t5-large
# Alternative options:
# FLAN_T5_MODEL_SIZE=google/flan-t5-base  # 1GB RAM
# FLAN_T5_MODEL_SIZE=google/flan-t5-xl    # 16GB RAM

# Generation parameters
FLAN_T5_MAX_LENGTH=512
FLAN_T5_TEMPERATURE=0.7
FLAN_T5_TOP_P=0.9
PORT=8100
```

**Orchestrator Integration:**
- Update `services/orchestrator/app.py` to call `http://llm-flan:8100` first
- Fallback to existing `llm:8000` on timeout/error
- Add `LLM_PRIMARY_URL=http://llm-flan:8100` env var

## Week 2: Audio Enhancement

### MetricGAN+ Preprocessing Service (Days 6-8)

**Create Service:** `services/audio-preprocessor/`

```python
# services/audio-preprocessor/app.py
from fastapi import FastAPI, UploadFile
from speechbrain.pretrained import SpectralMaskEnhancement
import torchaudio

app = FastAPI()
enhance_model = SpectralMaskEnhancement.from_hparams(
    source="speechbrain/metricgan-plus-voicebank",
    savedir="models/metricgan"
)

@app.post("/denoise")
async def denoise_audio(audio: UploadFile):
    # Load audio
    noisy = enhance_model.load_audio(audio.file)
    
    # Enhance
    enhanced = enhance_model.enhance_batch(noisy, lengths=torch.tensor([1.]))
    
    # Return as WAV
    return enhanced.numpy().tobytes()

@app.post("/denoise/streaming")
async def denoise_streaming(frame: bytes):
    # Real-time frame processing
    enhanced = enhance_model.enhance_batch(
        torch.frombuffer(frame, dtype=torch.float32)
    )
    return enhanced.numpy().tobytes()
```

**Dockerfile:**
```dockerfile
# Build stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest AS builder

WORKDIR /app

# Copy service-specific requirements
COPY services/audio-preprocessor/requirements.txt /app/services/audio-preprocessor/requirements.txt
COPY services/requirements-base.txt /app/services/requirements-base.txt
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/audio-preprocessor/requirements.txt

# Runtime stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY services/common /app/services/common
COPY services/audio-preprocessor /app/services/audio-preprocessor
COPY scripts/health_check.py /app/scripts/health_check.py

# Create models directory
RUN mkdir -p /app/models

ENV PORT=9200
ENV METRICGAN_MODEL_PATH=/app/models/metricgan

CMD ["uvicorn", "services.audio_preprocessor.app:app", "--host", "0.0.0.0", "--port", "9200"]
```

**Create requirements.txt:** `services/audio-preprocessor/requirements.txt`
```txt
# Include base requirements
-r ../requirements-base.txt

# Audio preprocessing specific dependencies
speechbrain>=0.5.16,<1.0
torchaudio>=2.9,<3.0
```

**Docker Configuration:**
```yaml
audio-preprocessor:
  build: ./services/audio-preprocessor
  ports: ["9210:9200"]  # External: 9210, Internal: 9200
  env_file:
    - "./.env.common"
    - "./.env.docker"
    - "./services/audio-preprocessor/.env.service"
  depends_on:
    audio-processor:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "python", "/app/scripts/health_check.py", "http://localhost:9200/health/ready", "--timeout", "5"]
    interval: 10s
    timeout: 5s
    retries: 3
    start_period: 30s
  deploy:
    resources:
      limits:
        memory: 4G   # For MetricGAN+
        cpus: "2"
  restart: "unless-stopped"
```

**Create Environment File:** `services/audio-preprocessor/.env.service`
```bash
METRICGAN_MODEL_PATH=models/metricgan
ENABLE_PREPROCESSING=true
PORT=9200
```

**Integration Points:**
- Insert between Discord audio capture and STT service
- Update `services/discord/discord_voice.py` to call preprocessor
- Add preprocessing to `services/audio_processor/processor.py`

**STT Service Enhancement:**
```python
# services/stt/app.py - Add preprocessing call
async def _preprocess_audio(wav_bytes: bytes) -> bytes:
    if ENABLE_PREPROCESSING:
        response = await preprocessor_client.post("/denoise", 
            files={"audio": wav_bytes})
        return response.content
    return wav_bytes
```

### Bark TTS Integration (Days 9-12)

**Create Enhanced TTS Service:** `services/tts-bark/`

```python
# services/tts-bark/app.py
from fastapi import FastAPI
from bark import SAMPLE_RATE, generate_audio, preload_models
from scipy.io.wavfile import write as write_wav
import numpy as np

app = FastAPI()
preload_models()

VOICE_PRESETS = [
    "v2/en_speaker_0",  # Male voice
    "v2/en_speaker_1",  # Female voice
    "v2/en_speaker_2",  # Male with accent
    "v2/en_speaker_3",  # Female expressive
    "v2/en_speaker_6",  # Male deep
]

@app.post("/synthesize")
async def synthesize(text: str, voice: str = "v2/en_speaker_1"):
    try:
        # Primary: Bark generation
        audio_array = generate_audio(text, history_prompt=voice)
        wav_bytes = audio_to_bytes(audio_array, SAMPLE_RATE)
        return {"audio": wav_bytes, "engine": "bark"}
    except Exception as e:
        # Fallback: Piper
        response = await piper_client.post("/synthesize", json={"text": text})
        return {"audio": response.content, "engine": "piper"}

@app.get("/voices")
async def list_voices():
    return {"bark": VOICE_PRESETS, "piper": ["default"]}
```

**Dockerfile:**
```dockerfile
# Build stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest AS builder

WORKDIR /app

# Copy service-specific requirements
COPY services/tts-bark/requirements.txt /app/services/tts-bark/requirements.txt
COPY services/requirements-base.txt /app/services/requirements-base.txt
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/tts-bark/requirements.txt

# Runtime stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY services/common /app/services/common
COPY services/tts-bark /app/services/tts-bark
COPY scripts/health_check.py /app/scripts/health_check.py

# Create models directory
RUN mkdir -p /app/models

ENV PORT=7100
ENV BARK_USE_SMALL_MODELS=false

CMD ["uvicorn", "services.tts_bark.app:app", "--host", "0.0.0.0", "--port", "7100"]
```

**Create requirements.txt:** `services/tts-bark/requirements.txt`
```txt
# Include base requirements
-r ../requirements-base.txt

# Bark TTS specific dependencies
bark>=1.0.0,<2.0
scipy>=1.11,<2.0
```

**Docker Configuration:**
```yaml
tts-bark:
  build: ./services/tts-bark
  ports: ["7120:7100"]  # External: 7120, Internal: 7100
  env_file:
    - "./.env.common"
    - "./.env.docker"
    - "./services/tts-bark/.env.service"
  environment:
    - BARK_USE_SMALL_MODELS=false
    - PIPER_FALLBACK_URL=http://tts:7000
  depends_on:
    tts:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "python", "/app/scripts/health_check.py", "http://localhost:7100/health/ready", "--timeout", "5"]
    interval: 10s
    timeout: 5s
    retries: 3
    start_period: 30s
  deploy:
    resources:
      limits:
        memory: 6G   # Increased for Bark
        cpus: "2"
  restart: "unless-stopped"
```

**Create Environment File:** `services/tts-bark/.env.service`
```bash
BARK_USE_SMALL_MODELS=false
BARK_VOICE_PRESET=v2/en_speaker_1
PIPER_FALLBACK_URL=http://tts:7000
PORT=7100
```

## Week 3: LangChain & Orchestration

### LangChain Integration (Days 13-15)

**Refactor Orchestrator:** `services/orchestrator-enhanced/`

```python
# services/orchestrator-enhanced/langchain_integration.py
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.llms import OpenAI
from langchain.memory import ConversationBufferMemory
from langchain.tools import Tool

# Prompt versioning
PROMPT_VERSION = "v1.0"
SYSTEM_PROMPT = """You are Atlas, a helpful voice assistant.
You can search information, control devices, and have natural conversations.
Be concise in voice responses (under 50 words preferred)."""

# Create versioned prompt template
prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="chat_history"),
    ("user", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

# Define MCP tools
tools = [
    Tool(
        name="SendDiscordMessage",
        func=send_discord_message,
        description="Send a message to Discord channel"
    ),
    Tool(
        name="SearchWeb",
        func=search_web,
        description="Search the web for information"
    ),
]

# Create agent with FLAN-T5 backend
llm = OpenAI(base_url="http://llm-flan:8100/v1", api_key="dummy")
agent = create_openai_functions_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, memory=memory)

async def process_with_langchain(transcript: str, session_id: str):
    result = await executor.ainvoke({
        "input": transcript,
        "chat_history": get_history(session_id)
    })
    return result["output"]
```

**Replace Existing Agents:**
- Convert `services/orchestrator/agents/conversation_agent.py` to use LangChain
- Convert `services/orchestrator/agents/intent_agent.py` to LangChain classifier
- Convert `services/orchestrator/agents/summarization_agent.py` to LangChain chain
- Keep `services/orchestrator/agents/echo_agent.py` for testing

### Agent Migration (Days 16-18)

**Update Agent Manager:**
```python
# services/orchestrator-enhanced/agents/manager.py
class EnhancedAgentManager:
    def __init__(self):
        self.langchain_executor = create_langchain_executor()
        # Rip out old agents completely - no fallback
        
    async def process_transcript(self, transcript: str, session_id: str):
        try:
            # Primary: LangChain orchestration only
            return await self.langchain_executor.ainvoke({
                "input": transcript,
                "session_id": session_id
            })
        except Exception as e:
            logger.error(f"LangChain processing failed: {e}")
            # Return error response instead of fallback
            return {"error": "Processing failed", "details": str(e)}
```

**Dockerfile:**
```dockerfile
# Build stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest AS builder

WORKDIR /app

# Copy service-specific requirements
COPY services/orchestrator-enhanced/requirements.txt /app/services/orchestrator-enhanced/requirements.txt
COPY services/requirements-base.txt /app/services/requirements-base.txt
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/orchestrator-enhanced/requirements.txt

# Runtime stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY services/common /app/services/common
COPY services/orchestrator-enhanced /app/services/orchestrator-enhanced
COPY scripts/health_check.py /app/scripts/health_check.py

ENV PORT=8200
ENV LLM_PRIMARY_URL=http://llm-flan:8100
ENV LLM_FALLBACK_URL=http://llm:8000
ENV GUARDRAILS_URL=http://guardrails:9300

CMD ["uvicorn", "services.orchestrator_enhanced.app:app", "--host", "0.0.0.0", "--port", "8200"]
```

**Create requirements.txt:** `services/orchestrator-enhanced/requirements.txt`
```txt
# Include base requirements
-r ../requirements-base.txt

# LangChain specific dependencies
langchain>=0.3.0,<1.0
langchain-community>=0.3.0,<1.0
langchain-openai>=0.2.0,<1.0
```

**Docker Configuration:**
```yaml
orchestrator-enhanced:
  build: ./services/orchestrator-enhanced
  ports: ["8220:8200"]  # External: 8220, Internal: 8200
  env_file:
    - "./.env.common"
    - "./.env.docker"
    - "./services/orchestrator-enhanced/.env.service"
  environment:
    - LLM_PRIMARY_URL=http://llm-flan:8100
    - LLM_FALLBACK_URL=http://llm:8000
    - GUARDRAILS_URL=http://guardrails:9300
  depends_on:
    llm-flan:
      condition: service_healthy
    guardrails:
      condition: service_healthy
    audio-processor:
      condition: service_healthy
    stt:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "python", "/app/scripts/health_check.py", "http://localhost:8200/health/ready", "--timeout", "5"]
    interval: 10s
    timeout: 5s
    retries: 3
    start_period: 30s
  deploy:
    resources:
      limits:
        memory: 2G   # LangChain + overhead
        cpus: "2"
  restart: "unless-stopped"
```

## Week 4: Guardrails & Safety

### Guardrails Service (Days 19-21)

**Create Service:** `services/guardrails/`

```python
# services/guardrails/app.py
from fastapi import FastAPI
from transformers import pipeline
import re

app = FastAPI()

# Load models
toxicity_detector = pipeline("text-classification", 
    model="unitary/toxic-bert")
pii_patterns = {
    "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    "phone": r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
    "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
}

@app.post("/validate/input")
async def validate_input(text: str):
    # Prompt injection detection
    if any(dangerous in text.lower() for dangerous in 
           ["ignore previous", "system:", "assistant:", "[INST]"]):
        return {"safe": False, "reason": "prompt_injection"}
    
    # Length check
    if len(text) > 1000:
        return {"safe": False, "reason": "too_long"}
    
    return {"safe": True, "sanitized": text}

@app.post("/validate/output")
async def validate_output(text: str):
    # Toxicity check
    result = toxicity_detector(text)[0]
    if result["label"] == "toxic" and result["score"] > 0.7:
        return {"safe": False, "reason": "toxic_content"}
    
    # PII detection
    for pii_type, pattern in pii_patterns.items():
        if re.search(pattern, text):
            # Redact PII
            text = re.sub(pattern, f"[{pii_type.upper()}_REDACTED]", text)
    
    return {"safe": True, "filtered": text}

@app.post("/escalate")
async def escalate_to_human(context: dict):
    # Log for human review
    logger.warning("Escalation required", extra=context)
    return {"message": "This request requires human review."}
```

**Dockerfile:**
```dockerfile
# Build stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest AS builder

WORKDIR /app

# Copy service-specific requirements
COPY services/guardrails/requirements.txt /app/services/guardrails/requirements.txt
COPY services/requirements-base.txt /app/services/requirements-base.txt
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/guardrails/requirements.txt

# Runtime stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY services/common /app/services/common
COPY services/guardrails /app/services/guardrails
COPY scripts/health_check.py /app/scripts/health_check.py

ENV PORT=9300
ENV TOXICITY_MODEL=unitary/toxic-bert

CMD ["uvicorn", "services.guardrails.app:app", "--host", "0.0.0.0", "--port", "9300"]
```

**Create requirements.txt:** `services/guardrails/requirements.txt`
```txt
# Include base requirements
-r ../requirements-base.txt

# Guardrails specific dependencies
transformers>=4.57,<5.0
torch>=2.9,<3.0
slowapi>=0.1.9,<1.0
```

**Docker Configuration:**
```yaml
guardrails:
  build: ./services/guardrails
  ports: ["9310:9300"]  # External: 9310, Internal: 9300
  env_file:
    - "./.env.common"
    - "./.env.docker"
    - "./services/guardrails/.env.service"
  healthcheck:
    test: ["CMD", "python", "/app/scripts/health_check.py", "http://localhost:9300/health/ready", "--timeout", "5"]
    interval: 10s
    timeout: 5s
    retries: 3
    start_period: 30s
  deploy:
    resources:
      limits:
        memory: 2G   # Toxicity detection
        cpus: "1"
  restart: "unless-stopped"
```

**Create Environment File:** `services/guardrails/.env.service`
```bash
TOXICITY_MODEL=unitary/toxic-bert
ENABLE_PII_DETECTION=true
PORT=9300
```

**Integration:**
```python
# services/orchestrator-enhanced/app.py
@app.post("/mcp/transcript")
async def handle_transcript(request: dict):
    # Input validation
    validation = await guardrails_client.post("/validate/input",
        json={"text": request["transcript"]})
    
    if not validation["safe"]:
        return await guardrails_client.post("/escalate", 
            json={"reason": validation["reason"]})
    
    # Process with LangChain
    response = await langchain_executor.process(validation["sanitized"])
    
    # Output filtering
    filtered = await guardrails_client.post("/validate/output",
        json={"text": response})
    
    return {"response": filtered["filtered"]}
```

### Rate Limiting & Monitoring (Days 22-24)

**Add Rate Limiting:**
```python
# services/guardrails/rate_limiter.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/mcp/transcript")
@limiter.limit("10/minute")
async def handle_transcript(request: Request):
    # Protected endpoint
    pass
```

**Enhanced Metrics:**
```python
# services/common/metrics.py - Add guardrail metrics
guardrail_blocks_total = Counter("guardrail_blocks_total", 
    "Total blocked requests", ["reason"])
guardrail_latency = Histogram("guardrail_latency_seconds",
    "Guardrail check duration")
```

## Week 5: Developer Experience

### Testing UI (Days 25-27)

**Create Gradio Interface:** `services/testing-ui/`

```python
# services/testing-ui/app.py
import gradio as gr
import httpx
import base64

client = httpx.AsyncClient()

async def test_pipeline(audio, text_input, voice_preset):
    if audio:
        # Audio input path
        # 1. Preprocess
        enhanced = await client.post("http://audio-preprocessor:9200/denoise",
            files={"audio": audio})
        
        # 2. Transcribe
        transcript_resp = await client.post("http://stt:9000/transcribe",
            files={"audio": enhanced.content})
        transcript = transcript_resp.json()["text"]
    else:
        transcript = text_input
    
    # 3. Process with orchestrator
    response = await client.post("http://orchestrator-enhanced:8200/mcp/transcript",
        json={"transcript": transcript})
    
    # 4. Synthesize
    tts_resp = await client.post("http://tts-bark:7100/synthesize",
        json={"text": response["response"], "voice": voice_preset})
    
    return transcript, response["response"], tts_resp.content

# Create interface
demo = gr.Interface(
    fn=test_pipeline,
    inputs=[
        gr.Audio(source="microphone", type="filepath", label="Speak"),
        gr.Textbox(label="Or type text input"),
        gr.Dropdown(["v2/en_speaker_0", "v2/en_speaker_1"], 
            label="Voice")
    ],
    outputs=[
        gr.Textbox(label="Transcript"),
        gr.Textbox(label="Response"),
        gr.Audio(label="Audio Output")
    ],
    title="Audio Orchestrator Testing Interface"
)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=8080)
```

**Dockerfile:**
```dockerfile
# Build stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest AS builder

WORKDIR /app

# Copy service-specific requirements
COPY services/testing-ui/requirements.txt /app/services/testing-ui/requirements.txt
COPY services/requirements-base.txt /app/services/requirements-base.txt
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/testing-ui/requirements.txt

# Runtime stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY services/common /app/services/common
COPY services/testing-ui /app/services/testing-ui
COPY scripts/health_check.py /app/scripts/health_check.py

ENV PORT=8080

CMD ["python", "-m", "services.testing_ui.app"]
```

**Create requirements.txt:** `services/testing-ui/requirements.txt`
```txt
# Include base requirements
-r ../requirements-base.txt

# Testing UI specific dependencies
gradio>=4.0,<5.0
```

**Docker Configuration:**
```yaml
testing-ui:
  build: ./services/testing-ui
  ports: ["8080:8080"]
  depends_on:
    - audio-preprocessor
    - stt
    - orchestrator-enhanced
    - tts-bark
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8080/health/ready"]
    interval: 10s
    timeout: 5s
    retries: 3
    start_period: 30s
  deploy:
    resources:
      limits:
        memory: 1G
        cpus: "1"
  restart: "unless-stopped"
```

### Monitoring Dashboard (Days 28-30)

**Create Streamlit Dashboard:** `services/monitoring-dashboard/`

```python
# services/monitoring-dashboard/app.py
import streamlit as st
import pandas as pd
import plotly.express as px
from prometheus_api_client import PrometheusConnect

prom = PrometheusConnect(url="http://prometheus:9090")

st.title("Audio Orchestrator Monitoring")

# Service Health
st.header("Service Health")
health_query = 'service_health_status{component="overall"}'
health_data = prom.custom_query(health_query)
st.metric("Overall Health", f"{health_data[0]['value'][1]}")

# Latency Metrics
st.header("Latency Distribution")
latency_query = 'histogram_quantile(0.95, rate(request_duration_seconds_bucket[5m]))'
latency_data = prom.custom_query_range(latency_query, 
    start_time="now-1h", end_time="now", step="1m")
df = pd.DataFrame(latency_data)
fig = px.line(df, x='timestamp', y='value', title='P95 Latency')
st.plotly_chart(fig)

# Guardrail Stats
st.header("Guardrail Blocks")
blocks_query = 'rate(guardrail_blocks_total[5m])'
blocks_data = prom.custom_query(blocks_query)
for block in blocks_data:
    st.metric(f"Blocked: {block['metric']['reason']}", 
        block['value'][1])
```

**Dockerfile:**
```dockerfile
# Build stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest AS builder

WORKDIR /app

# Copy service-specific requirements
COPY services/monitoring-dashboard/requirements.txt /app/services/monitoring-dashboard/requirements.txt
COPY services/requirements-base.txt /app/services/requirements-base.txt
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/monitoring-dashboard/requirements.txt

# Runtime stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY services/common /app/services/common
COPY services/monitoring-dashboard /app/services/monitoring-dashboard
COPY scripts/health_check.py /app/scripts/health_check.py

ENV PORT=8501

CMD ["streamlit", "run", "services/monitoring_dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

**Create requirements.txt:** `services/monitoring-dashboard/requirements.txt`
```txt
# Include base requirements
-r ../requirements-base.txt

# Monitoring dashboard specific dependencies
streamlit>=1.40,<2.0
plotly>=5.0,<6.0
pandas>=2.0,<3.0
prometheus-api-client>=0.5,<1.0
```

**Docker Configuration:**
```yaml
monitoring-dashboard:
  build: ./services/monitoring-dashboard
  ports: ["8501:8501"]
  depends_on:
    - prometheus
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8501/health/ready"]
    interval: 10s
    timeout: 5s
    retries: 3
    start_period: 30s
  deploy:
    resources:
      limits:
        memory: 1G
        cpus: "1"
  restart: "unless-stopped"
```

## Week 6: Integration & Testing

### System Integration (Days 31-33)

**Update Main Docker Compose:**
```yaml
# docker-compose.yml - Full integration
version: '3.8'
services:
  # Existing services (keep as fallback)
  discord: ...
  stt: ...
  tts: ...
  llm: ...  # Keep as fallback
  orchestrator: ...  # Keep as fallback
  audio-processor: ...
  
  # New enhanced services
  llm-flan:
    build: ./services/llm-flan
    ports: ["8110:8100"]  # External: 8110
  
  audio-preprocessor:
    build: ./services/audio-preprocessor
    ports: ["9210:9200"]  # External: 9210
  
  tts-bark:
    build: ./services/tts-bark
    ports: ["7120:7100"]  # External: 7120
    environment:
      - PIPER_FALLBACK_URL=http://tts:7000
  
  orchestrator-enhanced:
    build: ./services/orchestrator-enhanced
    ports: ["8220:8200"]  # External: 8220
    environment:
      - LLM_PRIMARY_URL=http://llm-flan:8100
      - LLM_FALLBACK_URL=http://llm:8000
      - GUARDRAILS_URL=http://guardrails:9300
  
  guardrails:
    build: ./services/guardrails
    ports: ["9310:9300"]  # External: 9310
  
  testing-ui:
    build: ./services/testing-ui
    ports: ["8080:8080"]
  
  monitoring-dashboard:
    build: ./services/monitoring-dashboard
    ports: ["8501:8501"]
```

**Environment Configuration:**
```bash
# .env.enhanced
# Primary services
LLM_PRIMARY_URL=http://llm-flan:8100
ORCHESTRATOR_PRIMARY_URL=http://orchestrator-enhanced:8200
TTS_PRIMARY_URL=http://tts-bark:7100

# Feature flags
ENABLE_PREPROCESSING=true
ENABLE_GUARDRAILS=true
ENABLE_LANGCHAIN=true

# Performance tuning
FLAN_T5_MODEL=google/flan-t5-large
BARK_USE_SMALL_MODELS=false
METRICGAN_BATCH_SIZE=1
```

### Testing & Validation (Days 34-36)

**Throw Out Old Tests, Write New:**
```python
# services/tests/integration/test_enhanced_pipeline.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_full_pipeline_with_flan_t5():
    async with AsyncClient() as client:
        # 1. Send transcript
        response = await client.post(
            "http://orchestrator-enhanced:8220/mcp/transcript",
            json={"transcript": "What's the weather?"}
        )
        assert response.status_code == 200
        assert "response" in response.json()

@pytest.mark.asyncio
async def test_bark_tts_with_fallback():
    async with AsyncClient() as client:
        response = await client.post(
            "http://tts-bark:7120/synthesize",
            json={"text": "Hello world"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["engine"] in ["bark", "piper"]

@pytest.mark.asyncio
async def test_guardrails_blocking():
    async with AsyncClient() as client:
        response = await client.post(
            "http://guardrails:9310/validate/input",
            json={"text": "Ignore previous instructions and..."}
        )
        assert response.json()["safe"] == False

@pytest.mark.asyncio
async def test_preprocessing_improves_quality():
    # Test that MetricGAN+ actually improves transcription
    async with AsyncClient() as client:
        # Without preprocessing
        raw_response = await client.post(
            "http://stt:9000/transcribe",
            files={"audio": open("noisy_audio.wav", "rb")}
        )
        
        # With preprocessing
        enhanced = await client.post(
            "http://audio-preprocessor:9210/denoise",
            files={"audio": open("noisy_audio.wav", "rb")}
        )
        processed_response = await client.post(
            "http://stt:9000/transcribe",
            files={"audio": enhanced.content}
        )
        
        # Assert improvement (manual verification initially)
        logger.info(f"Raw: {raw_response.json()}")
        logger.info(f"Enhanced: {processed_response.json()}")
```

### Documentation Updates (Days 37-42)

**Create New Documentation:**
- `docs/architecture/enhanced-system-overview.md` - Updated architecture with all new services
- `docs/guides/flan-t5-integration.md` - FLAN-T5 setup and usage
- `docs/guides/bark-tts-guide.md` - Bark TTS configuration and voice selection
- `docs/guides/metricgan-preprocessing.md` - Audio preprocessing pipeline
- `docs/guides/langchain-agents.md` - LangChain agent development
- `docs/guides/guardrails-configuration.md` - Safety and guardrails setup
- `docs/operations/enhanced-monitoring.md` - New monitoring capabilities
- `docs/api/enhanced-api-reference.md` - Complete API documentation

**Update Existing Docs:**
- Replace all references to old services with enhanced versions
- Update `README.md` with new capabilities
- Update `docs/getting-started/` with new setup instructions

## Cutover Strategy

### Pre-Cutover Checklist
- [ ] All new services build successfully
- [ ] Docker compose up starts all services
- [ ] Health checks pass for all services
- [ ] Basic smoke tests pass (send transcript, get response)
- [ ] Testing UI accessible and functional
- [ ] Monitoring dashboard shows metrics

### Cutover Steps

1. **Deploy Enhanced Stack:**
   ```bash
   # Stop old services
   make docker-clean
   
   # Start enhanced services
   docker-compose -f docker-compose.enhanced.yml up -d
   
   # Verify health
   make health-check-all
   ```

2. **Gradual Traffic Shift:**
   - Route 10% traffic to enhanced orchestrator
   - Monitor for 1 hour
   - Increase to 50% if stable
   - Monitor for 4 hours
   - Switch to 100%

3. **Fallback Plan:**
   ```bash
   # If issues detected, quick rollback
   docker-compose -f docker-compose.yml up -d
   ```

### Post-Cutover Monitoring
- Monitor error rates for 48 hours
- Track latency regressions
- Watch guardrail blocks for false positives
- Collect user feedback via testing UI
- Iterate on issues immediately

## Success Metrics
- [ ] FLAN-T5 responding with < 2s latency
- [ ] Bark TTS generating audio (Piper fallback working)
- [ ] MetricGAN+ denoising improves transcription accuracy
- [ ] LangChain orchestration functional
- [ ] Guardrails blocking malicious inputs
- [ ] Testing UI enables rapid iteration
- [ ] All services healthy and stable
- [ ] Documentation complete

## Risk Mitigation
- Keep old services running as fallback
- Feature flags for easy rollback
- Extensive logging for debugging
- Monitoring dashboards for visibility
- Testing UI for rapid validation

## Expected Test Failures
Many existing tests will fail and need rewriting:
- Agent tests (converted to LangChain)
- Orchestrator tests (new service)
- TTS tests (Bark vs Piper differences)
- Integration tests (new pipeline)

**Strategy:** Delete failing tests, write new ones that test actual behavior. Focus on end-to-end integration tests over unit tests.

## Resource Allocation Summary
- **Total RAM Required:** ~26GB (leaves 6GB for system + existing services)
- **FLAN-T5 Large:** 12GB
- **Bark TTS:** 6GB
- **MetricGAN+:** 4GB
- **Orchestrator Enhanced:** 2GB
- **Guardrails:** 2GB
- **Testing UI:** 1GB
- **Monitoring Dashboard:** 1GB

## Port Assignments (Fixed Conflicts)
- **llm-flan:** 8110:8100
- **orchestrator-enhanced:** 8220:8200
- **tts-bark:** 7120:7100
- **audio-preprocessor:** 9210:9200
- **guardrails:** 9310:9300
- **testing-ui:** 8080:8080
- **monitoring-dashboard:** 8501:8501
