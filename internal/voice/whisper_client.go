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

// buildWAV creates a simple RIFF/WAVE header for 16-bit PCM and returns the
// concatenated bytes (header + data). sampleRate in Hz, channels, bitsPerSample
// (commonly 16) are used to populate the header.
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

// sendPCMToWhisper wraps raw PCM16LE into a WAV and POSTs it to WHISPER_URL.
// It retries up to 3 times with exponential backoff for transient errors.
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
					b, err := os.ReadFile(path)
					if err != nil {
						logging.Warnw("failed to read sidecar for cid", "path", path, "err", err)
					} else {
						var sc map[string]interface{}
						if uerr := json.Unmarshal(b, &sc); uerr == nil {
							sc["stt_request_sent_utc"] = sendTs.UTC().Format(time.RFC3339Nano)
							sc["stt_response_received_utc"] = respReceivedTs.UTC().Format(time.RFC3339Nano)
							sc["stt_latency_ms"] = sttLatencyMs
							if sttServerMs > 0 {
								sc["stt_server_ms"] = sttServerMs
							}
							if endToEndMs > 0 {
								sc["end_to_end_ms"] = endToEndMs
							}
							sc["stt_status"] = resp.StatusCode
							if transcript != "" {
								sc["transcript"] = transcript
							}
							if segs, ok := out["segments"]; ok && segs != nil {
								sc["segments"] = segs
							}
							nb, _ := json.MarshalIndent(sc, "", "  ")
							_ = os.WriteFile(path+".tmp", nb, 0o644)
							_ = os.Rename(path+".tmp", path)
						} else {
							logging.Debugw("failed to unmarshal sidecar JSON", "path", path, "err", uerr)
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
