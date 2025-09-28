//go:build !opus
// +build !opus

package voice

import "github.com/bwmarrin/discordgo"

// This file provides a minimal stub of the voice Processor API for builds
// that do not include libopus. The real implementation is in processor.go
// which is built with the `opus` build tag.

type Processor struct{}

// NewProcessor returns a no-op Processor in non-opus builds.
func NewProcessor() (*Processor, error) {
	return &Processor{}, nil
}

func (p *Processor) Close() error { return nil }

// Correct handler signatures so discordgo.AddHandler accepts them in non-opus builds.
func (p *Processor) HandleVoiceState(s *discordgo.Session, vs *discordgo.VoiceStateUpdate)        {}
func (p *Processor) HandleSpeakingUpdate(s *discordgo.Session, su *discordgo.VoiceSpeakingUpdate) {}
