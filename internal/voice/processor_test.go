package voice

import (
	"testing"

	"github.com/bwmarrin/discordgo"
)

// TestHandleSpeakingUpdateMapsSSRC verifies that HandleSpeakingUpdate records
// the mapping from SSRC to user ID in the processor's internal map.
func TestHandleSpeakingUpdateMapsSSRC(t *testing.T) {
	p, err := NewProcessor()
	if err != nil {
		t.Fatalf("NewProcessor: %v", err)
	}
	defer func() { _ = p.Close() }()

	su := &discordgo.VoiceSpeakingUpdate{
		UserID:   "test-user-1",
		SSRC:     12345,
		Speaking: true,
	}

	// Call the handler directly (synchronous) and check mapping.
	p.HandleSpeakingUpdate(nil, su)

	p.mu.Lock()
	got := p.ssrcMap[uint32(su.SSRC)]
	p.mu.Unlock()

	if got != su.UserID {
		t.Fatalf("ssrc mapping mismatch: want=%s got=%s", su.UserID, got)
	}
}
