package voice

import (
	"time"
)

// pcmAccum holds accumulated PCM samples for an SSRC and timestamp of last append
type pcmAccum struct {
	samples       []int16
	last          time.Time
	correlationID string
	lastAboveRms  time.Time
	createdAt     time.Time
	userID        string
	username      string
}

// transcriptAgg holds an aggregated transcript for an SSRC and timestamp of last update
type transcriptAgg struct {
	text          string
	last          time.Time
	correlationID string
	wakeDetected  bool
	wakeStripped  string
	createdAt     time.Time
}
