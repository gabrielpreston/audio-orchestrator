package voice

import (
	"time"
)

// pcmAccum holds accumulated PCM samples and metadata for an SSRC.
type pcmAccum struct {
	samples       []int16
	last          time.Time
	correlationID string
	lastAboveRms  time.Time
	createdAt     time.Time
	userID        string
	username      string
}

// transcriptAgg holds an aggregated transcript for an SSRC.
type transcriptAgg struct {
	text          string
	last          time.Time
	correlationID string
	wakeDetected  bool
	wakeStripped  string
	createdAt     time.Time
}
