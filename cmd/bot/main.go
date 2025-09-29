package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"strings"

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

// safeMarshal attempts to JSON-marshal v but protects against panics and
// returns a human-friendly fallback when marshaling fails.
func safeMarshal(v any) []byte {
	defer func() {
		if r := recover(); r != nil {
			// swallow panic and fall back to fmt
		}
	}()
	b, err := json.Marshal(v)
	if err == nil {
		return b
	}
	// fallback to Sprint which is safer for types with unexported fields
	return []byte(fmt.Sprintf("%+v", v))
}

// safeMarshalIndent behaves like json.MarshalIndent but falls back to
// fmt.Sprintf on error or panic.
func safeMarshalIndent(v any) []byte {
	defer func() {
		if r := recover(); r != nil {
			// swallow panic
		}
	}()
	b, err := json.MarshalIndent(v, "", "  ")
	if err == nil {
		return b
	}
	return []byte(fmt.Sprintf("%+v", v))
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

	if err := vp.Close(); err != nil {
		sugar.Warnf("processor close error: %v", err)
	}
	if err := dg.Close(); err != nil {
		sugar.Warnf("discord session close error: %v", err)
	}
	// ensure any logging buffers are flushed
	if l := zap.L(); l != nil {
		_ = l.Sync()
	}
	sugar.Info("shutdown complete")
}
