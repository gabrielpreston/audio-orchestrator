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
}

func NewProcessor() (*Processor, error) {
	dec, err := opus.NewDecoder(48000, 2)
	if err != nil {
		return nil, err
	}
	p := &Processor{ssrcMap: make(map[uint32]string), dec: dec, httpClient: &http.Client{Timeout: 15 * time.Second}}
	logging.Sugar().Info("Processor: initialized opus decoder and http client")
	return p, nil
}

func (p *Processor) Close() error {
	logging.Sugar().Info("Processor: Close called")
	// nothing to close yet; if we add goroutines, cancel them here
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
	// decode opusPayload (assuming it's an encoded frame) into PCM16
	logging.Sugar().Infof("Processor: ProcessOpusFrame: ssrc=%d payload_bytes=%d", ssrc, len(opusPayload))
	pcm := make([]int16, 48000*2/50) // allocate for 20ms at 48k, stereo
	n, err := p.dec.Decode(opusPayload, pcm)
	if err != nil {
		logging.Sugar().Warnf("Processor: opus decode error: %v", err)
		return
	}
	// convert pcm (int16) into WAV bytes (16kHz mono is typical for STT, but we'll send 48k stereo)
	buf := &bytes.Buffer{}
	// write a simple WAV header + pcm little endian
	// RIFF header
	// For brevity: use raw PCM POST body and rely on WHISPER_URL accepting raw PCM16LE 48k stereo
	// create body
	// pack ints
	for i := 0; i < n; i++ {
		binary.Write(buf, binary.LittleEndian, pcm[i])
	}

	// POST to WHISPER_URL
	whisper := os.Getenv("WHISPER_URL")
	if whisper == "" {
		logging.Sugar().Warn("Processor: WHISPER_URL not set, dropping audio")
		return
	}
	// build request
	req, _ := http.NewRequestWithContext(context.Background(), "POST", whisper, bytes.NewReader(buf.Bytes()))
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
	// map ssrc -> username
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
