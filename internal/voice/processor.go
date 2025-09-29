package voice

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
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
	// opus decoder (one per stream)
	dec        *opus.Decoder
	httpClient *http.Client
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
	dec, err := opus.NewDecoder(48000, 2)
	if err != nil {
		return nil, err
	}
	ctx, cancel := context.WithCancel(context.Background())
	p := &Processor{
		ssrcMap:    make(map[uint32]string),
		dec:        dec,
		httpClient: &http.Client{Timeout: 15 * time.Second},
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
	logging.Sugar().Infof("Processor: HandleVoiceState: user=%s channel=%v session_update=%+v", vs.UserID, vs.ChannelID, vs)
}

// HandleSpeakingUpdate receives discordgo speaking updates and is used to map ssrc->user
func (p *Processor) HandleSpeakingUpdate(s *discordgo.Session, su *discordgo.VoiceSpeakingUpdate) {
	// map SSRC to user
	p.mu.Lock()
	defer p.mu.Unlock()
	p.ssrcMap[uint32(su.SSRC)] = su.UserID
	logging.Sugar().Infof("Processor: HandleSpeakingUpdate: mapped SSRC=%d -> user=%s", su.SSRC, su.UserID)
}

// This function would be called by the discord voice receive loop with raw opus frames.
// For simplicity in this scaffold, we'll expose a method to accept encoded opus frames and process them.
func (p *Processor) ProcessOpusFrame(ssrc uint32, opusPayload []byte) {
	// enqueue for background processing; drop if queue full to avoid blocking
	select {
	case p.opusCh <- opusPacket{ssrc: ssrc, data: append([]byte(nil), opusPayload...)}:
	default:
		logging.Sugar().Warnf("Processor: dropping opus frame ssrc=%d; queue full", ssrc)
	}
}

// handleOpusPacket performs the actual decode and HTTP POST. It uses the
// processor context to cancel in-flight requests when Close is called.
func (p *Processor) handleOpusPacket(pkt opusPacket) {
	ssrc := pkt.ssrc
	opusPayload := pkt.data
	logging.Sugar().Infof("Processor: handling opus packet: ssrc=%d payload_bytes=%d", ssrc, len(opusPayload))
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
	if username == "" {
		username = "unknown"
	}
	transcript := ""
	if t, ok := out["text"].(string); ok {
		transcript = t
	}
	logging.Sugar().Infof("Processor: transcription result user=%s ssrc=%d transcript=%s", username, ssrc, transcript)
}
