package voice

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"sync/atomic"
	"time"

	"github.com/discord-voice-lab/internal/logging"
)

// buildWAV creates a RIFF/WAVE header and appends PCM16LE data.
// sampleRate is in Hz; bitsPerSample is typically 16.
func buildWAV(pcm []byte, sampleRate, channels, bitsPerSample int) []byte {
	byteRate := uint32(sampleRate * channels * bitsPerSample / 8)
	blockAlign := uint16(channels * bitsPerSample / 8)
	dataLen := uint32(len(pcm))
	riffSize := uint32(4 + (8 + 16) + (8 + dataLen))

	buf := &bytes.Buffer{}
	buf.WriteString("RIFF")
	binary.Write(buf, binary.LittleEndian, riffSize)
	buf.WriteString("WAVE")
	buf.WriteString("fmt ")
	binary.Write(buf, binary.LittleEndian, uint32(16))
	binary.Write(buf, binary.LittleEndian, uint16(1))
	binary.Write(buf, binary.LittleEndian, uint16(channels))
	binary.Write(buf, binary.LittleEndian, uint32(sampleRate))
	binary.Write(buf, binary.LittleEndian, uint32(byteRate))
	binary.Write(buf, binary.LittleEndian, blockAlign)
	binary.Write(buf, binary.LittleEndian, uint16(bitsPerSample))
	buf.WriteString("data")
	binary.Write(buf, binary.LittleEndian, uint32(dataLen))
	buf.Write(pcm)
	return buf.Bytes()
}

// sendPCMToWhisper wraps PCM into a WAV and POSTs it to WHISPER_URL.
// Retries up to 3 times with exponential backoff on transient failures.
func (p *Processor) sendPCMToWhisper(ssrc uint32, pcmBytes []byte, correlationID string, accumCreatedAt time.Time, capturedUserID string, capturedUsername string) error {
	whisper := os.Getenv("WHISPER_URL")
	if whisper == "" {
		logging.Warnw("WHISPER_URL not set, dropping audio", "ssrc", ssrc, "correlation_id", correlationID)
		return fmt.Errorf("WHISPER_URL not set")
	}

	whisperURL := whisper
	if u, err := url.Parse(whisper); err == nil {
		q := u.Query()
		if v := os.Getenv("WHISPER_TRANSLATE"); v != "" {
			lv := strings.ToLower(strings.TrimSpace(v))
			if lv == "1" || lv == "true" || lv == "yes" {
				q.Set("task", "translate")
			}
		}
		if v := os.Getenv("STT_BEAM_SIZE"); v != "" {
			if _, err := strconv.Atoi(v); err == nil {
				q.Set("beam_size", v)
			}
		}
		if v := os.Getenv("STT_LANGUAGE"); v != "" {
			q.Set("language", v)
		}
		if v := os.Getenv("STT_WORD_TIMESTAMPS"); v != "" {
			lv := strings.ToLower(strings.TrimSpace(v))
			if lv == "1" || lv == "true" || lv == "yes" {
				q.Set("word_timestamps", "1")
			}
		}
		u.RawQuery = q.Encode()
		whisperURL = u.String()
	}

	wav := buildWAV(pcmBytes, 48000, 1, 16)

	// Optionally save decoded WAV and initial sidecar JSON for troubleshooting
	if p.saveAudioDir != "" && correlationID != "" {
		// determine user id / username for filename
		uid := capturedUserID
		if uid == "" {
			p.mu.Lock()
			uid = p.ssrcMap[ssrc]
			p.mu.Unlock()
		}
		username := capturedUsername
		if username == "" {
			if p.resolver != nil {
				if n := p.resolver.UserName(uid); n != "" {
					username = n
				}
			}
		}
		if username == "" {
			username = "unknown"
		}
		// safe filename: replace spaces with underscore
		safeName := strings.ReplaceAll(username, " ", "_")
		tsTs := time.Now().UTC().Format("20060102T150405.000Z")
		base := fmt.Sprintf("%s/%s_ssrc%d_%s", strings.TrimRight(p.saveAudioDir, "/"), tsTs, ssrc, safeName)
		wavPath := base + ".wav"
		jsonPath := base + ".json"

		// Save WAV; ignore errors but log them at debug level so operators can inspect
		if err := SaveFileAtomic(wavPath, wav, 0o644); err != nil {
			logging.Debugw("saveaudio: failed to write decoded wav", "err", err, "path", wavPath, "correlation_id", correlationID)
		} else {
			logging.Infow("saveaudio: wrote decoded wav", "path", wavPath, "correlation_id", correlationID)
		}

		// create initial sidecar JSON containing correlation id and created timestamp
		sc := map[string]interface{}{
			"correlation_id":    correlationID,
			"accum_created_utc": accumCreatedAt.UTC().Format(time.RFC3339Nano),
			"wav_path":          wavPath,
		}
		if b, err := json.MarshalIndent(sc, "", "  "); err == nil {
			if err := SaveFileAtomic(jsonPath, b, 0o644); err != nil {
				logging.Debugw("saveaudio: failed to write sidecar json", "err", err, "path", jsonPath, "correlation_id", correlationID)
			} else {
				logging.Infow("saveaudio: wrote sidecar json", "path", jsonPath, "correlation_id", correlationID)
			}
		} else {
			logging.Debugw("saveaudio: failed to marshal sidecar json", "err", err, "correlation_id", correlationID)
		}
	}

	var lastErr error
	for attempt := 0; attempt < 3; attempt++ {
		reqCtx, cancel := context.WithTimeout(p.ctx, time.Duration(p.whisperTimeoutMS)*time.Millisecond)
		req, err := http.NewRequestWithContext(reqCtx, "POST", whisperURL, bytes.NewReader(wav))
		if err != nil {
			cancel()
			lastErr = err
			break
		}
		req.Header.Set("Content-Type", "audio/wav")
		if correlationID != "" {
			req.Header.Set("X-Correlation-ID", correlationID)
		}
		sendTs := time.Now()
		durationMs := 0
		if len(pcmBytes) > 0 {
			samples := len(pcmBytes) / 2
			durationMs = (samples * 1000) / 48000
			uid := capturedUserID
			if uid == "" {
				p.mu.Lock()
				uid = p.ssrcMap[ssrc]
				p.mu.Unlock()
			}
			logging.Debugw("sending audio to whisper", "ssrc", ssrc, "url", whisperURL, "correlation_id", correlationID, "bytes", len(pcmBytes), "samples", samples, "duration_ms", durationMs, "user_id", uid)
		} else {
			logging.Debugw("sending audio to whisper", "ssrc", ssrc, "url", whisperURL, "correlation_id", correlationID)
		}

		resp, err := p.httpClient.Do(req)
		cancel()
		if err != nil {
			atomic.AddInt64(&p.sendFailCount, 1)
			lastErr = err
			logging.Warnw("HTTP send error to whisper", "ssrc", ssrc, "err", err, "attempt", attempt)
			backoff := time.Duration(1<<attempt) * time.Second
			time.Sleep(backoff)
			continue
		}
		respReceivedTs := time.Now()
		defer resp.Body.Close()

		if resp.StatusCode >= 500 {
			atomic.AddInt64(&p.sendFailCount, 1)
			lastErr = fmt.Errorf("server error status=%d", resp.StatusCode)
			logging.Warnw("STT server error", "ssrc", ssrc, "status", resp.StatusCode, "attempt", attempt)
			backoff := time.Duration(1<<attempt) * time.Second
			time.Sleep(backoff)
			continue
		}

		var out map[string]interface{}
		if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
			lastErr = err
			return err
		}

		sttLatencyMs := int(respReceivedTs.Sub(sendTs).Milliseconds())
		sttServerMs := 0
		if v := resp.Header.Get("X-Processing-Time-ms"); v != "" {
			if n, err := strconv.Atoi(v); err == nil {
				sttServerMs = n
			}
		}
		if sttServerMs == 0 {
			if sv, ok := out["processing_ms"]; ok {
				switch t := sv.(type) {
				case float64:
					sttServerMs = int(t)
				case int:
					sttServerMs = t
				case int64:
					sttServerMs = int(t)
				case string:
					if n, err := strconv.Atoi(t); err == nil {
						sttServerMs = n
					}
				}
			}
		}

		endToEndMs := 0
		if p.saveAudioDir != "" && correlationID != "" {
			if p.sidecar != nil {
				if path := p.sidecar.FindByCID(correlationID); path != "" {
					if b, err := os.ReadFile(path); err == nil {
						var sc map[string]interface{}
						if err := json.Unmarshal(b, &sc); err == nil {
							if ac, ok := sc["accum_created_utc"].(string); ok && ac != "" {
								if t, err := time.Parse(time.RFC3339Nano, ac); err == nil {
									endToEndMs = int(respReceivedTs.Sub(t).Milliseconds())
								}
							}
						}
					}
				}
			}
		}

		atomic.AddInt64(&p.sendCount, 1)
		uid := capturedUserID
		username := capturedUsername
		if uid == "" {
			p.mu.Lock()
			uid = p.ssrcMap[ssrc]
			p.mu.Unlock()
		}
		if username == "" {
			if p.resolver != nil {
				if n := p.resolver.UserName(uid); n != "" {
					username = n
				}
			}
		}
		if username == "" {
			username = "unknown"
		}
		logging.Infow("STT response received", "ssrc", ssrc, "user", username, "user_id", uid, "correlation_id", correlationID, "status", resp.StatusCode, "stt_latency_ms", sttLatencyMs, "stt_server_ms", sttServerMs, "end_to_end_ms", endToEndMs)

		transcript := ""
		if t, ok := out["text"].(string); ok {
			transcript = strings.TrimSpace(t)
		}

		if fw := os.Getenv("TEXT_FORWARD_URL"); fw != "" && transcript != "" {
			go func(forwardURL string, uid string, ssrc uint32, text string, cid string, sendTs, respTs time.Time, sttLatencyMs, sttServerMs, endToEndMs int) {
				payload := map[string]interface{}{
					"user_id":                   uid,
					"ssrc":                      ssrc,
					"transcript":                text,
					"correlation_id":            cid,
					"stt_request_sent_utc":      sendTs.UTC().Format(time.RFC3339Nano),
					"stt_response_received_utc": respTs.UTC().Format(time.RFC3339Nano),
					"stt_latency_ms":            sttLatencyMs,
					"stt_server_ms":             sttServerMs,
					"end_to_end_ms":             endToEndMs,
				}
				b, _ := json.Marshal(payload)
				req, err := http.NewRequestWithContext(context.Background(), "POST", forwardURL, bytes.NewReader(b))
				if err != nil {
					return
				}
				req.Header.Set("Content-Type", "application/json")
				c := &http.Client{Timeout: 5 * time.Second}
				resp, err := c.Do(req)
				if err != nil {
					return
				}
				defer resp.Body.Close()
			}(fw, uid, ssrc, transcript, correlationID, sendTs, respReceivedTs, sttLatencyMs, sttServerMs, endToEndMs)
		}

		if p.saveAudioDir != "" && correlationID != "" {
			if p.sidecar != nil {
				if path := p.sidecar.FindByCID(correlationID); path != "" {
					// Build update map and let SidecarManager handle read/merge/write
					upd := map[string]interface{}{
						"stt_request_sent_utc":      sendTs.UTC().Format(time.RFC3339Nano),
						"stt_response_received_utc": respReceivedTs.UTC().Format(time.RFC3339Nano),
						"stt_latency_ms":            sttLatencyMs,
						"stt_status":                resp.StatusCode,
					}
					if sttServerMs > 0 {
						upd["stt_server_ms"] = sttServerMs
					}
					if endToEndMs > 0 {
						upd["end_to_end_ms"] = endToEndMs
					}
					if transcript != "" {
						upd["transcript"] = transcript
					}
					if segs, ok := out["segments"]; ok && segs != nil {
						upd["segments"] = segs
					}
					if p.sidecar != nil {
						if err := p.sidecar.MergeUpdatesForCID(correlationID, upd); err != nil {
							logging.Warnw("failed to update sidecar via manager", "cid", correlationID, "err", err)
						}
					}
				}
			}
		}

		_, strippedText := p.wakeDetector.Detect(transcript)
		if transcript != "" {
			p.addAggregatedTranscript(ssrc, username, transcript, correlationID, accumCreatedAt, strippedText)
		}
		return nil
	}
	return lastErr
}
