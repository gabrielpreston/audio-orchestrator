package voice

import (
	"bytes"
	"encoding/binary"
	"math"
	"strings"
	"sync/atomic"
	"time"

	"github.com/discord-voice-lab/internal/logging"
	"github.com/google/uuid"
)

// Decoder helpers extracted from processor.go. These rely on Processor
// methods and fields defined in processor.go.

// handleOpusPacket decodes an Opus packet and appends decoded samples.
// It increments decode error counters on failures.
func (p *Processor) handleOpusPacket(pkt opusPacket) {
	ssrc := pkt.ssrc
	pcm := make([]int16, 48000/50)
	n, err := p.dec.Decode(pkt.data, pcm)
	if err != nil {
		atomic.AddInt64(&p.decodeErrCount, 1)
		logging.Errorw("opus decode error", "ssrc", ssrc, "err", err)
		return
	}
	samples := make([]int16, n)
	copy(samples, pcm[:n])
	_ = p.appendAccum(ssrc, samples, pkt.correlationID)
}

// appendAccum adds decoded samples to the per-SSRC accumulator and returns the correlation id.
func (p *Processor) appendAccum(ssrc uint32, samples []int16, incomingCID string) string {
	p.accumMu.Lock()
	defer p.accumMu.Unlock()
	a, ok := p.accums[ssrc]
	if !ok {
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
		if incomingCID != "" {
			a.correlationID = incomingCID
		} else {
			a.correlationID = uuid.NewString()
		}
		p.accums[ssrc] = a
	}
	if a.correlationID == "" {
		if incomingCID != "" {
			a.correlationID = incomingCID
		} else {
			a.correlationID = uuid.NewString()
		}
	}
	a.samples = append(a.samples, samples...)
	a.last = time.Now()
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
	durMs := (len(a.samples) * 1000) / 48000
	if durMs >= p.maxAccumMs || (durMs >= p.minFlushMs && p.flushOnMin) {
		go func(ssrc uint32) { p.flushAccum(ssrc) }(ssrc)
	}
	return a.correlationID
}

func (p *Processor) flushAccum(ssrc uint32) {
	// simplified: reuse original logic; kept inline to preserve behavior
	p.accumMu.Lock()
	a, ok := p.accums[ssrc]
	if !ok || len(a.samples) == 0 {
		p.accumMu.Unlock()
		return
	}
	samples := a.samples
	corrID := a.correlationID
	createdAt := a.createdAt
	uid := a.userID
	uname := a.username
	delete(p.accums, ssrc)
	p.accumMu.Unlock()
	pcmBytes := &bytes.Buffer{}
	for _, s := range samples {
		binary.Write(pcmBytes, binary.LittleEndian, s)
	}
	// VAD and saving logic omitted here for brevity; delegate to sendPCMToWhisper
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
	if uid == "" {
		logging.Warnw("dropping audio chunk with unknown user; not sending to STT", "ssrc", ssrc, "correlation_id", corrID)
		return
	}
	_ = p.sendPCMToWhisper(ssrc, pcmBytes.Bytes(), corrID, createdAt, uid, uname)
}

func (p *Processor) flushExpiredAccums() {
	now := time.Now()
	var toFlush []uint32
	p.accumMu.Lock()
	for ssrc, a := range p.accums {
		durMs := (len(a.samples) * 1000) / 48000
		if durMs >= p.maxAccumMs {
			toFlush = append(toFlush, ssrc)
			continue
		}
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
