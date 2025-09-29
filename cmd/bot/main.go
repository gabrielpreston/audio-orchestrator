package main

import (
	"encoding/json"
	"fmt"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"go.uber.org/zap"

	"github.com/bwmarrin/discordgo"
	"github.com/discord-voice-lab/internal/logging"
	"github.com/discord-voice-lab/internal/voice"
)

// extractMeta pulls common searchable fields from known event types.
func extractMeta(evt interface{}) (evtType, guildID, channelID, userID string, ssrc uint32, speaking bool) {
	evtType = fmt.Sprintf("%T", evt)
	switch e := evt.(type) {
	case *discordgo.VoiceStateUpdate:
		evtType = "VoiceStateUpdate"
		guildID = e.GuildID
		channelID = e.ChannelID
		userID = e.UserID
	case *discordgo.VoiceSpeakingUpdate:
		evtType = "VoiceSpeakingUpdate"
		userID = e.UserID
		ssrc = uint32(e.SSRC)
		speaking = e.Speaking
	case *discordgo.Ready:
		evtType = "Ready"
		if e.User.ID != "" {
			userID = e.User.ID
		}
	case *discordgo.GuildCreate:
		evtType = "GuildCreate"
		if e.ID != "" {
			guildID = e.ID
		}
	}
	return
}

// redactLargeValues inspects a generic JSON object (as bytes) and replaces
// values larger than redactBytes with a placeholder. Only applies to string
// values; other types are left intact. Returns the potentially-modified JSON
// bytes. If parsing fails, returns original bytes.
func redactLargeValues(raw []byte, redactBytes int64) []byte {
	if redactBytes <= 0 {
		return raw
	}
	var v any
	if err := json.Unmarshal(raw, &v); err != nil {
		return raw
	}

	var walk func(any) any
	walk = func(x any) any {
		switch vv := x.(type) {
		case map[string]any:
			for k, val := range vv {
				vv[k] = walk(val)
			}
			return vv
		case []any:
			for i, it := range vv {
				vv[i] = walk(it)
			}
			return vv
		case string:
			if int64(len(vv)) > redactBytes {
				return fmt.Sprintf("<redacted %d bytes>", len(vv))
			}
			return vv
		default:
			return vv
		}
	}

	cleaned := walk(v)
	out, err := json.Marshal(cleaned)
	if err != nil {
		return raw
	}
	return out
}

func main() {
	// Initialize centralized logging
	loggingSugar := logging.Init()
	if loggingSugar == nil {
		// fallback to a basic zap logger if initialization failed
		l, _ := zap.NewProduction()
		defer l.Sync()
		loggingSugar = l.Sugar()
	}
	sugar := loggingSugar
	// expose logLevel from environment (used later)
	logLevel := strings.ToLower(os.Getenv("LOG_LEVEL"))

	token := os.Getenv("DISCORD_BOT_TOKEN")
	if token == "" {
		sugar.Fatal("DISCORD_BOT_TOKEN required")
	}
	dg, err := discordgo.New("Bot " + token)
	if err != nil {
		sugar.Fatalf("discordgo.New: %v", err)
	}

	// Create voice processor
	sugar.Infow("creating voice processor")
	vp, err := voice.NewProcessor()
	if err != nil {
		sugar.Fatalf("voice.NewProcessor: %v", err)
	}
	sugar.Infow("voice processor created")

	// PAYLOAD_MAX_BYTES controls how many bytes of payload we log
	maxPayload := int64(8 * 1024)
	if v := os.Getenv("PAYLOAD_MAX_BYTES"); v != "" {
		if n, err := strconv.ParseInt(v, 10, 64); err == nil && n > 0 {
			maxPayload = n
		} else {
			sugar.Warnf("invalid PAYLOAD_MAX_BYTES=%s; using default %d", v, maxPayload)
		}
	}

	// DETAILED_EVENTS: comma-separated event type names which should always
	// produce detailed dumps regardless of LOG_LEVEL.
	detailedEvents := map[string]struct{}{}
	if v := os.Getenv("DETAILED_EVENTS"); v != "" {
		for _, part := range strings.Split(v, ",") {
			if t := strings.TrimSpace(part); t != "" {
				detailedEvents[t] = struct{}{}
			}
		}
	}

	// REDACT_LARGE_BYTES: strings longer than this will be replaced in
	// detailed dumps. Defaults to 1024 bytes.
	redactLarge := int64(1024)
	if v := os.Getenv("REDACT_LARGE_BYTES"); v != "" {
		if n, err := strconv.ParseInt(v, 10, 64); err == nil && n > 0 {
			redactLarge = n
		} else {
			sugar.Warnf("invalid REDACT_LARGE_BYTES=%s; using default %d", v, redactLarge)
		}
	}

	// Register a single generic handler to log every incoming event payload
	sugar.Infow("registering generic event handler: all event types")
	dg.AddHandler(func(s *discordgo.Session, evt interface{}) {
		// Attempt to marshal the incoming event to JSON for readable logging.
		// Use a type switch to also forward voice-related events to the processor.
		// Keep logs human-friendly and truncate very large payloads.
		var (
			b   []byte
			err error
		)

		// json.Marshal can panic if there are unexported fields; use a safe
		// fallback to fmt.Sprintf when marshaling fails.
		b, err = json.Marshal(evt)
		if err != nil {
			// fallback: use sprint with %+v which is still human-readable
			b = []byte(fmt.Sprintf("%+v", evt))
		}

		// Compact structured metadata
		evtType, guildID, channelID, userID, ssrc, speaking := extractMeta(evt)
		truncated := int64(len(b)) > maxPayload
		// Log a compact single-line structured event for quick scanning
		sugar.Infow("event",
			"type", evtType,
			"guild_id", guildID,
			"channel_id", channelID,
			"user_id", userID,
			"ssrc", ssrc,
			"speaking", speaking,
			"payload_len", len(b),
			"truncated", truncated,
		)

		// Forward known voice events to the processor using a type switch
		switch e := evt.(type) {
		case *discordgo.VoiceStateUpdate:
			vp.HandleVoiceState(s, e)
		case *discordgo.VoiceSpeakingUpdate:
			// Log speaking updates at INFO so they are visible even without debug
			sugar.Infow("speaking_update", "ssrc", e.SSRC, "user", e.UserID, "speaking", e.Speaking)
			vp.HandleSpeakingUpdate(s, e)

		default:
			// Only produce detailed output when debugging or when the event
			// type is explicitly requested in DETAILED_EVENTS.
			if logLevel == "debug" || func() bool {
				_, ok := detailedEvents[evtType]
				return ok
			}() {
				var pretty []byte
				if p, err := json.MarshalIndent(evt, "", "  "); err == nil {
					// redact only very large string fields
					r := redactLargeValues(p, redactLarge)
					pretty = r
				} else {
					pretty = []byte(fmt.Sprintf("%+v", evt))
				}

				// Truncate detailed dump if too large
				if int64(len(pretty)) > maxPayload {
					pretty = append(pretty[:maxPayload], []byte("...(truncated)")...)
				}

				sugar.Debugw("event_detailed",
					"type", evtType,
					"payload_pretty", string(pretty),
				)
			}
		}
	})
	sugar.Infow("generic handler registered")

	sugar.Infow("opening discord session")
	if err := dg.Open(); err != nil {
		sugar.Fatalf("Open: %v", err)
	}
	sugar.Infof("connected: user=%s#%s id=%s", dg.State.User.Username, dg.State.User.Discriminator, dg.State.User.ID)

	// join voice channel if configured
	var vc *discordgo.VoiceConnection
	gid := os.Getenv("GUILD_ID")
	cid := os.Getenv("VOICE_CHANNEL_ID")
	if gid != "" && cid != "" {
		// NOTE: ensure we do NOT self-deafen; we want to receive audio
		sugar.Infof("attempting ChannelVoiceJoin guild=%s channel=%s", gid, cid)
		vconn, err := dg.ChannelVoiceJoin(gid, cid, false, false)
		if err != nil {
			sugar.Warnf("ChannelVoiceJoin error: %v", err)
		} else {
			vc = vconn
			sugar.Infof("joined voice channel %s in guild %s", cid, gid)
			// Diagnostic: log whether we have an OpusRecv channel and basic vc info
			if vc == nil {
				sugar.Warn("voice connection is nil after ChannelVoiceJoin")
			} else {
				sugar.Infow("voice connection details", "opus_recv_nil", vc.OpusRecv == nil)
			}
			// start a goroutine to receive opus packets from the VoiceConnection
			if vc.OpusRecv == nil {
				sugar.Warn("voice connection OpusRecv channel is nil; incoming audio will not be received")
			} else {
				// Log channel buffer stats to help diagnose whether packets are
				// being enqueued by the voice subsystem.
				// Note: reflect the current length and capacity at startup.
				sugar.Infow("opus receive loop: starting", "chan_len", len(vc.OpusRecv), "chan_cap", cap(vc.OpusRecv))
				go func() {
					sugar.Info("opus receive loop: started")
					for pkt := range vc.OpusRecv {
						if pkt == nil {
							continue
						}

						sugar.Infof("opus receive loop: pkt SSRC=%d seq=%d ts=%d opus_bytes=%d", pkt.SSRC, pkt.Sequence, pkt.Timestamp, len(pkt.Opus))
						// hand off to processor
						vp.ProcessOpusFrame(pkt.SSRC, pkt.Opus)
					}
					sugar.Info("opus receive loop: ended")
				}()
				// Start a background goroutine to emit a periodic heartbeat log
				// so the operator can see the receive loop is alive even when
				// no packets arrive.
				go func() {
					// only run while vc is not nil
					for vc != nil {
						sugar.Debugw("opus receive loop: heartbeat", "chan_len", len(vc.OpusRecv), "chan_cap", cap(vc.OpusRecv))
						// sleep 5s between heartbeats
						// use time.Sleep inline to avoid importing additional packages at top
						// the overhead is minimal
						time.Sleep(5 * time.Second)
					}
				}()
			}
		}
	} else {
		sugar.Info("GUILD_ID or VOICE_CHANNEL_ID not set; not auto-joining voice channel")
	}

	// wait for signal
	sugar.Info("entering main wait; press Ctrl+C to shutdown")
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	sig := <-stop
	sugar.Infof("received signal: %v", sig)

	// gracefully stop: leave voice, close processor, close session
	sugar.Info("shutting down: leaving voice, closing processor and session")
	if vc != nil {
		vc.Close()
		sugar.Infof("left voice channel %s in guild %s", cid, gid)
	}
	if err := vp.Close(); err != nil {
		sugar.Warnf("processor close error: %v", err)
	}
	if err := dg.Close(); err != nil {
		sugar.Warnf("discord session close error: %v", err)
	}
	sugar.Info("shutdown complete")
}
