package voice

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
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
	return NewProcessorWithResolver(nil)
}

// NewProcessorWithResolver creates a Processor and accepts an optional
// NameResolver which will be used to populate human-friendly names in logs.
func NewProcessorWithResolver(resolver NameResolver) (*Processor, error) {
	dec, err := opus.NewDecoder(48000, 2)
	if err != nil {
		return nil, err
	}
	ctx, cancel := context.WithCancel(context.Background())
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
	buf := &bytes.Buffer{}
	for i := 0; i < n; i++ {
		binary.Write(buf, binary.LittleEndian, pcm[i])
	}
	whisper := os.Getenv("WHISPER_URL")
	if whisper == "" {
		logging.Sugar().Warn("Processor: WHISPER_URL not set, dropping audio")
		return
	}

	// create a cancellable request tied to processor context
	reqCtx, cancel := context.WithTimeout(p.ctx, 15*time.Second)
	defer cancel()
	req, _ := http.NewRequestWithContext(reqCtx, "POST", whisper, bytes.NewReader(buf.Bytes()))
	req.Header.Set("Content-Type", "audio/pcm")
	logging.Sugar().Infof("Processor: sending audio to WHISPER_URL=%s bytes=%d", whisper, buf.Len())
	resp, err := p.httpClient.Do(req)
	if err != nil {
		logging.Sugar().Warnf("Processor: whisper post error: %v", err)
		return
	}
	defer resp.Body.Close()
	var out map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		logging.Sugar().Warnf("whisper decode: %v", err)
		return
	}
	p.mu.Lock()
	uid := p.ssrcMap[ssrc]
	p.mu.Unlock()
	username := uid
	if p.resolver != nil {
		// If the resolver can provide a nicer display name, prefer that.
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
	// If we know a username, include human-friendly fields; otherwise the ID-only fields will show.
	// username here is the user ID when we couldn't resolve a name in this scaffold.
	fields := logging.UserFields(username, "")
	fields = append(fields, "ssrc", ssrc, "transcript", transcript)
	logging.Sugar().Infow("Processor: transcription result", fields...)
}
