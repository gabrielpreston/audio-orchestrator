2.1 Key Components

Preprocessing Service (new)

MetricGAN+ denoising: integrate SpeechBrain’s MetricGAN+ model to reduce noise before transcription. The model improves speech clarity by applying spectral mask enhancement and achieves high perceptual scores (PESQ 3.15, STOI 93.0)
dataloop.ai
dataloop.ai
.

Wake‑word/voice‑activity detection: optional future enhancement to avoid unnecessary processing when no speech is present.

STT Service (enhanced)

Primary model: faster‑whisper (or Distil-Whisper). Accepts cleaned audio streams and returns transcribed text.

Fallback: optional external STT API for languages or dialects not supported by Whisper.

Orchestrator/Agent Layer (enhanced)

Uses LangChain (or LangGraph) to manage prompt templates, chain composition and agent logic. LangChain’s four‑layer architecture (model, prompt, chain, agent) encourages separation of concerns
jetthoughts.com
.

MCP integration: register external services (REST APIs, web scraping functions, etc.) as MCP tools. The agent chooses when to call these tools and passes structured requests via MCP. Tool specifications (method, endpoint, parameters) can be stored in a registry.

State management: introduce persistent storage (Redis or a lightweight database) to record conversation sessions and job metadata. Short tasks are handled synchronously; long‑running tasks are scheduled via a background worker (Celery/asyncio). The orchestrator stores job IDs and can return status updates to the user.

Planning agents: adopt planning‑and‑execution patterns from LangChain. Agents can break down complex instructions into subtasks, delegate to sub‑agents and store intermediate results
marktechpost.com
. Memory folding or context compression techniques manage long contexts
marktechpost.com
.

Prompt versioning: store prompts and system messages with version control for safe experimentation
jetthoughts.com
.

LLM Service (enhanced)

Primary model: host a FLAN‑T5 checkpoint locally. FLAN‑T5 uses instruction fine‑tuning, enabling strong zero‑shot/few‑shot performance and efficient inference
byteplus.com
byteplus.com
. This reduces dependence on external APIs.

Fallback model: call an external LLM (e.g., GPT‑4 or LLaMA) when the local model cannot answer or times out. LangChain’s fallback chain pattern provides structured error handling and retry logic
jetthoughts.com
.

Guardrail & Safety Layer (new)

Input sanitization and output filtering: implement runtime guardrails that sanitize user inputs, detect prompt injection, and filter outputs for PII and toxicity. Guardrails enforce policies that models cannot self‑impose
leanware.co
.

Human escalation: for ambiguous or unsafe requests, route the conversation to a human or respond with a fallback message
gladia.io
.

Logging and monitoring: record decisions and flagged events for auditing and continuous improvement
leanware.co
.

TTS Service (enhanced)

Primary model: Bark. Bark is a generative text‑to‑audio model that produces realistic multilingual speech, non‑speech sounds and music
jimmysong.io
docs.openvino.ai
. It uses a GPT‑style model for semantic tokens followed by EnCodec decoding
docs.openvino.ai
, yielding expressive voices and nonverbal cues.

Fallback model: retain piper as a lightweight alternative for environments where Bark cannot run. Use caching for frequently used phrases.

UI & Testing Layer

Streamlit interface: implement a lightweight web UI for developers. 
sider.ai
.

Administrative dashboard: consider building a Streamlit dashboard for monitoring job queues, latency, and user interactions
sider.ai
.

Persistent Data Store

Use a database (e.g., PostgreSQL) or key–value store (Redis) for storing user sessions, conversation history, job statuses and cache of repeated requests.

2.2 Benefits of the Redesign

Improved audio quality: MetricGAN+ denoising enhances transcription accuracy
dataloop.ai
.

Reduced dependency on proprietary APIs: FLAN‑T5 provides local inference with strong zero‑shot capabilities
byteplus.com
.

Expressive output: Bark delivers natural‑sounding speech
docs.openvino.ai
.

Resilience & fault tolerance: fallback strategies at each stage (STT, LLM, TTS) ensure continuity even under failures.

Scalable state tracking: long‑running tasks can be processed asynchronously and resumed from stored state.

Safe interactions: guardrails and human escalation mitigate hallucinations and prevent misuse
gladia.io
.

Extensibility: MCP integration allows the agent to call arbitrary web services using structured tool calls.

3 Data Flow & State Tracking
3.1 End‑to‑End Flow

Audio Ingestion: audio arrives from Discord and is buffered in the Preprocessing service.

Denoising: MetricGAN+ cleans the audio. If the audio is silent (determined by voice‑activity detection), the pipeline does not proceed.

Transcription: the STT service transcribes the denoised audio into text.

Session lookup: the orchestrator queries the persistent store for an existing session; it loads context, job statuses and user preferences. New sessions are created with unique IDs.

Task classification: the orchestrator decides whether the user request is a quick reply or a long‑running task. For simple queries, it constructs a prompt using format_dialog
marktechpost.com
 and sends it to the LLM service. For complex commands (e.g., “summarize all meetings this week and generate action items”), it schedules sub‑tasks via the planning agent.

LLM processing: the primary FLAN‑T5 model generates a response. If the model fails or the request requires external data, the agent uses MCP to call registered tools (e.g., a calendar API) or falls back to an external LLM.
byteplus.com

Guardrail & Output filtering: the response passes through guardrails for PII, hallucination and toxicity checks. Unsafe outputs trigger a fallback or escalation
gladia.io
.

Speech synthesis: the TTS service (Bark or fallback) generates audio from the final text.

Return to user: audio is streamed back to the user. The session and job state are updated in the persistent store.

3.2 State Tracking

Session State: includes conversation history, language preferences, and context variables. Stored in the persistent database and reloaded when the same user interacts again.

Job State: long‑running tasks (e.g., summarizing long documents) are assigned job IDs and stored in a queue. Each job record includes status (pending, running, completed, failed), associated session ID, and result reference.

Memory Folding: for tasks requiring large context windows, the system summarises completed steps and stores summaries in long‑term memory. Techniques from context‑folding agents compress past interactions into succinct summaries
marktechpost.com
.

External Tool State: responses from external API calls (via MCP) are cached and logged along with their invocation parameters for auditability.

4 Dependency Mapping
Layer	Primary Components	Dependencies	Fallback/Notes
Preprocessing	MetricGAN+ (speechbrain)	PyTorch, SpeechBrain, audio stream interface	None (skip if noise is acceptable)
STT	faster‑whisper or Distil‑Whisper	Whisper model weights, CUDA/CPU backend	External STT API
Orchestrator/Agent	LangChain / LangGraph, MCP adapter	Python, LangChain, Redis/DB, MCP tool registry	None – orchestrates fallbacks below
LLM Service	FLAN‑T5 model	HuggingFace transformers, local model weights	External LLM via API (GPT‑4, LLaMA, etc.)
Guardrail Layer	Input & output filters, redaction	Regular expressions, PII detection libs, logging service	Human escalation
TTS	Bark	Suno Bark model weights, EnCodec, audio streaming	Piper (lightweight)
UI & Testing	Streamlit	Streamlit frameworks	CLI for offline testing
Persistence	Redis or PostgreSQL	DB driver (async support), containerized or cloud-hosted	Local file storage for prototypes
External Tools (MCP)	Various API clients (HTTP)	requests, authentication creds, tool definitions	None – design allows adding/removing tools easily
