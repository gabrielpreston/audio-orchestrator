package voice

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strings"
	"time"

	"github.com/discord-voice-lab/internal/logging"
)

// maybeForwardToOrchestrator checks for a wake phrase and forwards the
// aggregated transcript to the configured orchestrator (and TTS if enabled).
// Extracted from processor.go to keep that file focused.
func (p *Processor) maybeForwardToOrchestrator(ssrc uint32, a *transcriptAgg, text string, correlationID string) {
	if orch := os.Getenv("ORCHESTRATOR_URL"); orch != "" {
		matched := a.wakeDetected
		stripped := a.wakeStripped
		if !matched {
			var m bool
			if p.wakeDetector != nil {
				m, stripped = p.wakeDetector.Detect(text)
			}
			matched = m
		}
		if !matched {
			return
		}

		p.mu.Lock()
		uid := p.ssrcMap[ssrc]
		p.mu.Unlock()
		go func(orchestratorURL string, authToken string, uid string, ssrc uint32, text string, correlationID string, stripped string, aCreated time.Time) {
			if p == nil {
				return
			}
			// Build orchestrator request body (OpenAI-style chat completions)
			reqBody := map[string]interface{}{
				"model": "gpt-3.5-turbo",
				"messages": []map[string]string{
					{"role": "system", "content": "You are a helpful assistant."},
					{"role": "user", "content": text},
				},
			}
			rb, _ := json.Marshal(reqBody)
			resp, err := PostWithRetries(p.httpClient, orchestratorURL, rb, authToken, p.orchestratorTimeoutMS, 2, correlationID)
			if err != nil {
				logging.Debugw("orchestrator: POST failed", "err", err, "correlation_id", correlationID)
				return
			}
			defer resp.Body.Close()
			if resp.StatusCode >= 300 {
				body, _ := io.ReadAll(resp.Body)
				logging.Warnw("orchestrator: returned non-2xx", "status", resp.StatusCode, "body", string(body), "correlation_id", correlationID)
				return
			}
			var orchOut map[string]interface{}
			if err := json.NewDecoder(resp.Body).Decode(&orchOut); err != nil {
				logging.Debugw("orchestrator: failed to decode response", "err", err, "correlation_id", correlationID)
				return
			}

			var replyText string
			if choices, ok := orchOut["choices"].([]interface{}); ok && len(choices) > 0 {
				if ch0, ok := choices[0].(map[string]interface{}); ok {
					if msg, ok := ch0["message"].(map[string]interface{}); ok {
						if content, ok := msg["content"].(string); ok {
							replyText = strings.TrimSpace(content)
						}
					}
				}
			}

			if replyText == "" {
				return
			}

			logging.Infow("orchestrator: reply received", "correlation_id", correlationID, "reply_len", len(replyText))
			logging.Debugw("orchestrator: reply text", "correlation_id", correlationID, "reply", replyText)

			// Save reply to sidecar if configured
			if p.saveAudioDir != "" && correlationID != "" {
				upd := map[string]interface{}{
					"orchestrator_reply":                 replyText,
					"orchestrator_response_received_utc": time.Now().UTC().Format(time.RFC3339Nano),
				}
				if procMs, ok := orchOut["processing_ms"].(float64); ok {
					upd["orchestrator_processing_ms"] = int(procMs)
				}
				if p.sidecar != nil {
					_ = p.sidecar.MergeUpdatesForCID(correlationID, upd)
				}
			}

			// Optionally call TTS using configured client
			if p.tts != nil {
				_, _ = p.tts.SynthesizeAndSave(replyText, ssrc, correlationID)
			}
		}(orch, os.Getenv("ORCH_AUTH_TOKEN"), uid, ssrc, strings.TrimSpace(text), correlationID, stripped, a.createdAt)
	}
}

// handleTTS posts replyText to the TTS service, saves returned audio if configured, and updates sidecar.
func (p *Processor) handleTTS(replyText, ttsURL, authToken string, ssrc uint32, correlationID string) {
	b2, _ := json.Marshal(map[string]string{"text": replyText})
	ttsTimeout := 10000
	if p.orchestratorTimeoutMS > 0 {
		ttsTimeout = p.orchestratorTimeoutMS
	}
	resp2, err := PostWithRetries(p.httpClient, ttsURL, b2, authToken, ttsTimeout, 2, correlationID)
	if err != nil {
		logging.Debugw("tts: POST failed", "err", err, "correlation_id", correlationID)
		return
	}
	defer resp2.Body.Close()
	if resp2.StatusCode >= 300 {
		_, _ = io.ReadAll(resp2.Body)
		logging.Warnw("tts: returned non-2xx", "status", resp2.StatusCode, "correlation_id", correlationID)
		return
	}
	audioBytes, rerr := io.ReadAll(resp2.Body)
	if rerr != nil {
		logging.Debugw("tts: failed to read response body", "err", rerr, "correlation_id", correlationID)
		return
	}
	if p.saveAudioDir == "" {
		return
	}
	tsTs := time.Now().UTC().Format("20060102T150405.000Z")
	base := fmt.Sprintf("%s/%s_ssrc%d_tts", strings.TrimRight(p.saveAudioDir, "/"), tsTs, ssrc)
	fname := base + ".wav"
	if err := SaveFileAtomic(fname, audioBytes, 0o644); err != nil {
		logging.Debugw("tts: failed to save wav atomically", "err", err, "path", fname, "correlation_id", correlationID)
		return
	}
	logging.Infow("tts: saved audio to disk", "path", fname, "correlation_id", correlationID)
	if correlationID != "" && p.sidecar != nil {
		_ = p.sidecar.MergeUpdatesForCID(correlationID, map[string]interface{}{
			"tts_wav_path":  fname,
			"tts_saved_utc": time.Now().UTC().Format(time.RFC3339Nano),
		})
	}
}
