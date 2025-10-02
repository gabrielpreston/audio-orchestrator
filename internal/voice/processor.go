package voice

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"net/url"
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
type pcmAccum struct {
	samples []int16
	last    time.Time
	// correlationID is a per-accumulator UUID used to correlate saved WAVs,
	// STT requests and logs for a single accumulated chunk.
	correlationID string
	// lastAboveRms records the last time the accumulator saw a sample with
	// RMS above the VAD threshold. Used to enforce a silence period before
	// flushing to avoid chopping mid-utterance.
	lastAboveRms time.Time
	// createdAt marks when this accumulator was first created (used to
	// compute end-to-end time from accumulation start -> STT response).
	createdAt time.Time
	// user info captured from SSRC mapping when available. This avoids a
	// race where speaking updates arrive after accumulator creation.
	userID   string
	username string
}

// transcriptAgg holds an aggregated transcript for an SSRC and timestamp of last update
type transcriptAgg struct {
	text          string
	last          time.Time
	correlationID string
	// wakeDetected is true when any appended STT response contained the
	// wake phrase within the configured wake window. This allows the
	// flusher to forward the aggregated transcript even if the wake phrase
	// appeared after some initial non-wake words.
	wakeDetected bool
	// wakeStripped holds the transcript text with the wake phrase removed
	// (i.e., the user content after the wake phrase). This is populated
	// when a wake phrase is detected so the flusher can forward only the
	// intended user utterance.
	wakeStripped string
	createdAt    time.Time
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

// handleOpusPacket performs the actual decode and HTTP POST. It uses the
// processor context to cancel in-flight requests when Close is called.
func (p *Processor) handleOpusPacket(pkt opusPacket) {
	ssrc := pkt.ssrc
	opusPayload := pkt.data
	// Allocate a buffer large enough for a single frame. 20ms at 48kHz is
	// 960 samples per channel. Use a small multiple to be safe.
	pcm := make([]int16, 48000/50)
	n, err := p.dec.Decode(opusPayload, pcm)
	if err != nil {
		atomic.AddInt64(&p.decodeErrCount, 1)
		logging.Errorw("opus decode error", "ssrc", ssrc, "err", err)
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
	cid := p.appendAccum(ssrc, samples, pkt.correlationID)
	// Log the correlation id associated with this accumulated chunk so it's
	// visible early in the pipeline while frames are still arriving.
	if cid != "" {
		// logging removed: appended opus frame with correlation
	} else {
		// logging removed: appended opus frame
	}
}

// appendAccum adds decoded samples to the per-SSRC accumulator.
// appendAccum adds decoded samples to the per-SSRC accumulator and returns
// the accumulator's correlation ID (if any). The returned correlation ID is
// generated when a new accumulator is created and is used to correlate
// saved WAVs and STT requests/logs for that chunk.
// appendAccum adds decoded samples to the per-SSRC accumulator and returns
// the accumulator's correlation ID (if any). If an incomingCID is provided
// it will be preferred when creating or populating the accumulator.
func (p *Processor) appendAccum(ssrc uint32, samples []int16, incomingCID string) string {
	p.accumMu.Lock()
	defer p.accumMu.Unlock()
	a, ok := p.accums[ssrc]
	if !ok {
		// If we have a user mapping already, capture it to avoid races where
		// speaking updates arrive after accumulator creation. Read ssrcMap
		// under p.mu to avoid a data race (was observed as empty in logs).
		p.mu.Lock()
		uid := p.ssrcMap[ssrc]
		p.mu.Unlock()
		uname := "unknown"
		if uid != "" && p.resolver != nil {
			if n := p.resolver.UserName(uid); n != "" {
				uname = strings.ReplaceAll(n, " ", "_")
			}
		}
		a = &pcmAccum{samples: make([]int16, 0, len(samples)*4), last: time.Now(), createdAt: time.Now(), userID: uid, username: uname}
		// Prefer incomingCID if provided. Otherwise generate a correlation ID
		// unconditionally so downstream STT requests and logs always have a
		// value to correlate. If saving audio is enabled, emit an info log so
		// operators can find the sidecar more easily.
		if incomingCID != "" {
			a.correlationID = incomingCID
		} else {
			a.correlationID = uuid.NewString()
			if p.saveAudioDir != "" {
				// Log the generated correlation id so operator can find the sidecar later
				// logging removed: generated correlation id for accumulator on append
			}
		}
		p.accums[ssrc] = a
		// Log accumulator creation and captured user mapping (may be empty)
		logging.Debugw("appendAccum: created accumulator", "ssrc", ssrc, "user_id", uid, "user_name", uname, "correlation_id", a.correlationID)
	}
	// If accumulator exists but lacks an ID, populate it from incomingCID.
	if a.correlationID == "" {
		if incomingCID != "" {
			a.correlationID = incomingCID
		} else {
			// ensure every accumulator has an ID
			a.correlationID = uuid.NewString()
		}
		// Log correlation id assignment (if it was previously empty)
		logging.Debugw("appendAccum: assigned correlation id", "ssrc", ssrc, "correlation_id", a.correlationID, "user_id", a.userID)
	}
	a.samples = append(a.samples, samples...)
	a.last = time.Now()
	// Compute RMS for the newly appended samples to update lastAboveRms.
	if p.vadRmsThreshold > 0 && len(samples) > 0 {
		var sumSq int64
		for _, s := range samples {
			v := int64(s)
			sumSq += v * v
		}
		meanSq := sumSq / int64(len(samples))
		rms := int(math.Sqrt(float64(meanSq)))
		if rms >= p.vadRmsThreshold {
			a.lastAboveRms = time.Now()
		}
	}

	// Calculate duration in ms: samples / sampleRate * 1000 (sampleRate=48000)
	durMs := (len(a.samples) * 1000) / 48000
	// Flush when we reach the max accumulation limit, or when the min flush
	// threshold is reached and the FLUSH_ON_MIN policy is enabled.
	if durMs >= p.maxAccumMs || (durMs >= p.minFlushMs && p.flushOnMin) {
		// flush in a goroutine to avoid holding locks during HTTP
		go func(ssrc uint32) {
			p.flushAccum(ssrc)
		}(ssrc)
	}
	return a.correlationID
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
	// capture correlationID, createdAt and captured user info from accumulator (may be empty)
	corrID := a.correlationID
	createdAt := a.createdAt
	uid := a.userID
	uname := a.username
	delete(p.accums, ssrc)
	p.accumMu.Unlock()

	// Convert samples to bytes and send
	pcmBytes := &bytes.Buffer{}
	for _, s := range samples {
		binary.Write(pcmBytes, binary.LittleEndian, s)
	}
	// Compute RMS and duration (int16 samples)
	var sumSq int64
	for _, s := range samples {
		v := int64(s)
		sumSq += v * v
	}
	durationMs := 0
	if len(samples) > 0 {
		durationMs = (len(samples) * 1000) / 48000
	}
	rmsVal := 0
	if len(samples) > 0 {
		meanSq := sumSq / int64(len(samples))
		rmsVal = int(math.Sqrt(float64(meanSq)))
	}

	vadDropped := false
	if p.vadRmsThreshold > 0 && rmsVal < p.vadRmsThreshold {
		vadDropped = true
	}

	cid := corrID
	if cid == "" && p.saveAudioDir != "" {
		// If we didn't pre-generate a correlation ID on append, generate one
		// now because we're going to save the audio to disk.
		cid = uuid.NewString()
	}
	if p.saveAudioDir != "" {
		// capture accumulator createdAt and user info for end-to-end timing
		createdAt := a.createdAt
		uid := a.userID
		uname := a.username
		go func(ssrc uint32, pcm []byte, cid string, durationMs int, rmsVal int, vadDropped bool, createdAt time.Time, uid string, uname string) {
			// ensure dir exists
			if err := os.MkdirAll(p.saveAudioDir, 0o755); err != nil {
				logging.Errorw("failed to create save audio dir", "dir", p.saveAudioDir, "err", err)
				return
			}
			// prefer accumulator-captured user info to avoid races
			username := "unknown"
			if uid != "" {
				username = uid
				if uname != "" {
					username = uname
				} else if p.resolver != nil {
					if n := p.resolver.UserName(uid); n != "" {
						username = strings.ReplaceAll(n, " ", "_")
					}
				}
			}
			ts := time.Now().UTC().Format("20060102T150405.000Z")
			base := fmt.Sprintf("%s/%s_ssrc%d_%s_cid%s", strings.TrimRight(p.saveAudioDir, "/"), ts, ssrc, username, cid)
			fname := base + ".wav"
			wav := buildWAV(pcm, 48000, 1, 16)
			tmp := fname + ".tmp"
			if err := os.WriteFile(tmp, wav, 0o644); err != nil {
				logging.Errorw("failed to write wav tmp file", "tmp", tmp, "err", err)
				return
			}
			if err := os.Rename(tmp, fname); err != nil {
				logging.Errorw("failed to rename wav tmp", "tmp", tmp, "fname", fname, "err", err)
				_ = os.Remove(tmp)
				return
			}
			sidecar := map[string]interface{}{
				"correlation_id": cid,
				"ssrc":           ssrc,
				"user_id":        uid,
				"username":       username,
				// include the wav file path so consumers can locate the audio without a separate index
				"wav_path":      fname,
				"timestamp_utc": ts,
				"duration_ms":   durationMs,
				"rms":           rmsVal,
				"vad_dropped":   vadDropped,
				// placeholder timing fields filled after STT response
				"accum_created_utc": createdAt.UTC().Format(time.RFC3339Nano),
			}
			sidecarBytes, _ := json.MarshalIndent(sidecar, "", "  ")
			if err := os.WriteFile(base+".json.tmp", sidecarBytes, 0o644); err == nil {
				_ = os.Rename(base+".json.tmp", base+".json")
			}
			logging.Infow("saved audio to disk", "json", base+".json", "wav", fname, "ssrc", ssrc, "correlation_id", cid)
		}(ssrc, pcmBytes.Bytes(), cid, durationMs, rmsVal, vadDropped, createdAt, uid, uname)
	}
	// If accumulator didn't capture a user mapping, wait a short window for
	// a late speaking update to arrive (common when the bot joins after
	// participants are already speaking). This avoids sending "unknown"
	// transcripts when the mapping arrives milliseconds later.
	if uid == "" {
		waitUntil := time.Now().Add(500 * time.Millisecond)
		for time.Now().Before(waitUntil) {
			p.mu.Lock()
			possible := p.ssrcMap[ssrc]
			p.mu.Unlock()
			if possible != "" {
				uid = possible
				break
			}
			time.Sleep(25 * time.Millisecond)
		}
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
				atomic.AddInt64(&p.vadDropCount, 1)
				logging.Debugw("VAD dropped near-silence chunk", "ssrc", ssrc, "rms", rms)
				logging.Debugw("VAD drop details", "ssrc", ssrc, "samples", len(samples), "duration_ms", (len(samples)*1000)/48000)
				return
			}
		}
	}

	// If we still don't know which user this SSRC belongs to, drop the
	// chunk and log a warning. We intentionally do not send audio to STT
	// for anonymous SSRCs to avoid misattributing speech.
	if uid == "" {
		durationMs := 0
		if len(samples) > 0 {
			durationMs = (len(samples) * 1000) / 48000
		}
		atomic.AddInt64(&p.sendFailCount, 1)
		logging.Warnw("dropping audio chunk with unknown user; not sending to STT", "ssrc", ssrc, "correlation_id", cid, "duration_ms", durationMs)
		return
	}

	if err := p.sendPCMToWhisper(ssrc, pcmBytes.Bytes(), cid, createdAt, uid, uname); err != nil {
		// logging removed: send to whisper failed
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
		// Flush if we hit the hard max accumulation window.
		if durMs >= p.maxAccumMs {
			toFlush = append(toFlush, ssrc)
			continue
		}
		// If there's recent speech (lastAboveRms), wait for a silence period
		// before flushing. Otherwise, if inactivity exceeded flushTimeout,
		// flush as before.
		if !a.lastAboveRms.IsZero() {
			if now.Sub(a.lastAboveRms) >= time.Duration(p.silenceTimeoutMs)*time.Millisecond {
				toFlush = append(toFlush, ssrc)
			}
			continue
		}
		if now.Sub(a.last) >= time.Duration(p.flushTimeout)*time.Millisecond {
			toFlush = append(toFlush, ssrc)
		}
	}
	p.accumMu.Unlock()
	for _, s := range toFlush {
		p.flushAccum(s)
	}
}

// sendPCMToWhisper wraps raw PCM16LE into a WAV and POSTs it to WHISPER_URL.
// It retries up to 3 times with exponential backoff for transient errors.
func (p *Processor) sendPCMToWhisper(ssrc uint32, pcmBytes []byte, correlationID string, accumCreatedAt time.Time, capturedUserID string, capturedUsername string) error {
	whisper := os.Getenv("WHISPER_URL")
	if whisper == "" {
		logging.Warnw("WHISPER_URL not set, dropping audio", "ssrc", ssrc, "correlation_id", correlationID)
		return fmt.Errorf("WHISPER_URL not set")
	}

	// Build base whisper URL and optionally add query params to control
	// server-side transcription knobs. This keeps compatibility while
	// allowing runtime tuning via environment variables.
	whisperURL := whisper
	if u, err := url.Parse(whisper); err == nil {
		q := u.Query()
		// translation toggle
		if v := os.Getenv("WHISPER_TRANSLATE"); v != "" {
			lv := strings.ToLower(strings.TrimSpace(v))
			if lv == "1" || lv == "true" || lv == "yes" {
				q.Set("task", "translate")
			}
		}
		// optional beam size override for faster-whisper (int)
		if v := os.Getenv("STT_BEAM_SIZE"); v != "" {
			if _, err := strconv.Atoi(v); err == nil {
				q.Set("beam_size", v)
			}
		}
		// optional language override (e.g., "en", "es")
		if v := os.Getenv("STT_LANGUAGE"); v != "" {
			q.Set("language", v)
		}
		// optional word timestamps toggle for faster-whisper
		if v := os.Getenv("STT_WORD_TIMESTAMPS"); v != "" {
			lv := strings.ToLower(strings.TrimSpace(v))
			if lv == "1" || lv == "true" || lv == "yes" {
				q.Set("word_timestamps", "1")
			}
		}
		u.RawQuery = q.Encode()
		whisperURL = u.String()
	}

	// Build a mono WAV (48kHz, 16-bit) from decoded PCM so transcription
	// servers receive a standard audio container.
	wav := buildWAV(pcmBytes, 48000, 1, 16)

	// Attempt up to 3 tries with exponential backoff on transient errors.
	var lastErr error
	for attempt := 0; attempt < 3; attempt++ {
		// Use configured whisper timeout for per-request context
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
		// record send timestamp and log the send
		sendTs := time.Now()
		// Log detailed payload metadata: size, samples, duration and user mapping
		durationMs := 0
		if len(pcmBytes) > 0 {
			// pcmBytes length in bytes / 2 -> int16 samples
			samples := len(pcmBytes) / 2
			durationMs = (samples * 1000) / 48000
			// Prefer captured user info from the accumulator to avoid races
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
			// transient network error -> retry
			backoff := time.Duration(1<<attempt) * time.Second
			time.Sleep(backoff)
			continue
		}
		// record response receive timestamp
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

		// compute client-observed STT latency and attempt to extract server processing time
		sttLatencyMs := int(respReceivedTs.Sub(sendTs).Milliseconds())
		sttServerMs := 0
		// try header first
		if v := resp.Header.Get("X-Processing-Time-ms"); v != "" {
			if n, err := strconv.Atoi(v); err == nil {
				sttServerMs = n
			}
		}
		// fallback: JSON field
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

		// compute end-to-end latency if sidecar contains the accumulator created timestamp
		endToEndMs := 0
		if p.saveAudioDir != "" && correlationID != "" {
			if path := p.findSidecarPathForCID(correlationID); path != "" {
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

		// Successful response - log transcript and timing for tracing (username resolved below)
		// Successful response - log transcript if present and return nil.
		atomic.AddInt64(&p.sendCount, 1)
		// Prefer the accumulator-captured username when available to avoid
		// races where the SSRC->user mapping changed between accumulation and send.
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
		// Log STT response with resolved username and raw user id
		logging.Infow("STT response received", "ssrc", ssrc, "user", username, "user_id", uid, "correlation_id", correlationID, "status", resp.StatusCode, "stt_latency_ms", sttLatencyMs, "stt_server_ms", sttServerMs, "end_to_end_ms", endToEndMs)
		transcript := ""
		if t, ok := out["text"].(string); ok {
			// Trim whitespace the STT service may include (leading/trailing).
			transcript = strings.TrimSpace(t)
		}
		// Log STT result and timing for tracing
		// logging removed: STT response received
		// Optionally forward recognized text to another service for downstream
		// integrations. This is a best-effort POST; failures are logged but do
		// not affect the main transcription success path.
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
					// logging removed: text forward new request error
					return
				}
				req.Header.Set("Content-Type", "application/json")
				// Do not reuse processor httpClient to avoid interfering with timeouts
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
			}(fw, uid, ssrc, transcript, correlationID, sendTs, respReceivedTs, sttLatencyMs, sttServerMs, endToEndMs)
		}

		// Best-effort: update sidecar JSON with timing fields for offline analysis.
		if p.saveAudioDir != "" && correlationID != "" {
			if path := p.findSidecarPathForCID(correlationID); path != "" {
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
						// optionally include transcript for convenience
						if transcript != "" {
							sc["transcript"] = transcript
						}
						// If the STT server returned timestamped segments, copy them
						// into the sidecar for debugging (may be nil in production).
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
		// Add transcript to the per-SSRC aggregator. We run wake-phrase detection
		// on the root `transcript` field and pass any stripped text along so the
		// aggregator/flusher can forward only the post-wake content.
		_, strippedText := p.hasWakePhrase(transcript)
		if transcript != "" {
			p.addAggregatedTranscript(ssrc, username, transcript, correlationID, accumCreatedAt, strippedText)
		}
		return nil
	}
	return lastErr
}

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
