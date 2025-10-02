package voice

import (
	"context"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/bwmarrin/discordgo"
	"github.com/discord-voice-lab/internal/logging"
	"github.com/hraban/opus"
)

// flushExpiredAggs finds transcript aggregations idle past the window and
// emits them. Forwarding (wake-phrase checks + orchestrator calls) is
// delegated to maybeForwardToOrchestrator.
func (p *Processor) flushExpiredAggs() {
	now := time.Now()
	toEmit := make([]uint32, 0)
	p.aggMu.Lock()
	for ssrc, a := range p.aggs {
		if a == nil {
			continue
		}
		if now.Sub(a.last) >= time.Duration(p.aggMs)*time.Millisecond {
			toEmit = append(toEmit, ssrc)
		}
	}
	p.aggMu.Unlock()
	for _, s := range toEmit {
		p.aggMu.Lock()
		a, ok := p.aggs[s]
		if !ok || a == nil {
			p.aggMu.Unlock()
			continue
		}
		// capture and remove
		text := a.text
		corr := a.correlationID
		delete(p.aggs, s)
		p.aggMu.Unlock()

		if strings.TrimSpace(text) == "" {
			continue
		}
		// call helper to forward if needed
		p.maybeForwardToOrchestrator(s, a, text, corr)
	}
}

// Processor holds state and background workers for audio -> STT -> LLM
// orchestration.
type Processor struct {
	mu sync.Mutex
	// ssrc -> userID
	ssrcMap map[uint32]string
	// userID -> display name cache (seeded at join-time)
	userDisplay map[string]string
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
	// larger chunk (protected by accumMu).
	accumMu      sync.Mutex
	accums       map[uint32]*pcmAccum
	minFlushMs   int // minimum accumulated milliseconds before flush
	flushTimeout int // ms of inactivity before forcing a flush
	maxAccumMs   int // maximum accumulation duration per chunk
	// simple RMS-based VAD: drop chunks below vadRmsThreshold
	vadRmsThreshold int
	// monitoring counters
	decodeErrCount int64 // opus decode errors
	sendCount      int64 // successful sends to WHISPER_URL
	sendFailCount  int64 // failed sends

	// transcript aggregation: buffer successive transcripts per-SSRC and
	// emit a joined transcript after aggMs of inactivity.
	aggMu sync.Mutex
	aggs  map[uint32]*transcriptAgg
	aggMs int // aggregation window in milliseconds
	// If true, flush as soon as minFlushMs is reached; otherwise defer
	// to maxAccumMs or inactivity to avoid premature chunking.
	flushOnMin bool
	// silenceTimeoutMs: ms of observed silence after last above-threshold
	// RMS before flushing an accumulator.
	silenceTimeoutMs int
	// saveAudioDir: optional directory for raw/wav troubleshooting audio.
	// Empty disables saving.
	saveAudioDir string
	// manager for sidecar JSON files (created when saveAudioDir is set).
	sidecar *SidecarManager
	// wake phrases that must prefix a transcript to allow forwarding.
	wakePhrases  []string
	wakeDetector *WakeDetector
	// wakePhraseWindowS: seconds from accumulation start that a wake phrase
	// is considered valid.
	wakePhraseWindowS int
	// timeouts (ms) for external services (from env)
	whisperTimeoutMS      int
	orchestratorTimeoutMS int
	// TTS client (optional)
	tts *TTSClient
}

type opusPacket struct {
	ssrc uint32
	data []byte
	// optional correlation ID propagated from enqueue time so logs and
	// accumulators can be correlated from the earliest point in the
	// pipeline.
	correlationID string
}

// pcmAccum holds accumulated PCM samples for an SSRC and timestamp of last append
// types moved to types.go

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
		ssrcMap:      make(map[uint32]string),
		allowlist:    make(map[string]struct{}),
		dec:          dec,
		httpClient:   nil,
		resolver:     resolver,
		ctx:          ctx,
		cancel:       cancel,
		opusCh:       make(chan opusPacket, 32),
		accums:       make(map[uint32]*pcmAccum),
		aggs:         make(map[uint32]*transcriptAgg),
		saveAudioDir: getSaveAudioDir(),
		wakePhrases:  getWakePhrases(),
		wakeDetector: nil,
		sidecar:      NewSidecarManager(getSaveAudioDir()),
	}

	// Configure timeouts and wake phrase window from environment (ms/sec).
	// Defaults: 30s for whisper/orch, 3s window for wake phrase
	p.whisperTimeoutMS = 30000
	if v := os.Getenv("WHISPER_TIMEOUT_MS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			p.whisperTimeoutMS = n
		}
	}
	p.orchestratorTimeoutMS = 30000
	if v := os.Getenv("ORCH_TIMEOUT_MS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			p.orchestratorTimeoutMS = n
		}
	}
	p.wakePhraseWindowS = 3
	if v := os.Getenv("WAKE_PHRASE_WINDOW_S"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n >= 0 {
			p.wakePhraseWindowS = n
		}
	}

	// instantiate wake detector
	p.wakeDetector = NewWakeDetector(p.wakePhrases, p.wakePhraseWindowS)

	// assign http client with whisper timeout
	p.httpClient = &http.Client{Timeout: time.Duration(p.whisperTimeoutMS) * time.Millisecond}

	// optional TTS client
	p.tts = initTTSClient(p.sidecar, p.saveAudioDir, p.orchestratorTimeoutMS)

	// Retention settings for saved audio (optional)
	retHours := 72
	if v := os.Getenv("SAVE_AUDIO_RETENTION_HOURS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n >= 0 {
			retHours = n
		}
	}
	cleanIntervalMin := 10
	if v := os.Getenv("SAVE_AUDIO_CLEAN_INTERVAL_MIN"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			cleanIntervalMin = n
		}
	}
	maxFiles := 0
	if v := os.Getenv("SAVE_AUDIO_MAX_FILES"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n >= 0 {
			maxFiles = n
		}
	}

	// If saveAudioDir is set, start a background cleanup goroutine to prune old files
	if p.saveAudioDir != "" {
		p.wg.Add(1)
		StartSaveAudioCleaner(p.ctx, &p.wg, p.saveAudioDir, time.Duration(retHours)*time.Hour, time.Duration(cleanIntervalMin)*time.Minute, maxFiles)
	}

	// Configure accumulation thresholds from env or defaults
	p.minFlushMs = 800
	if v := os.Getenv("MIN_FLUSH_MS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			p.minFlushMs = n
		}
	}
	p.flushTimeout = 1200
	if v := os.Getenv("FLUSH_TIMEOUT_MS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			p.flushTimeout = n
		}
	}
	p.maxAccumMs = 12000
	if v := os.Getenv("MAX_ACCUM_MS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			p.maxAccumMs = n
		}
	}

	// RMS VAD threshold: if accumulated audio RMS is below this (int16 units)
	// we will drop the chunk instead of sending it to STT. Allows filtering
	// of low-energy noise. Default is 500 (adjustable via VAD_RMS_THRESHOLD).
	p.vadRmsThreshold = 110
	if v := os.Getenv("VAD_RMS_THRESHOLD"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n >= 0 {
			p.vadRmsThreshold = n
		}
	}

	// Whether to flush as soon as minFlushMs is reached. When false, we will
	// only flush when maxAccumMs is reached or when an inactivity timeout
	// elapses; this avoids aggressive chunking for long utterances.
	p.flushOnMin = false
	if v := os.Getenv("FLUSH_ON_MIN"); v != "" {
		lv := strings.ToLower(strings.TrimSpace(v))
		if lv == "1" || lv == "true" || lv == "yes" {
			p.flushOnMin = true
		}
	}
	p.silenceTimeoutMs = 600
	if v := os.Getenv("SILENCE_TIMEOUT_MS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n >= 0 {
			p.silenceTimeoutMs = n
		}
	}

	// start common background workers
	startBackgroundWorkers(p)

	// logging removed: Processor: initialized opus decoder and http client

	// transcript aggregation window (ms)
	p.aggMs = 1500
	if v := os.Getenv("TRANSCRIPT_AGG_MS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			p.aggMs = n
		}
	}

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

// touchStats references structure fields used for monitoring so static
// analysis does not report them as unused. It's a no-op at runtime.
// (removed touchStats helper; monitoring counters are used where needed)

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

// HandleVoiceState handles a Discord VoiceStateUpdate to keep the display
// name cache fresh. It's intentionally small: best-effort update from resolver
// or REST lookup when available.
func (p *Processor) HandleVoiceState(s *discordgo.Session, vs *discordgo.VoiceStateUpdate) {
	if vs == nil || vs.UserID == "" {
		return
	}
	uid := vs.UserID
	name := ""
	if p.resolver != nil {
		name = p.resolver.UserName(uid)
	}
	if name == "" && s != nil {
		if u, err := s.User(uid); err == nil && u != nil {
			name = u.Username
		}
	}
	if name == "" {
		name = uid
	}
	p.mu.Lock()
	if p.userDisplay == nil {
		p.userDisplay = make(map[string]string)
	}
	p.userDisplay[uid] = name
	p.mu.Unlock()
}

// HandleSpeakingUpdate is invoked for VoiceSpeakingUpdate events and maps
// SSRCs to user IDs so incoming opus frames can be correlated to users.
func (p *Processor) HandleSpeakingUpdate(s *discordgo.Session, su *discordgo.VoiceSpeakingUpdate) {
	if su == nil {
		return
	}
	if su.SSRC == 0 || su.UserID == "" {
		return
	}
	p.mu.Lock()
	p.ssrcMap[uint32(su.SSRC)] = su.UserID
	p.mu.Unlock()
}

// ProcessOpusFrame enqueues an incoming opus payload for background decoding.
// The send is non-blocking to avoid stalling the producer if the queue is full.
func (p *Processor) ProcessOpusFrame(ssrc uint32, data []byte) {
	if len(data) == 0 {
		return
	}
	pkt := opusPacket{ssrc: ssrc, data: append([]byte(nil), data...), correlationID: ""}
	select {
	case p.opusCh <- pkt:
	default:
		// drop if channel full
	}
}

// addAggregatedTranscript appends a partial transcript to the per-SSRC
// aggregation buffer and triggers any downstream forwarding (orchestrator)
// as a best-effort async call. This was factored out of the original large
// processor file so whisper_client.go can call it after STT returns.
func (p *Processor) addAggregatedTranscript(ssrc uint32, username, transcript, correlationID string, accumCreatedAt time.Time, strippedText string) {
	if transcript == "" {
		return
	}
	p.aggMu.Lock()
	a, ok := p.aggs[ssrc]
	if !ok {
		a = &transcriptAgg{
			text:          transcript,
			last:          time.Now(),
			correlationID: correlationID,
			wakeDetected:  strippedText != "",
			wakeStripped:  strippedText,
			createdAt:     accumCreatedAt,
		}
		p.aggs[ssrc] = a
	} else {
		if a.text == "" {
			a.text = transcript
		} else {
			a.text = strings.TrimSpace(a.text + " " + transcript)
		}
		a.last = time.Now()
		if !a.wakeDetected && strippedText != "" {
			a.wakeDetected = true
			a.wakeStripped = strippedText
		}
		if a.correlationID == "" && correlationID != "" {
			a.correlationID = correlationID
		}
	}
	p.aggMu.Unlock()

	// Best-effort: extracted orchestrator/TTS forwarding lives in orchestrator.go
	// call it to perform wake-phrase check and async forwarding when configured.
	p.maybeForwardToOrchestrator(ssrc, a, a.text, a.correlationID)
}
