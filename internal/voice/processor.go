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
	"strings"
	"sync"
	"time"

	"github.com/bwmarrin/discordgo"
	"github.com/hraban/opus"

	"github.com/discord-voice-lab/internal/logging"
)

type Processor struct {
	mu sync.Mutex
	// ssrc -> userID
	ssrcMap map[uint32]string
	// optional set of allowed user IDs; when non-empty, frames from mapped
	// users not in this set will be dropped early.
	allowlist map[string]struct{}
	// opus decoder (one per stream)
	dec        *opus.Decoder
	httpClient *http.Client
	// optional resolver for human-friendly names
	resolver NameResolver
	// background processing
	ctx    context.Context
	cancel context.CancelFunc
	wg     sync.WaitGroup
	opusCh chan opusPacket
}

type opusPacket struct {
	ssrc uint32
	data []byte
}

func NewProcessor() (*Processor, error) {
	return NewProcessorWithResolver(context.Background(), nil)
}

// NewProcessorWithResolver creates a Processor and accepts an optional
// parent context and NameResolver which will be used to populate human-friendly names in logs.
// If parent is nil the background context is used. The returned Processor's
// internal context is a child of the provided parent so callers can cancel
// the parent to request shutdown of processor workers.
func NewProcessorWithResolver(parent context.Context, resolver NameResolver) (*Processor, error) {
	if parent == nil {
		parent = context.Background()
	}
	dec, err := opus.NewDecoder(48000, 2)
	if err != nil {
		return nil, err
	}
	ctx, cancel := context.WithCancel(parent)
	p := &Processor{
		ssrcMap:    make(map[uint32]string),
		allowlist:  make(map[string]struct{}),
		dec:        dec,
		httpClient: &http.Client{Timeout: 15 * time.Second},
		resolver:   resolver,
		ctx:        ctx,
		cancel:     cancel,
		opusCh:     make(chan opusPacket, 32),
	}

	// start background worker to process opus frames
	p.wg.Add(1)
	go func() {
		defer p.wg.Done()
		for {
			select {
			case <-p.ctx.Done():
				return
			case pkt, ok := <-p.opusCh:
				if !ok {
					return
				}
				p.handleOpusPacket(pkt)
			}
		}
	}()

	logging.Sugar().Info("Processor: initialized opus decoder and http client")
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
	logging.Sugar().Infow("Processor: SetAllowedUsers", "count", len(p.allowlist))
}

func (p *Processor) Close() error {
	logging.Sugar().Info("Processor: Close called")
	// stop background workers
	p.cancel()
	// close channel to unblock worker if it's waiting
	close(p.opusCh)
	p.wg.Wait()
	return nil
}

// HandleVoiceState listens for voice state updates to map userID <-> SSRC (best-effort)
func (p *Processor) HandleVoiceState(s *discordgo.Session, vs *discordgo.VoiceStateUpdate) {
	// Include human-friendly fields when available; try resolver first.
	var userName, channelName string
	if p.resolver != nil {
		userName = p.resolver.UserName(vs.UserID)
		channelName = p.resolver.ChannelName(fmt.Sprintf("%v", vs.ChannelID))
	}
	fields := append(logging.UserFields(vs.UserID, userName), logging.ChannelFields(fmt.Sprintf("%v", vs.ChannelID), channelName)...)
	fields = append(fields, "session_update", vs)
	logging.Sugar().Infow("Processor: HandleVoiceState", fields...)
}

// HandleSpeakingUpdate receives discordgo speaking updates and is used to map ssrc->user
func (p *Processor) HandleSpeakingUpdate(s *discordgo.Session, su *discordgo.VoiceSpeakingUpdate) {
	// map SSRC to user
	p.mu.Lock()
	defer p.mu.Unlock()
	p.ssrcMap[uint32(su.SSRC)] = su.UserID
	var userName string
	if p.resolver != nil {
		userName = p.resolver.UserName(su.UserID)
	}
	fields := []interface{}{"ssrc", su.SSRC}
	fields = append(fields, logging.UserFields(su.UserID, userName)...)
	logging.Sugar().Infow("Processor: HandleSpeakingUpdate: mapped SSRC -> user", fields...)
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
		logging.Sugar().Debugw("Processor: dropping frame from non-allowed user", "ssrc", ssrc, "user_id", uid)
		return
	}

	// enqueue for background processing; drop if queue full to avoid blocking
	select {
	case p.opusCh <- opusPacket{ssrc: ssrc, data: append([]byte(nil), opusPayload...)}:
		// Log enqueue for diagnostics. We use len(opusCh) to approximate queue depth.
		logging.Sugar().Infow("Processor: opus frame enqueued", "ssrc", ssrc, "bytes", len(opusPayload), "queue_len", len(p.opusCh))
	default:
		logging.Sugar().Warnf("Processor: dropping opus frame ssrc=%d; queue full", ssrc)
	}
}

// handleOpusPacket performs the actual decode and HTTP POST. It uses the
// processor context to cancel in-flight requests when Close is called.
func (p *Processor) handleOpusPacket(pkt opusPacket) {
	ssrc := pkt.ssrc
	opusPayload := pkt.data
	logging.Sugar().Infow("Processor: handling opus packet", "ssrc", ssrc, "payload_bytes", len(opusPayload))
	pcm := make([]int16, 48000*2/50)
	n, err := p.dec.Decode(opusPayload, pcm)
	if err != nil {
		logging.Sugar().Warnf("Processor: opus decode error: %v", err)
		return
	}
	// assemble raw PCM bytes (little-endian int16)
	pcmBytes := &bytes.Buffer{}
	for i := 0; i < n; i++ {
		binary.Write(pcmBytes, binary.LittleEndian, pcm[i])
	}

	// Send the assembled PCM to the configured WHISPER_URL. The helper will
	// wrap bytes into a WAV container and perform retries/backoff. The helper
	// handles logging of the transcription result.
	if err := p.sendPCMToWhisper(ssrc, pcmBytes.Bytes()); err != nil {
		logging.Sugar().Warnf("Processor: send to whisper failed: %v", err)
		return
	}
}

// sendPCMToWhisper wraps raw PCM16LE bytes into a WAV and POSTs to WHISPER_URL.
// It performs a small retry/backoff loop for transient failures.
func (p *Processor) sendPCMToWhisper(ssrc uint32, pcmBytes []byte) error {
	whisper := os.Getenv("WHISPER_URL")
	if whisper == "" {
		logging.Sugar().Warn("Processor: WHISPER_URL not set, dropping audio")
		return fmt.Errorf("WHISPER_URL not set")
	}

	// If configured, request translation by adding a query param. This keeps
	// compatibility with simple STT endpoints while allowing the STT service
	// to perform translate tasks when supported (e.g., faster-whisper task=translate).
	whisperURL := whisper
	if v := os.Getenv("WHISPER_TRANSLATE"); v != "" {
		lv := strings.ToLower(strings.TrimSpace(v))
		if lv == "1" || lv == "true" || lv == "yes" {
			if u, err := url.Parse(whisper); err == nil {
				q := u.Query()
				q.Set("task", "translate")
				u.RawQuery = q.Encode()
				whisperURL = u.String()
			}
		}
	}

	// Build WAV bytes (48kHz, 2 channels, 16-bit samples) to be broadly compatible
	// with common transcription servers and tools.
	wav := buildWAV(pcmBytes, 48000, 2, 16)

	// Attempt up to 3 tries with exponential backoff on transient errors.
	var lastErr error
	for attempt := 0; attempt < 3; attempt++ {
		reqCtx, cancel := context.WithTimeout(p.ctx, 15*time.Second)
		req, err := http.NewRequestWithContext(reqCtx, "POST", whisperURL, bytes.NewReader(wav))
		if err != nil {
			cancel()
			lastErr = err
			break
		}
		req.Header.Set("Content-Type", "audio/wav")
		logging.Sugar().Infof("Processor: sending audio to WHISPER_URL=%s bytes=%d (attempt=%d)", whisper, len(wav), attempt+1)

		resp, err := p.httpClient.Do(req)
		cancel()
		if err != nil {
			lastErr = err
			// transient network error -> retry
			backoff := time.Duration(1<<attempt) * time.Second
			time.Sleep(backoff)
			continue
		}
		defer resp.Body.Close()

		if resp.StatusCode >= 500 {
			lastErr = fmt.Errorf("server error status=%d", resp.StatusCode)
			backoff := time.Duration(1<<attempt) * time.Second
			time.Sleep(backoff)
			continue
		}

		var out map[string]interface{}
		if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
			lastErr = err
			return err
		}

		// Successful response - log transcript if present and return nil.
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
		transcript := ""
		if t, ok := out["text"].(string); ok {
			transcript = t
		}
		// Optionally forward recognized text to another service for downstream
		// integrations. This is a best-effort POST; failures are logged but do
		// not affect the main transcription success path.
		if fw := os.Getenv("TEXT_FORWARD_URL"); fw != "" && transcript != "" {
			go func(forwardURL string, uid string, ssrc uint32, text string) {
				payload := map[string]interface{}{
					"user_id":    uid,
					"ssrc":       ssrc,
					"transcript": text,
				}
				b, _ := json.Marshal(payload)
				req, err := http.NewRequestWithContext(context.Background(), "POST", forwardURL, bytes.NewReader(b))
				if err != nil {
					logging.Sugar().Warnf("Processor: text forward new request error: %v", err)
					return
				}
				req.Header.Set("Content-Type", "application/json")
				// Do not reuse processor httpClient to avoid interfering with timeouts
				c := &http.Client{Timeout: 5 * time.Second}
				resp, err := c.Do(req)
				if err != nil {
					logging.Sugar().Warnf("Processor: text forward POST failed: %v", err)
					return
				}
				defer resp.Body.Close()
				if resp.StatusCode >= 300 {
					logging.Sugar().Warnf("Processor: text forward returned status=%d", resp.StatusCode)
				} else {
					logging.Sugar().Infow("Processor: forwarded transcript", "forward_url", forwardURL, "ssrc", ssrc)
				}
			}(fw, uid, ssrc, transcript)
		}
		fields := logging.UserFields(username, "")
		fields = append(fields, "ssrc", ssrc, "transcript", transcript)
		logging.Sugar().Infow("Processor: transcription result", fields...)
		return nil
	}
	return lastErr
}

// buildWAV creates a simple RIFF/WAVE header for 16-bit PCM and returns the
// concatenated bytes (header + data). sampleRate in Hz, channels, bitsPerSample
// (commonly 16) are used to populate the header.
func buildWAV(pcm []byte, sampleRate, channels, bitsPerSample int) []byte {
	byteRate := uint32(sampleRate * channels * bitsPerSample / 8)
	blockAlign := uint16(channels * bitsPerSample / 8)
	dataLen := uint32(len(pcm))
	// RIFF chunk size = 4 ("WAVE") + (8+fmtLen) + (8+dataLen) where fmtLen=16
	riffSize := uint32(4 + (8 + 16) + (8 + dataLen))

	buf := &bytes.Buffer{}
	// RIFF header
	buf.WriteString("RIFF")
	binary.Write(buf, binary.LittleEndian, riffSize)
	buf.WriteString("WAVE")
	// fmt chunk
	buf.WriteString("fmt ")
	binary.Write(buf, binary.LittleEndian, uint32(16))            // Subchunk1Size for PCM
	binary.Write(buf, binary.LittleEndian, uint16(1))             // AudioFormat = 1 (PCM)
	binary.Write(buf, binary.LittleEndian, uint16(channels))      // NumChannels
	binary.Write(buf, binary.LittleEndian, uint32(sampleRate))    // SampleRate
	binary.Write(buf, binary.LittleEndian, uint32(byteRate))      // ByteRate
	binary.Write(buf, binary.LittleEndian, blockAlign)            // BlockAlign
	binary.Write(buf, binary.LittleEndian, uint16(bitsPerSample)) // BitsPerSample
	// data chunk
	buf.WriteString("data")
	binary.Write(buf, binary.LittleEndian, uint32(dataLen))
	buf.Write(pcm)
	return buf.Bytes()
}
