//go:build !opus
// +build !opus

package voice

// This file provides a minimal stub of the voice Processor API for builds
// that do not include libopus. The real implementation is in processor.go
// which is built with the `opus` build tag.

type Processor struct{}

// NewProcessor returns a no-op Processor in non-opus builds.
func NewProcessor() (*Processor, error) {
	return &Processor{}, nil
}

func (p *Processor) Close() error { return nil }

// Handler stubs accept any parameters (variadic) so they can be used as
// placeholders for discordgo handler registration in non-opus builds.
func (p *Processor) HandleVoiceState(args ...interface{})     {}
func (p *Processor) HandleSpeakingUpdate(args ...interface{}) {}
