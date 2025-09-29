package voice

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"math"
	"net/http"
	"net/url"
	"os"
	"strconv"
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

	// accumulation state: per-SSRC decoded PCM waiting to be sent as a
	// larger chunk. Protected by accumMu.
	accumMu      sync.Mutex
	accums       map[uint32]*pcmAccum
	minFlushMs   int // minimum accumulated milliseconds before flush
	flushTimeout int // ms of inactivity before forcing a flush
	maxAccumMs   int // maximum accumulation duration per chunk
	// simple RMS-based VAD: if computed RMS < vadRmsThreshold we drop the chunk
	vadRmsThreshold int
}

type opusPacket struct {
	ssrc uint32
	data []byte
}

// pcmAccum holds accumulated PCM samples for an SSRC and timestamp of last append
type pcmAccum struct {
	samples []int16
	last    time.Time
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
	// Use mono (1 channel) decoder: Discord voice uses 48kHz but audio
	// frames are typically mono. Using 2 channels caused mis-interleaving
	// and corrupted audio when we wrote a stereo WAV later.
	dec, err := opus.NewDecoder(48000, 1)
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
		accums:     make(map[uint32]*pcmAccum),
	}

	// Configure accumulation thresholds from env or defaults
	p.minFlushMs = 300
	if v := os.Getenv("MIN_FLUSH_MS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			p.minFlushMs = n
		}
	}
	p.flushTimeout = 200
	if v := os.Getenv("FLUSH_TIMEOUT_MS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			p.flushTimeout = n
		}
	}
	p.maxAccumMs = 5000
	if v := os.Getenv("MAX_ACCUM_MS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			p.maxAccumMs = n
		}
	}

	// RMS VAD threshold: if accumulated audio RMS is below this (int16 units)
	// we will drop the chunk instead of sending it to STT. Allows filtering
	// of low-energy noise. Default is 500 (adjustable via VAD_RMS_THRESHOLD).
	p.vadRmsThreshold = 500
	if v := os.Getenv("VAD_RMS_THRESHOLD"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n >= 0 {
			p.vadRmsThreshold = n
		}
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

	// start background flusher which periodically checks for inactive
	// accumulators and flushes them
	p.wg.Add(1)
	go func() {
		defer p.wg.Done()
		ticker := time.NewTicker(100 * time.Millisecond)
		defer ticker.Stop()
		for {
			select {
			case <-p.ctx.Done():
				return
			case <-ticker.C:
				p.flushExpiredAccums()
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
	// Allocate a buffer large enough for a single frame. 20ms at 48kHz is
	// 960 samples per channel. Use a small multiple to be safe.
	pcm := make([]int16, 48000/50)
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

	// Append decoded samples to the accumulator for this SSRC. We'll flush
	// when the accumulator reaches a minimum duration or when it times out.
	samples := make([]int16, n)
	copy(samples, pcm[:n])
	p.appendAccum(ssrc, samples)
}

// appendAccum adds decoded samples to the per-SSRC accumulator.
func (p *Processor) appendAccum(ssrc uint32, samples []int16) {
	p.accumMu.Lock()
	defer p.accumMu.Unlock()
	a, ok := p.accums[ssrc]
	if !ok {
		a = &pcmAccum{samples: make([]int16, 0, len(samples)*4), last: time.Now()}
		p.accums[ssrc] = a
	}
	a.samples = append(a.samples, samples...)
	a.last = time.Now()

	// If we've reached the minFlushMs threshold, flush immediately (async)
	// Calculate duration in ms: samples / sampleRate * 1000 (sampleRate=48000)
	durMs := (len(a.samples) * 1000) / 48000
	if durMs >= p.minFlushMs || durMs*2 >= p.maxAccumMs {
		// flush in a goroutine to avoid holding locks during HTTP
		go func(ssrc uint32) {
			p.flushAccum(ssrc)
		}(ssrc)
	}
}

// flushAccum flushes an accumulator by sending its PCM to the STT service.
// It removes the accumulator entry.
func (p *Processor) flushAccum(ssrc uint32) {
	p.accumMu.Lock()
	a, ok := p.accums[ssrc]
	if !ok || len(a.samples) == 0 {
		p.accumMu.Unlock()
		return
	}
	samples := a.samples
	delete(p.accums, ssrc)
	p.accumMu.Unlock()

	// Convert samples to bytes and send
	pcmBytes := &bytes.Buffer{}
	for _, s := range samples {
		binary.Write(pcmBytes, binary.LittleEndian, s)
	}
	// Compute RMS and apply simple VAD: if RMS is below threshold, drop
	// the chunk. RMS computed in int32 space to avoid overflow.
	if p.vadRmsThreshold > 0 {
		var sumSq int64
		for _, s := range samples {
			v := int64(s)
			sumSq += v * v
		}
		if len(samples) > 0 {
			meanSq := sumSq / int64(len(samples))
			rms := int(math.Sqrt(float64(meanSq)))
			if rms < p.vadRmsThreshold {
				logging.Sugar().Infow("Processor: VAD dropped near-silence chunk", "ssrc", ssrc, "rms", rms, "threshold", p.vadRmsThreshold)
				return
			}
		}
	}

	if err := p.sendPCMToWhisper(ssrc, pcmBytes.Bytes()); err != nil {
		logging.Sugar().Warnf("Processor: send to whisper failed: %v", err)
		return
	}
}

// flushExpiredAccums checks accumulators and flushes ones that have been
// inactive longer than flushTimeout or exceed maxAccumMs.
func (p *Processor) flushExpiredAccums() {
	now := time.Now()
	var toFlush []uint32
	p.accumMu.Lock()
	for ssrc, a := range p.accums {
		durMs := (len(a.samples) * 1000) / 48000
		if durMs >= p.maxAccumMs || now.Sub(a.last) >= time.Duration(p.flushTimeout)*time.Millisecond {
			toFlush = append(toFlush, ssrc)
		}
	}
	p.accumMu.Unlock()
	for _, s := range toFlush {
		p.flushAccum(s)
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
	// Build WAV bytes (48kHz, 1 channel, 16-bit samples). We decode as
	// mono and therefore produce a mono WAV to avoid channel mismatch.
	wav := buildWAV(pcmBytes, 48000, 1, 16)

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
			// Trim whitespace the STT service may include (leading/trailing).
			transcript = strings.TrimSpace(t)
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
