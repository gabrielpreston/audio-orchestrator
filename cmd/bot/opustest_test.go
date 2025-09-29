package main

import (
	"sync"
	"testing"
	"time"

	"github.com/bwmarrin/discordgo"
)

// fakeProcessor satisfies the minimal surface used in main.go: ProcessOpusFrame
type fakeProcessor struct {
	mu       sync.Mutex
	called   bool
	lastSSRC uint32
}

func (f *fakeProcessor) ProcessOpusFrame(ssrc uint32, b []byte) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.called = true
	f.lastSSRC = ssrc
}

// TestOpusRecvWiring simulates a VoiceConnection with an OpusRecv channel and
// verifies that frames placed into the channel are observed by the processor.
func TestOpusRecvWiring(t *testing.T) {
	vc := &discordgo.VoiceConnection{}
	vc.OpusRecv = make(chan *discordgo.Packet, 2)

	fp := &fakeProcessor{}

	// Start the goroutine that mirrors main.go behavior.
	go func() {
		for pkt := range vc.OpusRecv {
			if pkt == nil {
				continue
			}
			fp.ProcessOpusFrame(uint32(pkt.SSRC), pkt.Opus)
		}
	}()

	// Send a single packet and close the channel to terminate the goroutine.
	vc.OpusRecv <- &discordgo.Packet{SSRC: 42, Opus: []byte{0x01, 0x02}}
	close(vc.OpusRecv)

	// Allow a small amount of time for the goroutine to process.
	time.Sleep(50 * time.Millisecond)

	fp.mu.Lock()
	called := fp.called
	last := fp.lastSSRC
	fp.mu.Unlock()

	if !called {
		t.Fatalf("fake processor was not called")
	}
	if last != 42 {
		t.Fatalf("unexpected ssrc: want=42 got=%d", last)
	}
}
