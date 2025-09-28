//go:build opus
// +build opus

package main

import (
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/bwmarrin/discordgo"
	"github.com/discord-voice-lab/internal/voice"
)

func main() {
	token := os.Getenv("DISCORD_BOT_TOKEN")
	if token == "" {
		log.Fatal("DISCORD_BOT_TOKEN required")
	}
	dg, err := discordgo.New("Bot " + token)
	if err != nil {
		log.Fatalf("discordgo.New: %v", err)
	}

	// Create voice processor
	vp, err := voice.NewProcessor()
	if err != nil {
		log.Fatalf("voice.NewProcessor: %v", err)
	}

	// Register handlers via wrapper functions to ensure discordgo accepts them
	dg.AddHandler(func(s *discordgo.Session, vs *discordgo.VoiceStateUpdate) {
		vp.HandleVoiceState(s, vs)
	})
	dg.AddHandler(func(s *discordgo.Session, su *discordgo.VoiceSpeakingUpdate) {
		vp.HandleSpeakingUpdate(s, su)
	})

	if err := dg.Open(); err != nil {
		log.Fatalf("Open: %v", err)
	}
	log.Printf("Connected to Discord as %s#%s (ID: %s)", dg.State.User.Username, dg.State.User.Discriminator, dg.State.User.ID)

	// join voice channel if configured
	var vc *discordgo.VoiceConnection
	gid := os.Getenv("GUILD_ID")
	cid := os.Getenv("VOICE_CHANNEL_ID")
	if gid != "" && cid != "" {
		// NOTE: ensure we do NOT self-deafen; we want to receive audio
		vconn, err := dg.ChannelVoiceJoin(gid, cid, false, false)
		if err != nil {
			log.Printf("ChannelVoiceJoin error: %v", err)
		} else {
			vc = vconn
			log.Printf("Joined voice channel %s in guild %s", cid, gid)
		}
	} else {
		log.Println("GUILD_ID or VOICE_CHANNEL_ID not set; not auto-joining voice channel")
	}

	// wait for signal
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	<-stop

	// gracefully stop: leave voice, close processor, close session
	log.Println("shutting down: leaving voice, closing processor and session")
	if vc != nil {
		vc.Close()
		log.Printf("left voice channel %s in guild %s", cid, gid)
	}
	if err := vp.Close(); err != nil {
		log.Printf("processor close error: %v", err)
	}
	if err := dg.Close(); err != nil {
		log.Printf("discord session close error: %v", err)
	}
	log.Println("shutdown complete")
}
