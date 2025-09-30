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
	"sort"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/bwmarrin/discordgo"
	"github.com/google/uuid"
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
	text string
	last time.Time
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
		aggs:       make(map[uint32]*transcriptAgg),
		// read the container-local save path; fall back to legacy SAVE_AUDIO_DIR
		saveAudioDir: func() string {
			if v := strings.TrimSpace(os.Getenv("SAVE_AUDIO_DIR_CONTAINER")); v != "" {
				return v
			}
			return strings.TrimSpace(os.Getenv("SAVE_AUDIO_DIR"))
		}(),
	}

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
						logging.Sugar().Warnw("Processor: cleanup readDir failed", "dir", dir, "err", err)
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
						logging.Sugar().Infow("Processor: cleanup removed old saved audio pairs", "dir", dir, "removed_pairs", removed)
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
								logging.Sugar().Infow("Processor: cleanup removed pairs to enforce max_files", "dir", dir, "removed_pairs", count, "max_pairs", maxFiles)
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
				enq := atomic.LoadInt64(&p.enqueueCount)
				dq := atomic.LoadInt64(&p.dropQueueCount)
				dec := atomic.LoadInt64(&p.decodeErrCount)
				vad := atomic.LoadInt64(&p.vadDropCount)
				sOK := atomic.LoadInt64(&p.sendCount)
				sFail := atomic.LoadInt64(&p.sendFailCount)
				logging.Sugar().Infow("Processor stats",
					"enqueued_frames", enq,
					"dropped_queue", dq,
					"decode_errors", dec,
					"vad_drops", vad,
					"sends_ok", sOK,
					"sends_failed", sFail,
				)
			}
		}
	}()

	logging.Sugar().Info("Processor: initialized opus decoder and http client")

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
	// Backfill any existing accumulator's user info to avoid unknown user in sidecars
	p.accumMu.Lock()
	if a, ok := p.accums[uint32(su.SSRC)]; ok {
		a.userID = su.UserID
		if p.resolver != nil {
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

	// Determine a correlation ID to propagate with the packet so early logs
	// (enqueue time) can include it. Prefer any existing accumulator's ID;
	// otherwise generate one if we're configured to save audio.
	var outgoingCID string
	if p.saveAudioDir != "" {
		p.accumMu.Lock()
		if a, ok := p.accums[ssrc]; ok && a.correlationID != "" {
			outgoingCID = a.correlationID
		} else {
			// generate and stash a placeholder accumulator so the ID exists
			outgoingCID = uuid.NewString()
			if !ok {
				// capture known user mapping if present to avoid later lookup races
				uid := p.ssrcMap[ssrc]
				uname := "unknown"
				if uid != "" && p.resolver != nil {
					if n := p.resolver.UserName(uid); n != "" {
						uname = strings.ReplaceAll(n, " ", "_")
					}
				}
				p.accums[ssrc] = &pcmAccum{samples: nil, last: time.Now(), correlationID: outgoingCID, createdAt: time.Now(), userID: uid, username: uname}
			} else {
				p.accums[ssrc].correlationID = outgoingCID
			}
		}
		p.accumMu.Unlock()
	}

	// enqueue for background processing; drop if queue full to avoid blocking
	select {
	case p.opusCh <- opusPacket{ssrc: ssrc, data: append([]byte(nil), opusPayload...), correlationID: outgoingCID}:
		// increment enqueue counter and log enqueue for diagnostics
		atomic.AddInt64(&p.enqueueCount, 1)
		if outgoingCID != "" {
			logging.Sugar().Infow("Processor: opus frame enqueued", "ssrc", ssrc, "bytes", len(opusPayload), "queue_len", len(p.opusCh), "correlation_id", outgoingCID)
		} else {
			logging.Sugar().Infow("Processor: opus frame enqueued", "ssrc", ssrc, "bytes", len(opusPayload), "queue_len", len(p.opusCh))
		}
	default:
		atomic.AddInt64(&p.dropQueueCount, 1)
		logging.Sugar().Warnw("Processor: dropping opus frame; queue full", "ssrc", ssrc)
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
		logging.Sugar().Warnw("Processor: opus decode error", "err", err, "ssrc", ssrc, "payload_bytes", len(opusPayload))
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
		logging.Sugar().Infow("Processor: appended opus frame with correlation", "ssrc", ssrc, "correlation_id", cid, "payload_bytes", len(opusPayload))
	} else {
		logging.Sugar().Debugw("Processor: appended opus frame", "ssrc", ssrc, "payload_bytes", len(opusPayload))
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
		// speaking updates arrive after accumulator creation.
		uid := p.ssrcMap[ssrc]
		uname := "unknown"
		if uid != "" && p.resolver != nil {
			if n := p.resolver.UserName(uid); n != "" {
				uname = strings.ReplaceAll(n, " ", "_")
			}
		}
		a = &pcmAccum{samples: make([]int16, 0, len(samples)*4), last: time.Now(), createdAt: time.Now(), userID: uid, username: uname}
		// Prefer incomingCID if provided. Otherwise generate when we intend to
		// save audio (SAVE_AUDIO_DIR set).
		if incomingCID != "" {
			a.correlationID = incomingCID
		} else if p.saveAudioDir != "" {
			a.correlationID = uuid.NewString()
		}
		p.accums[ssrc] = a
	}
	// If accumulator exists but lacks an ID, populate it from incomingCID.
	if a.correlationID == "" && incomingCID != "" {
		a.correlationID = incomingCID
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
	// capture correlationID from accumulator (may be empty)
	corrID := a.correlationID
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
				logging.Sugar().Warnw("Processor: failed to create save audio dir", "dir", p.saveAudioDir, "err", err)
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
				logging.Sugar().Warnw("Processor: failed to write wav tmp file", "tmp", tmp, "err", err)
				return
			}
			if err := os.Rename(tmp, fname); err != nil {
				logging.Sugar().Warnw("Processor: failed to rename wav tmp", "tmp", tmp, "final", fname, "err", err)
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
			logging.Sugar().Infow("Processor: saved audio to disk", "path", fname, "ssrc", ssrc, "correlation_id", cid, "rms", rmsVal, "vad_dropped", vadDropped)
		}(ssrc, pcmBytes.Bytes(), cid, durationMs, rmsVal, vadDropped, createdAt, uid, uname)
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
				logging.Sugar().Infow("Processor: VAD dropped near-silence chunk", logging.AccumFields(ssrc, len(samples), (len(samples)*1000)/48000)...)
				logging.Sugar().Infow("Processor: VAD drop details", "ssrc", ssrc, "rms", rms, "threshold", p.vadRmsThreshold)
				return
			}
		}
	}

	if err := p.sendPCMToWhisper(ssrc, pcmBytes.Bytes(), cid); err != nil {
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

// sendPCMToWhisper wraps raw PCM16LE bytes into a WAV and POSTs to WHISPER_URL.
// It performs a small retry/backoff loop for transient failures.
func (p *Processor) sendPCMToWhisper(ssrc uint32, pcmBytes []byte, correlationID string) error {
	whisper := os.Getenv("WHISPER_URL")
	if whisper == "" {
		logging.Sugar().Warn("Processor: WHISPER_URL not set, dropping audio")
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
		if correlationID != "" {
			req.Header.Set("X-Correlation-ID", correlationID)
		}
		// record send timestamp
		sendTs := time.Now()
		logging.Sugar().Infow("Processor: sending audio",
			"whisper_url", whisper,
			"bytes", len(wav),
			"attempt", attempt+1,
			"send_ts", sendTs.UTC().Format(time.RFC3339Nano),
		)

		resp, err := p.httpClient.Do(req)
		cancel()
		if err != nil {
			atomic.AddInt64(&p.sendFailCount, 1)
			lastErr = err
			logging.Sugar().Warnw("Processor: HTTP send error", "err", err, "attempt", attempt+1, "whisper_url", whisper)
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
			logging.Sugar().Warnw("Processor: STT server error", "status", resp.StatusCode, "attempt", attempt+1)
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

		// compute end-to-end latency if accumulator creation time was saved in sidecar
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

		// Successful response - log transcript if present and return nil.
		atomic.AddInt64(&p.sendCount, 1)
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
					logging.Sugar().Warnw("Processor: text forward new request error", "err", err)
					return
				}
				req.Header.Set("Content-Type", "application/json")
				// Do not reuse processor httpClient to avoid interfering with timeouts
				c := &http.Client{Timeout: 5 * time.Second}
				resp, err := c.Do(req)
				if err != nil {
					logging.Sugar().Warnw("Processor: text forward POST failed", "err", err)
					return
				}
				defer resp.Body.Close()
				if resp.StatusCode >= 300 {
					logging.Sugar().Warnw("Processor: text forward returned non-2xx", "status", resp.StatusCode, "forward_url", forwardURL, "ssrc", ssrc)
				} else {
					logging.Sugar().Infow("Processor: forwarded transcript", "forward_url", forwardURL, "ssrc", ssrc, "correlation_id", cid)
				}
			}(fw, uid, ssrc, transcript, correlationID, sendTs, respReceivedTs, sttLatencyMs, sttServerMs, endToEndMs)
		}

		// Best-effort: update sidecar JSON with timing fields so offline analysis
		// can correlate times without hitting the server. This is tolerant to
		// missing files and performs no critical work on failure.
		if p.saveAudioDir != "" && correlationID != "" {
			if path := p.findSidecarPathForCID(correlationID); path != "" {
				b, err := os.ReadFile(path)
				if err == nil {
					var sc map[string]interface{}
					if err := json.Unmarshal(b, &sc); err == nil {
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
						// If the STT server returned timestamped segments (word timestamps),
						// copy them into the sidecar so offline analysis can access them.
						if segs, ok := out["segments"]; ok && segs != nil {
							// store as-is (may be []interface{} or other json-compatible type)
							sc["segments"] = segs
						}
						nb, _ := json.MarshalIndent(sc, "", "  ")
						_ = os.WriteFile(path+".tmp", nb, 0o644)
						_ = os.Rename(path+".tmp", path)
					}
				}
			}
		}
		// Use aggregation: add the transcript to the per-SSRC aggregator and
		// defer emitting until aggregation window passes.
		if transcript != "" {
			p.addAggregatedTranscript(ssrc, username, transcript)
		}
		return nil
	}
	return lastErr
}

// addAggregatedTranscript appends/inserts a transcript into the per-SSRC
// aggregation buffer and updates the timestamp. The flusher will emit
// combined transcripts after aggMs of inactivity.
func (p *Processor) addAggregatedTranscript(ssrc uint32, username, text string) {
	p.aggMu.Lock()
	defer p.aggMu.Unlock()
	a, ok := p.aggs[ssrc]
	if !ok {
		a = &transcriptAgg{text: text, last: time.Now()}
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
	fields := logging.UserFields(username, "")
	fields = append(fields, "ssrc", ssrc, "transcript", strings.TrimSpace(text))
	logging.Sugar().Infow("Processor: transcription result", fields...)
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
				logging.Sugar().Warnw("Processor: text forward new request error", "err", err)
				return
			}
			req.Header.Set("Content-Type", "application/json")
			c := &http.Client{Timeout: 5 * time.Second}
			resp, err := c.Do(req)
			if err != nil {
				logging.Sugar().Warnw("Processor: text forward POST failed", "err", err)
				return
			}
			defer resp.Body.Close()
			if resp.StatusCode >= 300 {
				logging.Sugar().Warnw("Processor: text forward returned non-2xx", "status", resp.StatusCode, "forward_url", forwardURL, "ssrc", ssrc)
			} else {
				logging.Sugar().Infow("Processor: forwarded transcript", "forward_url", forwardURL, "ssrc", ssrc)
			}
		}(fw, uid, ssrc, strings.TrimSpace(text))
	}

	// Forward aggregated transcript to an optional orchestrator service.
	// ORCHESTRATOR_URL: endpoint to receive conversation events (JSON POST).
	// ORCH_AUTH_TOKEN: optional bearer token to include in Authorization header.
	if orch := os.Getenv("ORCHESTRATOR_URL"); orch != "" {
		go func(orchestratorURL string, authToken string, uid string, ssrc uint32, text string) {
			payload := map[string]interface{}{
				"user_id":    uid,
				"ssrc":       ssrc,
				"transcript": text,
				"source":     "discord-voice-lab",
			}
			b, _ := json.Marshal(payload)
			ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
			defer cancel()
			req, err := http.NewRequestWithContext(ctx, "POST", orchestratorURL, bytes.NewReader(b))
			if err != nil {
				logging.Sugar().Warnw("Processor: orchestrator new request error", "err", err, "orchestrator_url", orchestratorURL)
				return
			}
			req.Header.Set("Content-Type", "application/json")
			if authToken != "" {
				req.Header.Set("Authorization", "Bearer "+authToken)
			}
			c := &http.Client{Timeout: 8 * time.Second}
			resp, err := c.Do(req)
			if err != nil {
				logging.Sugar().Warnw("Processor: orchestrator POST failed", "err", err, "orchestrator_url", orchestratorURL)
				return
			}
			defer resp.Body.Close()
			body, _ := io.ReadAll(resp.Body)
			if resp.StatusCode >= 300 {
				logging.Sugar().Warnw("Processor: orchestrator returned non-2xx", "status", resp.StatusCode, "orchestrator_url", orchestratorURL, "ssrc", ssrc, "body", string(body))
				return
			}
			logging.Sugar().Infow("Processor: forwarded transcript to orchestrator", "orchestrator_url", orchestratorURL, "ssrc", ssrc)

			// Try to parse JSON response and look for a 'reply' field (string)
			var orchOut map[string]interface{}
			if err := json.Unmarshal(body, &orchOut); err == nil {
				if r, ok := orchOut["reply"].(string); ok && strings.TrimSpace(r) != "" {
					replyText := strings.TrimSpace(r)
					logging.Sugar().Infow("Processor: orchestrator reply received", "ssrc", ssrc, "reply", replyText)
					// If TTS_URL is configured, POST the reply text and save returned audio
					if tts := os.Getenv("TTS_URL"); tts != "" {
						// Build payload for TTS service. Use {"text": "..."} as a common shape.
						b2, _ := json.Marshal(map[string]string{"text": replyText})
						req2, err := http.NewRequestWithContext(context.Background(), "POST", tts, bytes.NewReader(b2))
						if err != nil {
							logging.Sugar().Warnw("Processor: tts new request error", "err", err, "tts_url", tts)
							return
						}
						req2.Header.Set("Content-Type", "application/json")
						// Optional TTS auth via ORCH_AUTH_TOKEN or separate TTS_AUTH_TOKEN env var
						if tok := os.Getenv("TTS_AUTH_TOKEN"); tok != "" {
							req2.Header.Set("Authorization", "Bearer "+tok)
						} else if authToken != "" {
							req2.Header.Set("Authorization", "Bearer "+authToken)
						}
						c2 := &http.Client{Timeout: 10 * time.Second}
						resp2, err := c2.Do(req2)
						if err != nil {
							logging.Sugar().Warnw("Processor: tts POST failed", "err", err, "tts_url", tts)
							return
						}
						defer resp2.Body.Close()
						if resp2.StatusCode >= 300 {
							body2, _ := io.ReadAll(resp2.Body)
							logging.Sugar().Warnw("Processor: tts returned non-2xx", "status", resp2.StatusCode, "tts_url", tts, "body", string(body2))
							return
						}
						// Read audio bytes and save to disk if configured
						audioBytes, err := io.ReadAll(resp2.Body)
						if err != nil {
							logging.Sugar().Warnw("Processor: failed to read tts response body", "err", err)
							return
						}
						if p.saveAudioDir != "" {
							tsTs := time.Now().UTC().Format("20060102T150405.000Z")
							base := fmt.Sprintf("%s/%s_ssrc%d_tts", strings.TrimRight(p.saveAudioDir, "/"), tsTs, ssrc)
							fname := base + ".wav"
							tmp := fname + ".tmp"
							if err := os.WriteFile(tmp, audioBytes, 0o644); err != nil {
								logging.Sugar().Warnw("Processor: failed to write tts wav tmp file", "tmp", tmp, "err", err)
								return
							}
							if err := os.Rename(tmp, fname); err != nil {
								logging.Sugar().Warnw("Processor: failed to rename tts wav tmp", "tmp", tmp, "final", fname, "err", err)
								_ = os.Remove(tmp)
								return
							}
							logging.Sugar().Infow("Processor: saved TTS audio to disk", "path", fname, "ssrc", ssrc)
						}
					}
				}
			}
		}(orch, os.Getenv("ORCH_AUTH_TOKEN"), uid, ssrc, strings.TrimSpace(text))
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
