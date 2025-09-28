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

	dg.AddHandler(vp.HandleVoiceState)
	dg.AddHandler(vp.HandleSpeakingUpdate)

	if err := dg.Open(); err != nil {
		log.Fatalf("Open: %v", err)
	}
	defer dg.Close()

	// wait for signal
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	<-stop

	// gracefully stop
	vp.Close()
	dg.Close()
	log.Println("shutdown")
}
