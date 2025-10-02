package voice

import (
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/discord-voice-lab/internal/logging"
)

// getSaveAudioDir returns the configured save audio directory or empty string
// if saving is disabled.
func getSaveAudioDir() string {
	enabled := strings.ToLower(strings.TrimSpace(os.Getenv("SAVE_AUDIO_ENABLED")))
	if enabled != "true" {
		return ""
	}
	if v := strings.TrimSpace(os.Getenv("SAVE_AUDIO_DIR_CONTAINER")); v != "" {
		return v
	}
	return strings.TrimSpace(os.Getenv("SAVE_AUDIO_DIR"))
}

// getWakePhrases returns the configured wake phrases or a sensible default.
func getWakePhrases() []string {
	def := []string{"computer", "hey computer", "hello computer", "ok computer", "hey comp"}
	if v := strings.TrimSpace(os.Getenv("WAKE_PHRASES")); v != "" {
		parts := strings.Split(v, ",")
		out := make([]string, 0, len(parts))
		for _, p := range parts {
			s := strings.ToLower(strings.TrimSpace(p))
			if s != "" {
				out = append(out, s)
			}
		}
		if len(out) > 0 {
			return out
		}
	}
	return def
}

// initTTSClient configures and returns an optional TTSClient based on env vars.
func initTTSClient(sidecar *SidecarManager, saveDir string, orchTimeout int) *TTSClient {
	if ttsURL := strings.TrimSpace(os.Getenv("TTS_URL")); ttsURL != "" {
		return &TTSClient{
			URL:       ttsURL,
			AuthToken: strings.TrimSpace(os.Getenv("TTS_AUTH_TOKEN")),
			Client:    &http.Client{Timeout: time.Duration(orchTimeout) * time.Millisecond},
			Sidecar:   sidecar,
			SaveDir:   saveDir,
			TimeoutMs: orchTimeout,
		}
	}
	return nil
}

// startBackgroundWorkers starts common background goroutines for the processor
// (opus frame worker, accumulator flusher, stats ticker, aggregation flusher)
// to keep NewProcessorWithResolver concise. It expects p to be initialized
// with necessary channels, context, and WaitGroup.
func startBackgroundWorkers(p *Processor) {
	// opus frame worker
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

	// accumulator flusher
	p.wg.Add(1)
	go func() {
		defer p.wg.Done()
		ticker := time.NewTicker(100 * time.Millisecond)
		defer ticker.Stop()
		for {
			select {
			case <-p.ctx.Done():
				return
			case <-ticker.C:
				p.flushExpiredAccums()
			}
		}
	}()

	// stats ticker
	p.wg.Add(1)
	go func() {
		defer p.wg.Done()
		statsTicker := time.NewTicker(15 * time.Second)
		defer statsTicker.Stop()
		for {
			select {
			case <-p.ctx.Done():
				return
			case <-statsTicker.C:
				// periodic stats hook (noop by default)
			}
		}
	}()

	// aggregation flusher
	p.wg.Add(1)
	go func() {
		defer p.wg.Done()
		ticker := time.NewTicker(200 * time.Millisecond)
		defer ticker.Stop()
		for {
			select {
			case <-p.ctx.Done():
				return
			case <-ticker.C:
				p.flushExpiredAggs()
			}
		}
	}()
	logging.Infow("Processor: background workers started")
}
