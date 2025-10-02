package voice

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/discord-voice-lab/internal/logging"
)

// maybeForwardToOrchestrator checks wake-phrase and forwards the aggregated
// transcript to the configured orchestrator and optional TTS service.
// This mirrors the original logic from processor.go but is extracted to
// keep processor.go smaller.
func (p *Processor) maybeForwardToOrchestrator(ssrc uint32, a *transcriptAgg, text string, correlationID string) {
	if orch := os.Getenv("ORCHESTRATOR_URL"); orch != "" {
		matched := a.wakeDetected
		stripped := a.wakeStripped
		if !matched {
			var m bool
			m, stripped = p.hasWakePhrase(text)
			matched = m
		}
		if !matched {
			return
		}

		// capture uid under lock to avoid data race
		p.mu.Lock()
		uid := p.ssrcMap[ssrc]
		p.mu.Unlock()
		go func(orchestratorURL string, authToken string, uid string, ssrc uint32, text string, correlationID string, stripped string, aCreated time.Time) {
			userContent := stripped
			if userContent == "" {
				userContent = strings.TrimSpace(text)
			}

			chatPayload := map[string]interface{}{
				"model": os.Getenv("ORCHESTRATOR_MODEL"),
				"messages": []map[string]string{
					{"role": "system", "content": fmt.Sprintf("source: discord-voice-lab; user_id: %s; ssrc: %d; correlation_id: %s", uid, ssrc, correlationID)},
					{"role": "user", "content": userContent},
				},
				"correlation_id": correlationID,
			}
			if chatPayload["model"] == "" || chatPayload["model"] == nil {
				delete(chatPayload, "model")
			}

			b, _ := json.Marshal(chatPayload)

			timeoutMs := p.orchestratorTimeoutMS
			if timeoutMs <= 0 {
				timeoutMs = 30000
			}

			resp, err := p.postWithRetries(orchestratorURL, b, authToken, timeoutMs, 3, correlationID)
			if err != nil {
				logging.Debugw("orchestrator: POST failed", "err", err, "correlation_id", correlationID)
				return
			}
			defer resp.Body.Close()

			body, _ := io.ReadAll(resp.Body)
			if resp.StatusCode >= 300 {
				logging.Warnw("orchestrator: returned non-2xx", "status", resp.StatusCode, "correlation_id", correlationID)
				return
			}
			logging.Infow("orchestrator: forwarded transcript", "status", resp.StatusCode, "correlation_id", correlationID)

			var orchOut map[string]interface{}
			if err := json.Unmarshal(body, &orchOut); err != nil {
				logging.Debugw("orchestrator: failed to unmarshal response", "err", err, "correlation_id", correlationID)
				return
			}

			bstr := strings.TrimSpace(string(body))
			if bstr != "" {
				if len(bstr) > 2000 {
					logging.Debugw("orchestrator: response (truncated)", "correlation_id", correlationID, "body_len", len(bstr))
				} else {
					logging.Debugw("orchestrator: response body", "correlation_id", correlationID, "body", bstr)
				}
			}

			// Extract reply text if present
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
				p.updateSidecarForCID(correlationID, upd)
			}

			// Optionally call TTS
			if tts := os.Getenv("TTS_URL"); tts != "" {
				// choose token: prefer TTS_AUTH_TOKEN, fall back to orchestrator authToken
				tok := os.Getenv("TTS_AUTH_TOKEN")
				if tok == "" {
					tok = authToken
				}
				p.handleTTS(replyText, tts, tok, ssrc, correlationID)
			}
		}(orch, os.Getenv("ORCH_AUTH_TOKEN"), uid, ssrc, strings.TrimSpace(text), correlationID, stripped, a.createdAt)
	}
}

// postWithRetries posts JSON payload to url with simple retry/backoff and returns the http.Response.
// Caller is responsible for closing resp.Body.
func (p *Processor) postWithRetries(url string, body []byte, authToken string, timeoutMs int, attempts int, correlationID string) (*http.Response, error) {
	for i := 0; i < attempts; i++ {
		ctxReq, cancelReq := context.WithTimeout(context.Background(), time.Duration(timeoutMs)*time.Millisecond)
		req, rerr := http.NewRequestWithContext(ctxReq, "POST", url, bytes.NewReader(body))
		if rerr != nil {
			logging.Debugw("postWithRetries: new request error", "err", rerr, "correlation_id", correlationID)
			cancelReq()
			return nil, rerr
		}
		req.Header.Set("Content-Type", "application/json")
		if authToken != "" {
			req.Header.Set("Authorization", "Bearer "+authToken)
		}
		client := &http.Client{Timeout: time.Duration(timeoutMs) * time.Millisecond}
		resp, err := client.Do(req)
		cancelReq()
		if err != nil {
			logging.Debugw("postWithRetries: POST attempt failed", "attempt", i+1, "err", err, "correlation_id", correlationID)
			if i < attempts-1 {
				time.Sleep(time.Duration(200*(1<<i)) * time.Millisecond)
				continue
			}
			return nil, err
		}
		return resp, nil
	}
	return nil, fmt.Errorf("no response from postWithRetries")
}

// updateSidecarForCID reads the sidecar for correlationID, merges updates, and writes it back.
func (p *Processor) updateSidecarForCID(correlationID string, updates map[string]interface{}) {
	if path := p.findSidecarPathForCID(correlationID); path != "" {
		sb, rerr := os.ReadFile(path)
		if rerr != nil {
			logging.Debugw("orchestrator: failed to read sidecar for cid", "path", path, "err", rerr, "correlation_id", correlationID)
			return
		}
		var sc map[string]interface{}
		if uerr := json.Unmarshal(sb, &sc); uerr != nil {
			logging.Debugw("orchestrator: failed to unmarshal sidecar JSON", "path", path, "err", uerr, "correlation_id", correlationID)
			return
		}
		for k, v := range updates {
			sc[k] = v
		}
		nb, _ := json.MarshalIndent(sc, "", "  ")
		_ = os.WriteFile(path+".tmp", nb, 0o644)
		_ = os.Rename(path+".tmp", path)
		logging.Infow("orchestrator: saved reply to sidecar", "path", path, "correlation_id", correlationID)
	}
}

// handleTTS posts replyText to the TTS service, saves returned audio if configured, and updates sidecar.
func (p *Processor) handleTTS(replyText, ttsURL, authToken string, ssrc uint32, correlationID string) {
	b2, _ := json.Marshal(map[string]string{"text": replyText})
	ttsTimeout := 10000
	if p.orchestratorTimeoutMS > 0 {
		ttsTimeout = p.orchestratorTimeoutMS
	}
	resp2, err := p.postWithRetries(ttsURL, b2, authToken, ttsTimeout, 2, correlationID)
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
	tmp := fname + ".tmp"
	if err := os.WriteFile(tmp, audioBytes, 0o644); err != nil {
		logging.Debugw("tts: failed to write tmp file", "err", err, "path", tmp, "correlation_id", correlationID)
		return
	}
	if err := os.Rename(tmp, fname); err != nil {
		logging.Debugw("tts: failed to rename tmp file", "err", err, "tmp", tmp, "final", fname, "correlation_id", correlationID)
		_ = os.Remove(tmp)
		return
	}
	logging.Infow("tts: saved audio to disk", "path", fname, "correlation_id", correlationID)
	if correlationID != "" {
		p.updateSidecarForCID(correlationID, map[string]interface{}{
			"tts_wav_path":  fname,
			"tts_saved_utc": time.Now().UTC().Format(time.RFC3339Nano),
		})
	}
}
