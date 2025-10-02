package voice

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/bwmarrin/discordgo"
	"github.com/discord-voice-lab/internal/logging"
	"github.com/google/uuid"
	"github.com/hraban/opus"
)


	// start flusher for transcript aggregation
	p.wg.Add(1)
	go func() {
		defer p.wg.Done()
		ticker := time.NewTicker(200 * time.Millisecond)
		defer ticker.Stop()
		for {
			select {
			case <-p.ctx.Done():
				return
			case <-ticker.C:
				p.flushExpiredAggs()
			}
		}
	}()

	return p, nil
}

// SetAllowedUsers configures an explicit allow-list of user IDs. When the
// allowlist is non-empty, ProcessOpusFrame will drop frames whose mapped
// user ID is known and not present in the allowlist. Passing an empty slice
// clears the allowlist and restores normal behavior.
func (p *Processor) SetAllowedUsers(ids []string) {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.allowlist = make(map[string]struct{}, len(ids))
	for _, id := range ids {
		if id == "" {
			continue
		}
		p.allowlist[id] = struct{}{}
	}
	// log configured allowlist size
	logging.Infow("Processor: SetAllowedUsers", "count", len(p.allowlist))
}

func (p *Processor) Close() error {
	logging.Infow("Processor: Close called")
	// stop background workers
	p.cancel()
	// close channel to unblock worker if it's waiting
	close(p.opusCh)
	p.wg.Wait()
	return nil
}

// SeedVoiceChannelMembers enumerates the session state's voice states for
// the given guild and channel and populates an internal userID->display
// name cache. This helps provide immediate names for participants when the
// processor starts handling audio for a channel (note: this does not map
// SSRC -> userID; that still comes from speaking updates).
func (p *Processor) SeedVoiceChannelMembers(s *discordgo.Session, guildID, channelID string) {
	if s == nil || guildID == "" || channelID == "" {
		return
	}
	// Create a local map so we can batch update under the processor mutex
	m := make(map[string]string)
	if s.State != nil {
		if gs, err := s.State.Guild(guildID); err == nil && gs != nil {
			for _, vs := range gs.VoiceStates {
				if vs.ChannelID != channelID {
					continue
				}
				uid := vs.UserID
				if uid == "" {
					continue
				}
				// Try resolver first if present
				name := ""
				if p.resolver != nil {
					name = p.resolver.UserName(uid)
				}
				// Fall back to session REST lookup if resolver didn't return a name
				if name == "" {
					if u, err := s.User(uid); err == nil && u != nil {
						name = u.Username
					}
				}
				if name == "" {
					name = uid
				}
				m[uid] = name
			}
		}
	}
	if len(m) == 0 {
		return
	}
	p.mu.Lock()
	if p.userDisplay == nil {
		p.userDisplay = make(map[string]string)
	}
	for k, v := range m {
		p.userDisplay[k] = v
	}
	p.mu.Unlock()
}

// HandleVoiceState listens for voice state updates to map userID <-> SSRC (best-effort)
func (p *Processor) HandleVoiceState(s *discordgo.Session, vs *discordgo.VoiceStateUpdate) {
	// Include human-friendly names when available via resolver (unused after logging removed).
	if p.resolver != nil {
		if n := p.resolver.UserName(vs.UserID); n != "" {
			logging.Debugw("Processor: VoiceState update", logging.UserFields(vs.UserID, n)...)
		} else {
			logging.Debugw("Processor: VoiceState update", "user_id", vs.UserID)
		}
	}
}

// HandleSpeakingUpdate receives discordgo speaking updates and is used to map ssrc->user
func (p *Processor) HandleSpeakingUpdate(s *discordgo.Session, su *discordgo.VoiceSpeakingUpdate) {
	// map SSRC to user
	p.mu.Lock()
	defer p.mu.Unlock()
	p.ssrcMap[uint32(su.SSRC)] = su.UserID
	// Backfill any existing accumulator's user info to avoid unknown user in sidecars
	p.accumMu.Lock()
	if a, ok := p.accums[uint32(su.SSRC)]; ok {
		a.userID = su.UserID
		if p.resolver != nil && su.UserID != "" {
			if n := p.resolver.UserName(su.UserID); n != "" {
				a.username = strings.ReplaceAll(n, " ", "_")
			} else {
				a.username = su.UserID
			}
		} else {
			a.username = su.UserID
		}
	}
	p.accumMu.Unlock()
	// resolver lookup retained for potential future use
	// Log mapping at info level so operator can see when SSRCs are associated
	logging.Infow("Processor: HandleSpeakingUpdate: mapped SSRC -> user", "ssrc", su.SSRC, "user_id", su.UserID)
}

// This function would be called by the discord voice receive loop with raw opus frames.
// For simplicity in this scaffold, we'll expose a method to accept encoded opus frames and process them.
func (p *Processor) ProcessOpusFrame(ssrc uint32, opusPayload []byte) {
	// If an allowlist is configured and we already know which user this SSRC
	// maps to, drop frames from non-allowed users early to avoid unnecessary
	// decoding and HTTP requests.
	p.mu.Lock()
	uid := p.ssrcMap[ssrc]
	// copy allowlist reference for check
	allowCount := len(p.allowlist)
	_, allowed := p.allowlist[uid]
	p.mu.Unlock()

	if allowCount > 0 && uid != "" && !allowed {
		// logging removed: dropping frame from non-allowed user
		return
	}

	// Determine a correlation ID to propagate with the packet so early logs
	// (enqueue time) can include it. Prefer any existing accumulator's ID;
	// otherwise generate one if we're configured to save audio.
	// Always ensure an accumulator exists and has a correlation ID so STT
	// requests include it. Previously this was gated on saveAudioDir; assign
	// unconditionally (small UUID cost) to enable end-to-end tracing.
	var outgoingCID string
	// Read the SSRC->user mapping under p.mu *before* acquiring accumMu so
	// we don't hold both locks at once. This avoids the previous data race
	// where appendAccum read p.ssrcMap without synchronization.
	p.mu.Lock()
	preUid := p.ssrcMap[ssrc]
	p.mu.Unlock()
	preUname := "unknown"
	if preUid != "" && p.resolver != nil {
		if n := p.resolver.UserName(preUid); n != "" {
			preUname = strings.ReplaceAll(n, " ", "_")
		}
	}

	p.accumMu.Lock()
	if a, ok := p.accums[ssrc]; ok && a.correlationID != "" {
		outgoingCID = a.correlationID
	} else {
		outgoingCID = uuid.NewString()
		if !ok {
			// Use the pre-captured user info when creating the accumulator so
			// it contains the correct mapping even if a speaking update races in.
			p.accums[ssrc] = &pcmAccum{samples: nil, last: time.Now(), correlationID: outgoingCID, createdAt: time.Now(), userID: preUid, username: preUname}
			logging.Debugw("generated correlation id for new accumulator", "user_id", preUid, "user_name", preUname, "ssrc", ssrc, "correlation_id", outgoingCID)
		} else {
			p.accums[ssrc].correlationID = outgoingCID
			logging.Debugw("assigned correlation id to existing accumulator", "ssrc", ssrc, "correlation_id", outgoingCID)
		}
	}
	p.accumMu.Unlock()

	// enqueue for background processing; drop if queue full to avoid blocking
	select {
	case p.opusCh <- opusPacket{ssrc: ssrc, data: append([]byte(nil), opusPayload...), correlationID: outgoingCID}:
		// increment enqueue counter and log enqueue for diagnostics
		atomic.AddInt64(&p.enqueueCount, 1)
		if outgoingCID != "" {
			logging.Debugw("opus frame enqueued", "ssrc", ssrc, "correlation_id", outgoingCID)
		} else {
			logging.Debugw("opus frame enqueued", "ssrc", ssrc)
		}
	default:
		atomic.AddInt64(&p.dropQueueCount, 1)
		logging.Warnw("dropping opus frame; queue full", "ssrc", ssrc)
	}
}

// handleOpusPacket implementation moved to decoder.go

// appendAccum adds decoded samples to the per-SSRC accumulator.
// appendAccum adds decoded samples to the per-SSRC accumulator and returns
// the accumulator's correlation ID (if any). The returned correlation ID is
// generated when a new accumulator is created and is used to correlate
// saved WAVs and STT requests/logs for that chunk.
// appendAccum adds decoded samples to the per-SSRC accumulator and returns
// the accumulator's correlation ID (if any). If an incomingCID is provided
// it will be preferred when creating or populating the accumulator.
// appendAccum implementation moved to decoder.go

// flushAccum implementation moved to decoder.go

// flushExpiredAccums implementation moved to decoder.go

// sendPCMToWhisper implementation moved to whisper_client.go

// addAggregatedTranscript appends/inserts a transcript into the per-SSRC
// aggregation buffer and updates the timestamp. The flusher will emit
// combined transcripts after aggMs of inactivity.
func (p *Processor) addAggregatedTranscript(ssrc uint32, username, text string, correlationID string, createdAt time.Time, strippedText string) {
	p.aggMu.Lock()
	defer p.aggMu.Unlock()
	a, ok := p.aggs[ssrc]
	if !ok {
		a = &transcriptAgg{text: text, last: time.Now(), correlationID: correlationID, createdAt: createdAt}
		if strippedText != "" {
			a.wakeDetected = true
			a.wakeStripped = strippedText
		}
		p.aggs[ssrc] = a
		return
	}
	// Append with a space separator if existing text is non-empty
	if a.text != "" {
		a.text = strings.TrimSpace(a.text) + " " + strings.TrimSpace(text)
	} else {
		a.text = strings.TrimSpace(text)
	}
	a.last = time.Now()
	// If correlationID not set on existing agg, set it when provided
	if a.correlationID == "" && correlationID != "" {
		a.correlationID = correlationID
	}
	if a.createdAt.IsZero() && !createdAt.IsZero() {
		a.createdAt = createdAt
	}
	// preserve true once set: do not clear an existing wakeDetected flag
	if strippedText != "" {
		a.wakeDetected = true
		// prefer the first seen stripped text
		if a.wakeStripped == "" {
			a.wakeStripped = strippedText
		}
	}
}

// flushExpiredAggs checks aggregation buffers and flushes ones that have
// been inactive longer than aggMs.
func (p *Processor) flushExpiredAggs() {
	now := time.Now()
	var toFlush []uint32
	p.aggMu.Lock()
	for ssrc, a := range p.aggs {
		if now.Sub(a.last) >= time.Duration(p.aggMs)*time.Millisecond {
			toFlush = append(toFlush, ssrc)
		}
	}
	p.aggMu.Unlock()
	for _, s := range toFlush {
		p.flushAgg(s)
	}
}

// flushAgg emits the aggregated transcript for an SSRC (logs + optional forward)
func (p *Processor) flushAgg(ssrc uint32) {
	p.aggMu.Lock()
	a, ok := p.aggs[ssrc]
	if !ok {
		p.aggMu.Unlock()
		return
	}
	text := a.text
	corrID := a.correlationID
	delete(p.aggs, ssrc)
	p.aggMu.Unlock()
	if text == "" {
		return
	}
	// Resolve username for logging/forwarding
	p.mu.Lock()
	uid := p.ssrcMap[ssrc]
	p.mu.Unlock()
	username := uid
	if p.resolver != nil {
		if n := p.resolver.UserName(uid); n != "" {
			username = n
		}
	}
	if username == "" {
		username = "unknown"
	}
	// Also forward to TEXT_FORWARD_URL if configured (reuse same payload logic)
	if fw := os.Getenv("TEXT_FORWARD_URL"); fw != "" {
		go func(forwardURL string, uid string, ssrc uint32, text string) {
			payload := map[string]interface{}{
				"user_id":    uid,
				"ssrc":       ssrc,
				"transcript": text,
			}
			b, _ := json.Marshal(payload)
			req, err := http.NewRequestWithContext(context.Background(), "POST", forwardURL, bytes.NewReader(b))
			if err != nil {
				// logging removed: text forward new request error
				return
			}
			req.Header.Set("Content-Type", "application/json")
			c := &http.Client{Timeout: 5 * time.Second}
			resp, err := c.Do(req)
			if err != nil {
				// logging removed: text forward POST failed
				return
			}
			defer resp.Body.Close()
			if resp.StatusCode >= 300 {
				// logging removed: text forward returned non-2xx
			} else {
				// logging removed: forwarded transcript
			}
		}(fw, uid, ssrc, strings.TrimSpace(text))
	}

	// Forward aggregated transcript to an optional orchestrator / LLM service
	// only when the transcript begins with a configured wake phrase. This
	// avoids sending background speech to downstream processing. The set of
	// wake phrases may be configured via WAKE_PHRASES (comma-separated).
	// ORCHESTRATOR_URL: OpenAI-compatible chat completions endpoint (e.g. http://orch:8000/v1/chat/completions)
	// ORCH_AUTH_TOKEN: optional bearer token to include in Authorization header.
	if orch := os.Getenv("ORCHESTRATOR_URL"); orch != "" {
		// check wake phrase: prefer aggregated wakeDetected (set from STT
		// segments when available). If not set, fall back to the textual
		// check which uses the configured window heuristic.
		matched := a.wakeDetected
		stripped := a.wakeStripped
		if !matched {
			// fallback to a text-based check and use its stripped text
			var m bool
			m, stripped = p.hasWakePhrase(text)
			matched = m
		}
		if !matched {
			// not matching wake phrase; skip orchestrator/TTS forwarding
			return
		} else {
			// use stripped text for the user content
			go func(orchestratorURL string, authToken string, uid string, ssrc uint32, text string, correlationID string) {
				// Build an OpenAI-compatible chat request. Include a short system message
				// with metadata so the orchestrator can use it if desired.
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
					// include correlation_id in top-level payload for easier downstream tracing
					"correlation_id": correlationID,
				}
				// If model is empty, remove it to let the server pick a default
				if chatPayload["model"] == "" || chatPayload["model"] == nil {
					delete(chatPayload, "model")
				}
				b, _ := json.Marshal(chatPayload)
				// Use configured orchestrator timeout (fallback to 30s) and retry a few times
				timeoutMs := p.orchestratorTimeoutMS
				if timeoutMs <= 0 {
					timeoutMs = 30000
				}
				attempts := 3
				var resp *http.Response
				var err error
				for i := 0; i < attempts; i++ {
					ctxReq, cancelReq := context.WithTimeout(context.Background(), time.Duration(timeoutMs)*time.Millisecond)
					req, rerr := http.NewRequestWithContext(ctxReq, "POST", orchestratorURL, bytes.NewReader(b))
					if rerr != nil {
						logging.Debugw("orchestrator: new request error", "err", rerr, "correlation_id", correlationID)
						cancelReq()
						err = rerr
						break
					}
					req.Header.Set("Content-Type", "application/json")
					if authToken != "" {
						req.Header.Set("Authorization", "Bearer "+authToken)
					}
					client := &http.Client{Timeout: time.Duration(timeoutMs) * time.Millisecond}
					resp, err = client.Do(req)
					cancelReq()
					if err != nil {
						logging.Debugw("orchestrator: POST attempt failed", "attempt", i+1, "err", err, "correlation_id", correlationID)
						if i < attempts-1 {
							time.Sleep(time.Duration(200*(1<<i)) * time.Millisecond)
							continue
						}
						// final failure
						return
					}
					// Received response; stop retrying
					break
				}
				if resp == nil {
					logging.Debugw("orchestrator: no response received", "correlation_id", correlationID)
					return
				}
				defer resp.Body.Close()
				body, _ := io.ReadAll(resp.Body)
				if resp.StatusCode >= 300 {
					logging.Warnw("orchestrator: returned non-2xx", "status", resp.StatusCode, "correlation_id", correlationID)
					return
				}
				logging.Infow("orchestrator: forwarded transcript", "status", resp.StatusCode, "correlation_id", correlationID)

				// Parse OpenAI-style response: choices[0].message.content
				var orchOut map[string]interface{}
				if err := json.Unmarshal(body, &orchOut); err == nil {
					// Log raw orchestrator response for easier tracing (non-sensitive)
					if bstr := strings.TrimSpace(string(body)); bstr != "" {
						// Avoid logging extremely large bodies
						if len(bstr) > 2000 {
							logging.Debugw("orchestrator: response (truncated)", "correlation_id", correlationID, "body_len", len(bstr))
						} else {
							logging.Debugw("orchestrator: response body", "correlation_id", correlationID, "body", bstr)
						}
					}
					if choices, ok := orchOut["choices"].([]interface{}); ok && len(choices) > 0 {
						if ch0, ok := choices[0].(map[string]interface{}); ok {
							if msg, ok := ch0["message"].(map[string]interface{}); ok {
								if content, ok := msg["content"].(string); ok && strings.TrimSpace(content) != "" {
									replyText := strings.TrimSpace(content)
									logging.Infow("orchestrator: reply received", "correlation_id", correlationID, "reply_len", len(replyText))
									logging.Debugw("orchestrator: reply text", "correlation_id", correlationID, "reply", replyText)

									// Persist orchestrator reply to sidecar JSON (best-effort)
									if p.saveAudioDir != "" && correlationID != "" {
										if path := p.findSidecarPathForCID(correlationID); path != "" {
											if sb, rerr := os.ReadFile(path); rerr == nil {
												var sc map[string]interface{}
												if uerr := json.Unmarshal(sb, &sc); uerr == nil {
													sc["orchestrator_reply"] = replyText
													sc["orchestrator_response_received_utc"] = time.Now().UTC().Format(time.RFC3339Nano)
													if procMs, ok := orchOut["processing_ms"].(float64); ok {
														sc["orchestrator_processing_ms"] = int(procMs)
													}
													nb, _ := json.MarshalIndent(sc, "", "  ")
													_ = os.WriteFile(path+".tmp", nb, 0o644)
													_ = os.Rename(path+".tmp", path)
													logging.Infow("orchestrator: saved reply to sidecar", "path", path, "correlation_id", correlationID)
												} else {
													logging.Debugw("orchestrator: failed to unmarshal sidecar JSON", "path", path, "err", uerr, "correlation_id", correlationID)
												}
											} else {
												logging.Debugw("orchestrator: failed to read sidecar for cid", "path", path, "err", rerr, "correlation_id", correlationID)
											}
										}
									}

									// If TTS_URL is configured, POST the reply text and save returned audio (with retries)
									if tts := os.Getenv("TTS_URL"); tts != "" {
										b2, _ := json.Marshal(map[string]string{"text": replyText})
										ttsTimeout := 10000
										if p.orchestratorTimeoutMS > 0 {
											ttsTimeout = p.orchestratorTimeoutMS
										}
										ttsAttempts := 2
										var resp2 *http.Response
										var terr error
										for ti := 0; ti < ttsAttempts; ti++ {
											ctx2, cancel2 := context.WithTimeout(context.Background(), time.Duration(ttsTimeout)*time.Millisecond)
											req2, rerr := http.NewRequestWithContext(ctx2, "POST", tts, bytes.NewReader(b2))
											if rerr != nil {
												logging.Debugw("tts: new request error", "err", rerr, "correlation_id", correlationID)
												cancel2()
												terr = rerr
												break
											}
											req2.Header.Set("Content-Type", "application/json")
											if tok := os.Getenv("TTS_AUTH_TOKEN"); tok != "" {
												req2.Header.Set("Authorization", "Bearer "+tok)
											} else if authToken != "" {
												req2.Header.Set("Authorization", "Bearer "+authToken)
											}
											client2 := &http.Client{Timeout: time.Duration(ttsTimeout) * time.Millisecond}
											resp2, terr = client2.Do(req2)
											cancel2()
											if terr != nil {
												logging.Debugw("tts: POST attempt failed", "attempt", ti+1, "err", terr, "correlation_id", correlationID)
												if ti < ttsAttempts-1 {
													time.Sleep(time.Duration(200*(1<<ti)) * time.Millisecond)
													continue
												}
												break
											}
											// got response; stop retrying
											break
										}
										if terr != nil {
											logging.Debugw("tts: POST failed", "err", terr, "correlation_id", correlationID)
										} else if resp2 != nil {
											defer resp2.Body.Close()
											if resp2.StatusCode >= 300 {
												_, _ = io.ReadAll(resp2.Body)
												logging.Warnw("tts: returned non-2xx", "status", resp2.StatusCode, "correlation_id", correlationID)
											} else {
												audioBytes, rerr := io.ReadAll(resp2.Body)
												if rerr != nil {
													logging.Debugw("tts: failed to read response body", "err", rerr, "correlation_id", correlationID)
												} else if p.saveAudioDir != "" {
													tsTs := time.Now().UTC().Format("20060102T150405.000Z")
													base := fmt.Sprintf("%s/%s_ssrc%d_tts", strings.TrimRight(p.saveAudioDir, "/"), tsTs, ssrc)
													fname := base + ".wav"
													tmp := fname + ".tmp"
													if err := os.WriteFile(tmp, audioBytes, 0o644); err != nil {
														logging.Debugw("tts: failed to write tmp file", "err", err, "path", tmp, "correlation_id", correlationID)
													} else if err := os.Rename(tmp, fname); err != nil {
														logging.Debugw("tts: failed to rename tmp file", "err", err, "tmp", tmp, "final", fname, "correlation_id", correlationID)
														_ = os.Remove(tmp)
													} else {
														logging.Infow("tts: saved audio to disk", "path", fname, "correlation_id", correlationID)
														// record tts path into sidecar JSON if possible
														if p.saveAudioDir != "" && correlationID != "" {
															if path := p.findSidecarPathForCID(correlationID); path != "" {
																if sb, rerr := os.ReadFile(path); rerr == nil {
																	var sc map[string]interface{}
																	if uerr := json.Unmarshal(sb, &sc); uerr == nil {
																		sc["tts_wav_path"] = fname
																		sc["tts_saved_utc"] = time.Now().UTC().Format(time.RFC3339Nano)
																		nb, _ := json.MarshalIndent(sc, "", "  ")
																		_ = os.WriteFile(path+".tmp", nb, 0o644)
																		_ = os.Rename(path+".tmp", path)
																		logging.Infow("tts: saved tts path to sidecar", "path", path, "correlation_id", correlationID)
																	} else {
																		logging.Debugw("tts: failed to unmarshal sidecar JSON", "path", path, "err", uerr, "correlation_id", correlationID)
																	}
																} else {
																	logging.Debugw("tts: failed to read sidecar for cid", "path", path, "err", rerr, "correlation_id", correlationID)
																}
															}
														}
													}
												}
											}
										}
									}
								}
							}
						}
					}
				}
			}(orch, os.Getenv("ORCH_AUTH_TOKEN"), uid, ssrc, strings.TrimSpace(text), corrID)
		}
	}
}

// buildWAV creates a simple RIFF/WAVE header for 16-bit PCM and returns the
// concatenated bytes (header + data). sampleRate in Hz, channels, bitsPerSample
// (commonly 16) are used to populate the header.
// buildWAV moved to whisper_client.go

// hasWakePhrase checks whether the provided text begins with one of the
// configured wake phrases (case-insensitive). If a wake phrase is found,
// it returns (true, strippedText) where strippedText is the text with the
// wake phrase and any immediate punctuation removed. Otherwise returns
// (false, "").
func (p *Processor) hasWakePhrase(text string) (bool, string) {
	if text == "" {
		return false, ""
	}
	s := strings.ToLower(strings.TrimSpace(text))
	// normalize whitespace
	s = regexp.MustCompile(`\s+`).ReplaceAllString(s, " ")
	// trim any leading punctuation
	s = strings.TrimLeft(s, " \t\n\r\f\v\"'`~")
	// If wakePhraseWindowS == 0, fallback to strict prefix semantics
	windowS := p.wakePhraseWindowS
	for _, wp := range p.wakePhrases {
		if wp == "" {
			continue
		}
		// exact match
		if s == wp {
			return true, ""
		}
		// If windowS == 0 use original prefix-based detection
		if windowS == 0 {
			prefixes := []string{wp + " ", wp + ",", wp + ".", wp + "!", wp + "?", wp + ":"}
			for _, pref := range prefixes {
				if strings.HasPrefix(s, pref) {
					stripped := strings.TrimLeft(strings.TrimSpace(s[len(pref):]), " ,.!?;:-\"'`~")
					return true, stripped
				}
			}
			continue
		}
		// Window-based heuristic: check whether the wake phrase appears within
		// the first K words of the transcript. K derived from windowS and a
		// heuristic speech rate (~3 words/sec). This avoids requiring strict
		// prefix matching while still limiting false positives.
		words := strings.Fields(s)
		k := windowS * 3
		if k < 3 {
			k = 3
		}
		if len(words) > k {
			words = words[:k]
		}
		// Split wake phrase into words to perform a word-boundary-aware search
		wpWords := strings.Fields(wp)
		if len(wpWords) == 0 {
			continue
		}
		// helper to normalize a token for comparison (strip surrounding punctuation)
		normalizeToken := func(tok string) string {
			return strings.Trim(strings.ToLower(strings.TrimSpace(tok)), " ,.!?;:-\"'`~")
		}
		// Search for the wake phrase sequence anywhere inside the head word slice
		for i := 0; i+len(wpWords) <= len(words); i++ {
			match := true
			for j := 0; j < len(wpWords); j++ {
				if normalizeToken(words[i+j]) != normalizeToken(wpWords[j]) {
					match = false
					break
				}
			}
			if match {
				// Build stripped text from the remainder of the entire normalized
				// transcript (not just the head) starting after the matched words.
				// Find the index of the first occurrence of this sequence in the
				// full words list to capture any words beyond the head.
				fullWords := strings.Fields(strings.TrimSpace(regexp.MustCompile(`\s+`).ReplaceAllString(s, " ")))
				// locate the matched sequence in fullWords
				foundIdx := -1
				for fi := 0; fi+len(wpWords) <= len(fullWords); fi++ {
					okMatch := true
					for fj := 0; fj < len(wpWords); fj++ {
						if normalizeToken(fullWords[fi+fj]) != normalizeToken(wpWords[fj]) {
							okMatch = false
							break
						}
					}
					if okMatch {
						foundIdx = fi
						break
					}
				}
				stripped := ""
				if foundIdx >= 0 && foundIdx+len(wpWords) <= len(fullWords) {
					if foundIdx+len(wpWords) < len(fullWords) {
						stripped = strings.Join(fullWords[foundIdx+len(wpWords):], " ")
						stripped = strings.Trim(stripped, " ,.!?;:-\"'`~")
					}
				}
				return true, stripped
			}
		}
	}
	return false, ""
}

// findSidecarPathForCID returns the full path to the sidecar JSON for a given
// correlation id. It first looks for an index file named `cid-<cid>.idx` in
// the saveAudioDir which contains the exact JSON path. If not found, it
// falls back to scanning the directory for a filename that contains
// 'cid<cid>' and ends with .json (legacy behavior).
func (p *Processor) findSidecarPathForCID(cid string) string {
	if p.saveAudioDir == "" || cid == "" {
		return ""
	}
	// Scan JSON files in saveAudioDir and try to find a sidecar whose
	// correlation_id matches. Fall back to filename substring match if
	// necessary. This avoids relying on a separate index file.
	files, _ := os.ReadDir(p.saveAudioDir)
	for _, fi := range files {
		name := fi.Name()
		if !strings.HasSuffix(name, ".json") {
			continue
		}
		path := p.saveAudioDir + "/" + name
		if b, err := os.ReadFile(path); err == nil {
			var sc map[string]interface{}
			if err := json.Unmarshal(b, &sc); err == nil {
				if v, ok := sc["correlation_id"].(string); ok && v == cid {
					return path
				}
			}
		}
	}
	// fallback: filename contains cid
	for _, fi := range files {
		name := fi.Name()
		if strings.Contains(name, "cid"+cid) && strings.HasSuffix(name, ".json") {
			return p.saveAudioDir + "/" + name
		}
	}
	return ""
}
