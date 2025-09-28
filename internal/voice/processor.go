//go:build opus
// +build opus

package voice

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"sync"
	"time"

	"github.com/bwmarrin/discordgo"
	"github.com/hraban/opus"
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
	return &Processor{ssrcMap: make(map[uint32]string), dec: dec, httpClient: &http.Client{Timeout: 15 * time.Second}}, nil
}

func (p *Processor) Close() error {
	// nothing yet
	return nil
}

// HandleVoiceState listens for voice state updates to map userID <-> SSRC (best-effort)
func (p *Processor) HandleVoiceState(s *discordgo.Session, vs *discordgo.VoiceStateUpdate) {
	// no-op for now
	_ = s
	_ = vs
}

// HandleSpeakingUpdate receives discordgo speaking updates and is used to map ssrc->user
func (p *Processor) HandleSpeakingUpdate(s *discordgo.Session, su *discordgo.VoiceSpeakingUpdate) {
	// map SSRC to user
	p.mu.Lock()
	defer p.mu.Unlock()
	p.ssrcMap[uint32(su.SSRC)] = su.UserID
}

// This function would be called by the discord voice receive loop with raw opus frames.
// For simplicity in this scaffold, we'll expose a method to accept encoded opus frames and process them.
func (p *Processor) ProcessOpusFrame(ssrc uint32, opusPayload []byte) {
	// decode opusPayload (assuming it's an encoded frame) into PCM16
	pcm := make([]int16, 48000*2/50) // allocate for 20ms at 48k, stereo
	n, err := p.dec.Decode(opusPayload, pcm)
	if err != nil {
		log.Printf("opus decode error: %v", err)
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
		log.Printf("WHISPER_URL not set, dropping audio")
		return
	}
	// build request
	req, _ := http.NewRequestWithContext(context.Background(), "POST", whisper, bytes.NewReader(buf.Bytes()))
	req.Header.Set("Content-Type", "audio/pcm")
	resp, err := p.httpClient.Do(req)
	if err != nil {
		log.Printf("whisper post error: %v", err)
		return
	}
	defer resp.Body.Close()
	var out map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		log.Printf("whisper decode: %v", err)
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
	log.Printf("[%s] => %s", username, transcript)
}
