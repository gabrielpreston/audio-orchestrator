package voice

import (
	"context"
	"encoding/json"
	"net/http"
	"os"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/bwmarrin/discordgo"
	"github.com/discord-voice-lab/internal/logging"
	"github.com/hraban/opus"
)

// flushExpiredAggs iterates active transcript aggregations and emits
// any that have been idle longer than the aggregation window. It calls
// maybeForwardToOrchestrator to perform wake-phrase checks and forwarding.
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
	// larger chunk. Protected by accumMu.
	accumMu      sync.Mutex
	accums       map[uint32]*pcmAccum
	minFlushMs   int // minimum accumulated milliseconds before flush
	flushTimeout int // ms of inactivity before forcing a flush
	maxAccumMs   int // maximum accumulation duration per chunk
	// simple RMS-based VAD: if computed RMS < vadRmsThreshold we drop the chunk
	vadRmsThreshold int
	// monitoring counters
	enqueueCount   int64 // total frames enqueued
	dropQueueCount int64 // frames dropped due to full queue
	decodeErrCount int64 // opus decode errors
	vadDropCount   int64 // VAD drop count
	sendCount      int64 // successful sends to WHISPER_URL
	sendFailCount  int64 // failed sends

	// transcript aggregation: buffer successive transcripts per-SSRC and
	// emit a joined transcript when no new partial arrives within aggMs.
	aggMu sync.Mutex
	aggs  map[uint32]*transcriptAgg
	aggMs int // aggregation window in milliseconds
	// If true, flush immediately once minFlushMs is reached. When false,
	// only flush on maxAccumMs or inactivity timeout to avoid premature
	// chunking of long utterances.
	flushOnMin bool
	// silenceTimeoutMs controls how long (ms) of observed silence after the
	// last above-threshold RMS we'll wait before flushing an accumulator.
	// This allows us to dynamically extend buffering while speech continues.
	silenceTimeoutMs int
	// optional directory to save raw/wav audio for troubleshooting. If empty,
	// audio is not saved to disk.
	saveAudioDir string
	// wake phrases that must prefix a transcript to allow forwarding to orchestrator
	wakePhrases []string
	// wakePhraseWindowS controls how many seconds from the start of an
	// accumulation we consider the wake phrase to be valid (Option C).
	wakePhraseWindowS int
	// timeouts (ms) for external services, configurable via env
	whisperTimeoutMS      int
	orchestratorTimeoutMS int
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
		ssrcMap:    make(map[uint32]string),
		allowlist:  make(map[string]struct{}),
		dec:        dec,
		httpClient: nil,
		resolver:   resolver,
		ctx:        ctx,
		cancel:     cancel,
		opusCh:     make(chan opusPacket, 32),
		accums:     make(map[uint32]*pcmAccum),
		aggs:       make(map[uint32]*transcriptAgg),
		// read the container-local save path; fall back to legacy SAVE_AUDIO_DIR
		// but only enable saving when SAVE_AUDIO_ENABLED is set to "true"
		saveAudioDir: func() string {
			enabled := strings.ToLower(strings.TrimSpace(os.Getenv("SAVE_AUDIO_ENABLED")))
			if enabled != "true" {
				return ""
			}
			if v := strings.TrimSpace(os.Getenv("SAVE_AUDIO_DIR_CONTAINER")); v != "" {
				return v
			}
			return strings.TrimSpace(os.Getenv("SAVE_AUDIO_DIR"))
		}(),
		wakePhrases: func() []string {
			// default set of wake phrases
			def := []string{"computer", "hey computer", "hello computer", "ok computer", "hey comp"}
			if v := strings.TrimSpace(os.Getenv("WAKE_PHRASES")); v != "" {
				// split on comma and trim
				parts := strings.Split(v, ",")
				out := make([]string, 0, len(parts))
				for _, p := range parts {
					s := strings.ToLower(strings.TrimSpace(p))
					if s != "" {
						out = append(out, s)
					}

				}
				if len(out) > 0 {
					return out
				}
			}
			return def
		}(),
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

	// assign http client with whisper timeout
	p.httpClient = &http.Client{Timeout: time.Duration(p.whisperTimeoutMS) * time.Millisecond}

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
		go func(dir string, retention time.Duration, interval time.Duration, maxFiles int) {
			defer p.wg.Done()
			ticker := time.NewTicker(interval)
			defer ticker.Stop()
			for {
				select {
				case <-p.ctx.Done():
					return
				case <-ticker.C:
					// list files and remove sidecar pairs older than retention
					files, err := os.ReadDir(dir)
					if err != nil {
						// logging removed: Processor: cleanup readDir failed
						continue
					}
					// Collect sidecar JSON entries and associated WAVs, keyed by a base id
					type pairInfo struct {
						jsonPath string
						wavPath  string
						mod      time.Time
					}
					pairs := make(map[string]*pairInfo)
					for _, fi := range files {
						name := fi.Name()
						if !strings.HasSuffix(name, ".json") {
							continue
						}
						jsonPath := dir + "/" + name
						b, err := os.ReadFile(jsonPath)
						if err != nil {
							continue
						}
						var sc map[string]interface{}
						if err := json.Unmarshal(b, &sc); err != nil {
							continue
						}
						wavPath := ""
						if v, ok := sc["wav_path"].(string); ok && v != "" {
							wavPath = v
						} else {
							// derive wav path by replacing .json with .wav
							wavPath = strings.TrimSuffix(jsonPath, ".json") + ".wav"
						}
						st, err := os.Stat(jsonPath)
						if err != nil {
							continue
						}
						base := strings.TrimSuffix(name, ".json")
						pairs[base] = &pairInfo{jsonPath: jsonPath, wavPath: wavPath, mod: st.ModTime()}
					}
					// convert to slice and sort by modtime ascending
					var pairList []pairInfo
					for _, p := range pairs {
						pairList = append(pairList, *p)
					}
					sort.Slice(pairList, func(i, j int) bool { return pairList[i].mod.Before(pairList[j].mod) })
					// Remove pairs older than retention
					cutoff := time.Now().Add(-retention)
					removed := 0
					for _, pi := range pairList {
						if pi.mod.Before(cutoff) {
							// remove json and wav if present
							_ = os.Remove(pi.jsonPath)
							if pi.wavPath != "" {
								_ = os.Remove(pi.wavPath)
							}
							removed++
						}
					}
					if removed > 0 {
						// logging removed: Processor: cleanup removed old saved audio pairs
					}
					// If maxFiles > 0, enforce it in terms of pairs (oldest first)
					if maxFiles > 0 {
						filesLeft := len(pairList) - removed
						if filesLeft > maxFiles {
							toRemove := filesLeft - maxFiles
							count := 0
							for _, pi := range pairList {
								if count >= toRemove {
									break
								}
								// skip pairs that were already removed above
								if _, err := os.Stat(pi.jsonPath); err == nil {
									_ = os.Remove(pi.jsonPath)
								}
								if pi.wavPath != "" {
									if _, err := os.Stat(pi.wavPath); err == nil {
										_ = os.Remove(pi.wavPath)
									}
								}
								count++
							}
							if count > 0 {
								// logging removed: Processor: cleanup removed pairs to enforce max_files
							}
						}
					}
				}
			}
		}(p.saveAudioDir, time.Duration(retHours)*time.Hour, time.Duration(cleanIntervalMin)*time.Minute, maxFiles)
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

	// monitoring ticker: emit periodic stats so we can observe rates over time
	p.wg.Add(1)
	go func() {
		defer p.wg.Done()
		statsTicker := time.NewTicker(15 * time.Second)
		defer statsTicker.Stop()
		for {
			select {
			case <-p.ctx.Done():
				return
			case <-statsTicker.C:
				// stats collection disabled (logging removed)
			}
		}
	}()

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
	if data == nil || len(data) == 0 {
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
