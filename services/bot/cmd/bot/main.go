package main

import (
	"context"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/bwmarrin/discordgo"
	"github.com/discord-voice-lab/internal/logging"
	"github.com/discord-voice-lab/internal/mcp"
	mcpconfig "github.com/discord-voice-lab/internal/mcp/config"
	"github.com/discord-voice-lab/internal/voice"
)

// Minimal main for the bot. See internal/voice/discord_resolver.go for
// the resolver implementation. Non-essential logging helpers were removed
// to keep this entrypoint focused and compact.

func main() {
	// Initialize centralized logging
	logging.Init()
	defer logging.Sync()

	rootCtx, rootCancel := context.WithCancel(context.Background())
	defer rootCancel()

	serviceName := os.Getenv("MCP_SERVICE_NAME")
	if serviceName == "" {
		serviceName = "bot"
	}

	var mcpClients []*mcp.ClientWrapper

	manifestResult, manifestErr := mcpconfig.LoadResult()
	if manifestErr != nil {
		logging.Warnw("failed to load mcp manifest", "err", manifestErr)
	} else if len(manifestResult.Order) > 0 {
		logging.Infow("loaded mcp configuration", "sources", manifestResult.Sources, "servers", len(manifestResult.Order))
		for _, serverName := range manifestResult.Order {
			server := manifestResult.Servers[serverName]
			if !server.EnabledValue() {
				logging.Debugw("skipping disabled mcp server", "server", serverName)
				continue
			}

			client := mcp.NewClientWrapper(serviceName, "v0.0.0")
			switch {
			case server.Transport != nil && strings.EqualFold(server.Transport.Type, "websocket"):
				wsURL := server.Transport.URL
				if wsURL == "" {
					logging.Warnw("mcp server missing websocket url", "server", serverName)
					continue
				}
				connectCtx, cancel := context.WithTimeout(rootCtx, 5*time.Second)
				err := client.ConnectWebSocket(connectCtx, wsURL)
				cancel()
				if err != nil {
					logging.Warnw("mcp websocket connect failed", "server", serverName, "err", err)
					continue
				}
				logging.Infow("connected mcp websocket server", "server", serverName)
			case server.Command != "":
				connectCtx, cancel := context.WithTimeout(rootCtx, 10*time.Second)
				err := client.ConnectCommand(connectCtx, serverName, server.Command, server.Args, server.Env)
				cancel()
				if err != nil {
					logging.Warnw("mcp command connect failed", "server", serverName, "err", err)
					continue
				}
				logging.Infow("started mcp command server", "server", serverName)
			default:
				logging.Warnw("mcp server missing transport configuration", "server", serverName)
				continue
			}

			mcpClients = append(mcpClients, client)
		}
	}

	if len(mcpClients) == 0 {
		if mcpURL := os.Getenv("MCP_SERVER_URL"); mcpURL != "" {
			wsURL := mcpURL
			if !strings.HasPrefix(wsURL, "ws://") && !strings.HasPrefix(wsURL, "wss://") {
				if strings.HasPrefix(wsURL, "http://") {
					wsURL = "ws://" + strings.TrimPrefix(wsURL, "http://")
				} else if strings.HasPrefix(wsURL, "https://") {
					wsURL = "wss://" + strings.TrimPrefix(wsURL, "https://")
				} else {
					wsURL = "ws://" + wsURL
				}
			}
			if !strings.HasSuffix(wsURL, "/mcp/ws") {
				wsURL = strings.TrimRight(wsURL, "/") + "/mcp/ws"
			}

			client := mcp.NewClientWrapper(serviceName, "v0.0.0")
			connectCtx, cancel := context.WithTimeout(rootCtx, 5*time.Second)
			err := client.ConnectWebSocket(connectCtx, wsURL)
			cancel()
			if err != nil {
				logging.Warnw("mcp websocket connect failed, falling back to Register", "err", err)
				botURL := os.Getenv("BOT_EXTERNAL_URL")
				if botURL == "" {
					botURL = "http://bot:8080"
				}
				if err := mcp.Register(serviceName, botURL); err != nil {
					logging.Warnw("mcp register failed", "err", err)
				}
			} else {
				mcpClients = append(mcpClients, client)
			}
		}
	}

	token := os.Getenv("DISCORD_BOT_TOKEN")
	if token == "" {
		logging.FatalExitf("DISCORD_BOT_TOKEN required")
	}
	dg, err := discordgo.New("Bot " + token)
	if err != nil {
		logging.FatalExitf("discordgo.New failed", "err", err)
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
		// privileged intents present (ensure enabled in Developer Portal)
	}

	// Open the Discord session so the bot connects and can receive events.
	if err := dg.Open(); err != nil {
		logging.FatalExitf("discord session open failed", "err", err)
	}

	// Create a single resolver backed by the discord session state and
	// reuse it for the voice processor and local logging so caches are shared.
	resolver := voice.NewDiscordResolver(dg)
	// Use the shared root context so subsystems can observe cancellation
	// during shutdown when we receive an OS signal.
	vp, err := voice.NewProcessorWithResolver(rootCtx, resolver)
	if err != nil {
		logging.FatalExitf("voice.NewProcessor failed", "err", err)
	}
	logging.Infow("voice processor created")

	// If ALLOWED_USER_IDS is set, parse it as a comma-separated list and
	// configure the processor to only accept audio from those users.
	if v := os.Getenv("ALLOWED_USER_IDS"); v != "" {
		parts := []string{}
		for _, p := range strings.Split(v, ",") {
			if t := strings.TrimSpace(p); t != "" {
				parts = append(parts, t)
			}
		}
		if len(parts) > 0 {
			vp.SetAllowedUsers(parts)
			logging.Infow("configured allowed users", "count", len(parts))
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

	// Register the processor handlers for voice state and speaking updates so
	// it can map SSRC <-> user IDs. Wrap the method calls in explicit
	// functions so discordgo's reflection validation accepts them.
	dg.AddHandler(func(s *discordgo.Session, vs *discordgo.VoiceStateUpdate) {
		vp.HandleVoiceState(s, vs)
	})

	// Generic event handler is a no-op because logging is suppressed.
	dg.AddHandler(func(s *discordgo.Session, evt *discordgo.Event) {
		// no-op
	})

	// If configured, attempt to auto-join a voice channel.
	var vc *discordgo.VoiceConnection
	guildID := os.Getenv("GUILD_ID")
	voiceChannelID := os.Getenv("VOICE_CHANNEL_ID")
	if guildID != "" && voiceChannelID != "" {
		// Try to resolve human-friendly names for the guild and channel
		_ = resolver.GuildName(guildID)
		_ = resolver.ChannelName(voiceChannelID)
		// joining voice channel
		vconn, err := dg.ChannelVoiceJoin(guildID, voiceChannelID, false, false)
		if err != nil {
			logging.Warnw("voice join failed", "err", err)
		} else {
			vc = vconn
			logging.Infow("joined voice channel", "guild_id", guildID, "channel_id", voiceChannelID)
			// Seed processor display-name cache from current voice channel participants
			vp.SeedVoiceChannelMembers(dg, guildID, voiceChannelID)
			// Register voice-level handler for speaking updates which provides
			// the VoiceConnection and a *discordgo.VoiceSpeakingUpdate.
			vc.AddHandler(func(v *discordgo.VoiceConnection, su *discordgo.VoiceSpeakingUpdate) {
				logging.Debugw("voice connection speaking update received", "ssrc", su.SSRC, "user_id", su.UserID)
				vp.HandleSpeakingUpdate(dg, su)
			})

			// If OpusRecv is non-nil, start a goroutine to read incoming opus
			// packets and forward them to the Processor. This keeps audio capture
			// logic out of the main event loop and allows the Processor to decode
			// and dispatch to STT asynchronously.
			if vc.OpusRecv != nil {
				go func(vc *discordgo.VoiceConnection) {
					// Loop until OpusRecv channel is closed, the VoiceConnection ends,
					// or the root context is cancelled. This ensures the application
					// can shut down promptly when requested.
					for {
						select {
						case <-rootCtx.Done():
							return
						case pkt, ok := <-vc.OpusRecv:
							if !ok {
								return
							}
							if pkt == nil {
								continue
							}
							vp.ProcessOpusFrame(uint32(pkt.SSRC), pkt.Opus)
						}
					}
				}(vc)
			} else {
				// voice connection has no OpusRecv
			}

		}
	}

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)

	<-stop
	// shutdown signal received

	// Cancel the root context so all subsystems observing it can begin
	// cooperative shutdown (Processor, opus reader goroutine, etc.).
	rootCancel()

	// Perform cleanup with a timeout so shutdown cannot hang indefinitely.
	done := make(chan struct{})
	go func() {
		if err := vp.Close(); err != nil {
			logging.Warnw("processor close error", "err", err)
		}
		// If we joined a voice channel, disconnect cleanly first.
		if vc != nil {
			if err := vc.Disconnect(); err != nil {
				logging.Warnw("voice disconnect error", "err", err)
			}
		}
		if err := dg.Close(); err != nil {
			logging.Warnw("discord session close error", "err", err)
		}
		for _, client := range mcpClients {
			if err := client.Close(); err != nil {
				logging.Warnw("mcp client close error", "err", err)
			}
		}
		close(done)
	}()

	select {
	case <-done:
		// normal shutdown finished
	case <-time.After(10 * time.Second):
		logging.Warnw("shutdown timed out after 10s; forcing exit")
	}
	// shutdown complete
}
