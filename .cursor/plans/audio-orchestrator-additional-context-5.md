Below is a high‑level definition of the interfaces between each component in the redesigned Voice Agent and a description of how data flows through the system. Each interface abstracts away implementation details and focuses on the inputs, outputs and responsibilities of the services.

1. Audio Input & Preprocessing Interface

From: Discord voice gateway (or the test UI).

To: Preprocessing Service.

Data: Raw audio stream (PCM or Opus frames) tagged with a session ID.

Operation: The Preprocessing service applies noise reduction (MetricGAN+) and optional voice‑activity detection. It emits a cleaned audio stream. If silence is detected, it stops the pipeline to avoid unnecessary processing.

2. Preprocessing → STT Interface

From: Preprocessing Service.

To: STT Service.

Data: Cleaned audio stream and session metadata (language preferences, user ID, timestamp).

Operation: The STT service transcribes the audio to text using Whisper or a fallback API. It returns a transcript object containing the text, timing metadata and confidence scores.

3. STT → Orchestrator/Agent Interface

From: STT Service.

To: Orchestrator/Agent.

Data: Transcript object ({session_id, text, confidence, start_time, end_time}).

Operation: The orchestrator loads the session state (conversation history, pending jobs) and appends the new transcript to the conversation context. It then classifies the user request (quick reply vs. long task).

4. Orchestrator ↔ LLM Service Interface

From: Orchestrator.

To: LLM Service.

Data: Prompt package ({session_id, system_prompt, conversation_history, current_query}).

Operation: The orchestrator sends the prompt to the primary FLAN‑T5 model; the LLM service returns a response object ({session_id, text_response, usage, model_id, fallback_used}).

Fallback: If the primary model fails or the orchestrator deems external reasoning necessary, it sends the same prompt to a fallback LLM (e.g., GPT‑4) and records which model was used.

5. Orchestrator ↔ MCP/Tool Adapter Interface

From: Orchestrator/Agent.

To: MCP Adapter.

Data: Tool call object ({tool_name, parameters, session_id}).

Operation: When the LLM suggests calling an external tool, the orchestrator validates the request against allowed tool definitions and forwards it via MCP. The adapter performs HTTP/API calls to the external service and returns the results in a structured format ({tool_name, result_data, status}).

Safety: Guardrails inspect tool requests for unsafe parameters; disallowed calls are blocked.

6. Orchestrator ↔ Guardrail Layer Interface

From: Orchestrator.

To: Guardrail Service.

Data: Proposed input or output text ({session_id, phase (input|output), content}).

Operation: The guardrail service performs input sanitization (prompt injection detection) and output filtering (PII redaction, toxicity checks). It returns either the sanitized content or a flagged status requiring human escalation.

7. Orchestrator ↔ Persistence/State Store Interface

From/To: Orchestrator.

Data: Session state ({session_id, conversation_history, language, user preferences}), job state ({job_id, status, assigned_subtasks, results}), cached API responses and prompt versions.

Operation: The orchestrator reads existing state when a request arrives and writes updates after each step. For long‑running tasks it writes intermediate results and job status so it can report progress or resume after failure.

8. Orchestrator → TTS Service Interface

From: Orchestrator.

To: TTS Service.

Data: Final text response ({session_id, text_response, voice_profile}).

Operation: The TTS service uses Bark to generate a speech waveform. It returns audio data (e.g., WAV or Opus frames) along with metadata (duration, sampling rate). If Bark fails, the service uses Piper as a fallback and logs the fallback usage.

9. TTS Service → Output Interface

From: TTS Service.

To: Discord voice gateway (or test UI).

Data: Encoded audio stream ready for playback.

Operation: The audio is streamed back to the client. The orchestrator logs the completion time and updates the job/session state.

10. Test UI ↔ Orchestrator Interface

From/To: Streamlit UI.

Data: User text/audio input and responses mirrored from the orchestrator.

Operation: The UI allows developers to input text or record audio, view transcripts, view LLM responses and play synthesized audio. It mirrors the same internal interfaces as Discord, enabling quick iteration.

Data Flow Summary

Audio flows from Discord/UI through preprocessing to STT.

Transcript flows to the orchestrator, which consults state and decides next steps.

Prompts and tool calls flow to the LLM service and MCP adapter; results flow back.

Guardrails intercept user requests and LLM outputs for safety checks.

State updates persist throughout, ensuring long tasks can be resumed or monitored.

Text responses flow to TTS for synthesis, then audio flows back to the user.