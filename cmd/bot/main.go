package main

import (
	"encoding/json"
	"fmt"
	"os"
	"os/signal"
	"reflect"
	"strconv"
	"strings"
	"syscall"

	"go.uber.org/zap"

	"github.com/bwmarrin/discordgo"
	"github.com/discord-voice-lab/internal/logging"
	"github.com/discord-voice-lab/internal/voice"
)

// sensitiveKeys lists JSON keys which should never be logged in plaintext.
var sensitiveKeys = map[string]struct{}{
	"token": {}, "session_id": {}, "access_token": {}, "refresh_token": {},
	"authorization": {}, "password": {}, "email": {}, "client_secret": {},
}

// redactAny walks a decoded JSON value (map[string]any / []any) and replaces
// values for sensitive keys with a placeholder. It modifies maps/slices in place.
func redactAny(v any) any {
	switch vv := v.(type) {
	case map[string]any:
		for k, val := range vv {
			lk := strings.ToLower(k)
			if _, ok := sensitiveKeys[lk]; ok {
				vv[k] = "<redacted>"
				continue
			}
			// Recurse into nested structures
			vv[k] = redactAny(val)
		}
		return vv
	case []any:
		for i, it := range vv {
			vv[i] = redactAny(it)
		}
		return vv
	default:
		return v
	}
}

// extractMeta pulls common searchable fields from known event types.
// extractMeta pulls common searchable fields from known event types and
// also returns a flexible metadata map built from typed fields, JSON
// payloads, or reflection. The returned meta map contains stringified
// key/value pairs discovered on the event which can be used for richer
// logging and exploration.
func extractMeta(evt interface{}) (evtType, guildID, channelID, userID string, ssrc uint32, speaking bool, meta map[string]any) {
	meta = make(map[string]any)
	if evt == nil {
		evtType = "<nil>"
		return
	}

	// Default type name
	evtType = fmt.Sprintf("%T", evt)

	// Helper to add to meta if value non-empty
	addMeta := func(k string, v any) {
		if v == nil {
			return
		}
		// Preserve original types where possible. For numeric json decoded
		// values (float64) we leave them as-is; callers can inspect types.
		switch tv := v.(type) {
		case string:
			if tv != "" {
				meta[k] = tv
			}
		default:
			meta[k] = tv
		}
	}

	// Known typed cases (fast-path)
	switch e := evt.(type) {
	case *discordgo.VoiceStateUpdate:
		evtType = "VoiceStateUpdate"
		guildID = e.GuildID
		channelID = e.ChannelID
		userID = e.UserID
		addMeta("guild_id", e.GuildID)
		addMeta("channel_id", e.ChannelID)
		addMeta("user_id", e.UserID)
	case *discordgo.VoiceSpeakingUpdate:
		evtType = "VoiceSpeakingUpdate"
		userID = e.UserID
		ssrc = uint32(e.SSRC)
		speaking = e.Speaking
		addMeta("user_id", e.UserID)
		addMeta("ssrc", e.SSRC)
		addMeta("speaking", e.Speaking)
	case *discordgo.Ready:
		evtType = "Ready"
		if e.User != nil && e.User.ID != "" {
			userID = e.User.ID
			addMeta("user_id", e.User.ID)
		}
	case *discordgo.GuildCreate:
		evtType = "GuildCreate"
		if e.ID != "" {
			guildID = e.ID
			addMeta("guild_id", e.ID)
		}
	case *discordgo.Event:
		// Event contains RawData which is JSON -- try to decode common keys
		evtType = e.Type
		var m map[string]any
		if err := json.Unmarshal(e.RawData, &m); err == nil {
			for k, v := range m {
				addMeta(k, v)
			}
			// map common names
			if v, ok := m["guild_id"].(string); ok {
				guildID = v
			}
			if v, ok := m["channel_id"].(string); ok {
				channelID = v
			}
			if v, ok := m["user_id"].(string); ok {
				userID = v
			}
			// ssrc may be a number; try several numeric types
			if v, ok := m["ssrc"].(float64); ok {
				ssrc = uint32(v)
			} else if v, ok := m["ssrc"].(int); ok {
				ssrc = uint32(v)
			} else if v, ok := m["ssrc"].(int64); ok {
				ssrc = uint32(v)
			}
			if v, ok := m["speaking"].(bool); ok {
				speaking = v
			}
		}
	}

	// If we didn't hit a known typed case, try to decode generically from
	// some common shapes: map[string]any, json.RawMessage, []byte, or struct via reflection.
	if len(meta) == 0 {
		switch v := evt.(type) {
		case map[string]any:
			for k, val := range v {
				addMeta(k, val)
				if k == "guild_id" {
					if s, ok := val.(string); ok {
						guildID = s
					}
				}
				if k == "channel_id" {
					if s, ok := val.(string); ok {
						channelID = s
					}
				}
				if k == "user_id" {
					if s, ok := val.(string); ok {
						userID = s
					}
				}
			}
		case json.RawMessage:
			var m map[string]any
			if err := json.Unmarshal(v, &m); err == nil {
				for k, val := range m {
					addMeta(k, val)
				}
			}
		case []byte:
			var m map[string]any
			if err := json.Unmarshal(v, &m); err == nil {
				for k, val := range m {
					addMeta(k, val)
				}
			}
		default:
			// Use reflection for structs: iterate exported fields and use json tag if present
			rv := reflect.ValueOf(evt)
			if rv.Kind() == reflect.Ptr {
				rv = rv.Elem()
			}
			if rv.Kind() == reflect.Struct {
				rt := rv.Type()
				for i := 0; i < rt.NumField(); i++ {
					f := rt.Field(i)
					if f.PkgPath != "" { // unexported
						continue
					}
					name := f.Name
					if tag := f.Tag.Get("json"); tag != "" {
						// json tag may be like "name,omitempty"
						parts := strings.Split(tag, ",")
						if parts[0] != "" {
							name = parts[0]
						}
					}
					fv := rv.Field(i)
					if !fv.IsValid() || (fv.Kind() == reflect.Ptr && fv.IsNil()) {
						continue
					}
					var val any
					if fv.Kind() == reflect.Ptr {
						val = fv.Elem().Interface()
					} else {
						val = fv.Interface()
					}
					addMeta(name, val)
				}
			}
		}
	}

	// Populate canonical return values from meta if still empty
	if guildID == "" {
		if v, ok := meta["guild_id"]; ok {
			if s, ok2 := v.(string); ok2 {
				guildID = s
			}
		}
	}
	if channelID == "" {
		if v, ok := meta["channel_id"]; ok {
			if s, ok2 := v.(string); ok2 {
				channelID = s
			}
		}
	}
	if userID == "" {
		if v, ok := meta["user_id"]; ok {
			if s, ok2 := v.(string); ok2 {
				userID = s
			}
		}
	}
	// ssrc and speaking are already set where possible

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

// (safeMarshal removed; safeMarshalIndent is used where indentation is needed)

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

	// By default set a conservative intent mask needed for voice functionality.
	// Guilds + GuildVoiceStates allow receiving GUILD_CREATE and VoiceStateUpdate
	// events which are sufficient for mapping join/leave and mute state.
	defaultIntents := discordgo.IntentsGuilds | discordgo.IntentsGuildVoiceStates
	// If user has not configured Identify.Intents, apply our conservative default.
	if dg.Identify.Intents == 0 {
		dg.Identify = discordgo.Identify{Intents: defaultIntents}
	}

	// Warn if privileged intents are present in the mask so operators remember
	// to enable them in the Developer Portal. Privileged intents include
	// IntentsGuildMembers and IntentsGuildPresences.
	privileged := discordgo.IntentsGuildMembers | discordgo.IntentsGuildPresences
	if dg.Identify.Intents&privileged != 0 {
		sugar.Warnw("bot is requesting privileged gateway intents; ensure these are enabled in the Discord Developer Portal", "intents", dg.Identify.Intents)
	}

	sugar.Infow("using gateway intents", "intents", dg.Identify.Intents)

	// Open the Discord session so the bot connects and can receive events.
	sugar.Infow("opening discord session")
	if err := dg.Open(); err != nil {
		sugar.Fatalf("discord session open failed: %v", err)
	}
	sugar.Infow("discord session opened")

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

	// Wait for termination signal (Ctrl+C, Docker stop) and shutdown gracefully.
	// Register the processor handlers for voice state and speaking updates so
	// it can map SSRC <-> user IDs. Wrap the method calls in explicit
	// functions so discordgo's reflection validation accepts them.
	dg.AddHandler(func(s *discordgo.Session, vs *discordgo.VoiceStateUpdate) {
		vp.HandleVoiceState(s, vs)
	})
	// Note: voice speaking updates are delivered on the VoiceConnection
	// websocket. We'll register a voice-level handler after joining so
	// the handler has access to the VoiceConnection. For now we omit a
	// session-level VoiceSpeakingUpdate handler which would be invalid.

	// Generic event logger: logs every event that comes across the wire.
	// Use *discordgo.Event as the handler signature so discordgo's
	// reflection validation accepts it. Prefer the populated evt.Struct
	// (if present) which is a typed event; otherwise unmarshal RawData.
	dg.AddHandler(func(s *discordgo.Session, evt *discordgo.Event) {
		var obj any
		if evt.Struct != nil {
			obj = evt.Struct
		} else {
			// fallback to decoding RawData into a generic structure
			var v any
			if err := json.Unmarshal(evt.RawData, &v); err == nil {
				// redact sensitive fields before using the decoded object
				obj = redactAny(v)
			} else {
				// as a last resort, keep raw bytes as a string (not ideal)
				// avoid logging raw bytes that might include tokens
				obj = "<raw data omitted>"
			}
		}

		evtType, guildID, channelID, userID, ssrc, speaking, meta := extractMeta(obj)
		// If extractMeta couldn't identify a typed event, use the gateway Type
		if evtType == fmt.Sprintf("%T", obj) || evtType == "" {
			evtType = evt.Type
		}

		// Marshal the event safely and redact/truncate according to config.
		payload := safeMarshalIndent(obj)
		// If this event type is in detailedEvents, include full payload but
		// redact very large strings. Otherwise, truncate to maxPayload.
		if _, ok := detailedEvents[evtType]; ok {
			payload = redactLargeValues(payload, redactLarge)
		} else {
			if int64(len(payload)) > maxPayload {
				// include a short truncated note
				note := fmt.Sprintf("\n<truncated %d bytes>", len(payload))
				payload = append(payload[:maxPayload], []byte(note)...)
			}
		}

		sugar.Infow("discord event", "type", evtType, "guild", guildID, "channel", channelID, "user", userID, "ssrc", ssrc, "speaking", speaking, "meta", meta, "payload", string(payload))
	})

	// If configured, attempt to auto-join a voice channel.
	var vc *discordgo.VoiceConnection
	guildID := os.Getenv("GUILD_ID")
	voiceChannelID := os.Getenv("VOICE_CHANNEL_ID")
	if guildID != "" && voiceChannelID != "" {
		sugar.Infow("joining voice channel", "guild", guildID, "channel", voiceChannelID)
		vconn, err := dg.ChannelVoiceJoin(guildID, voiceChannelID, false, false)
		if err != nil {
			sugar.Warnf("voice join failed: %v", err)
		} else {
			vc = vconn
			// Register voice-level handler for speaking updates which provides
			// the VoiceConnection and a *discordgo.VoiceSpeakingUpdate.
			vc.AddHandler(func(v *discordgo.VoiceConnection, su *discordgo.VoiceSpeakingUpdate) {
				// Log speaking updates observed on the voice websocket so we
				// can confirm they arrive here. Then forward to the processor
				// which will map SSRC -> user. Pass the session so the
				// processor has access to session-based helpers if needed.
				sugar.Infow("voice connection speaking update received", "user", su.UserID, "ssrc", su.SSRC, "speaking", su.Speaking)
				vp.HandleSpeakingUpdate(dg, su)
			})
			sugar.Infow("voice joined", "guild", guildID, "channel", voiceChannelID)
		}
	}

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)

	<-stop
	sugar.Infow("shutdown signal received, closing resources")

	if err := vp.Close(); err != nil {
		sugar.Warnf("processor close error: %v", err)
	}
	// If we joined a voice channel, disconnect cleanly first.
	if vc != nil {
		if err := vc.Disconnect(); err != nil {
			sugar.Warnf("voice disconnect error: %v", err)
		}
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
