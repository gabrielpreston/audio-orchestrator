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
	log.Println("creating voice processor")
	vp, err := voice.NewProcessor()
	if err != nil {
		log.Fatalf("voice.NewProcessor: %v", err)
	}
	log.Println("voice processor created")

	// Register handlers via wrapper functions to ensure discordgo accepts them
	log.Println("registering handlers")
	dg.AddHandler(func(s *discordgo.Session, vs *discordgo.VoiceStateUpdate) {
		log.Printf("event: VoiceStateUpdate: %+v", vs)
		vp.HandleVoiceState(s, vs)
	})
	dg.AddHandler(func(s *discordgo.Session, su *discordgo.VoiceSpeakingUpdate) {
		log.Printf("event: VoiceSpeakingUpdate: SSRC=%d User=%s Speaking=%d", su.SSRC, su.UserID, su.Speaking)
		vp.HandleSpeakingUpdate(s, su)
	})
	log.Println("handlers registered")

	log.Println("opening discord session")
	if err := dg.Open(); err != nil {
		log.Fatalf("Open: %v", err)
	}
	log.Printf("connected: user=%s#%s id=%s", dg.State.User.Username, dg.State.User.Discriminator, dg.State.User.ID)

	// join voice channel if configured
	var vc *discordgo.VoiceConnection
	gid := os.Getenv("GUILD_ID")
	cid := os.Getenv("VOICE_CHANNEL_ID")
	if gid != "" && cid != "" {
		// NOTE: ensure we do NOT self-deafen; we want to receive audio
		log.Printf("attempting ChannelVoiceJoin guild=%s channel=%s", gid, cid)
		vconn, err := dg.ChannelVoiceJoin(gid, cid, false, false)
		if err != nil {
			log.Printf("ChannelVoiceJoin error: %v", err)
		} else {
			vc = vconn
			log.Printf("joined voice channel %s in guild %s", cid, gid)
			// start a goroutine to receive opus packets from the VoiceConnection
			if vc.OpusRecv == nil {
				log.Println("voice connection OpusRecv channel is nil; incoming audio will not be received")
			} else {
				go func() {
					log.Println("opus receive loop: started")
					for pkt := range vc.OpusRecv {
						if pkt == nil {
							continue
						}
						log.Printf("opus receive loop: pkt SSRC=%d seq=%d ts=%d opus_bytes=%d", pkt.SSRC, pkt.Sequence, pkt.Timestamp, len(pkt.Opus))
						// hand off to processor
						vp.ProcessOpusFrame(pkt.SSRC, pkt.Opus)
					}
					log.Println("opus receive loop: ended")
				}()
			}
		}
	} else {
		log.Println("GUILD_ID or VOICE_CHANNEL_ID not set; not auto-joining voice channel")
	}

	// wait for signal
	log.Println("entering main wait; press Ctrl+C to shutdown")
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	sig := <-stop
	log.Printf("received signal: %v", sig)

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
