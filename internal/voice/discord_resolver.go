package voice

import (
	"sync"
	"time"

	"github.com/bwmarrin/discordgo"
)

type discordResolver struct {
	s  *discordgo.Session
	mu sync.Mutex
	// simple caches for users/guilds/channels: id -> (value, expiry)
	userCache    map[string]cacheEntry
	guildCache   map[string]cacheEntry
	channelCache map[string]cacheEntry
}

type cacheEntry struct {
	val    string
	expiry time.Time
}

func NewDiscordResolver(s *discordgo.Session) *discordResolver {
	return &discordResolver{
		s:            s,
		userCache:    make(map[string]cacheEntry),
		guildCache:   make(map[string]cacheEntry),
		channelCache: make(map[string]cacheEntry),
	}
}

// cacheTTL controls how long a cached name is valid.
var cacheTTL = 5 * time.Minute

func (d *discordResolver) lookupCache(m map[string]cacheEntry, id string) (string, bool) {
	if id == "" {
		return "", false
	}
	if e, ok := m[id]; ok {
		if time.Now().Before(e.expiry) {
			return e.val, true
		}
		delete(m, id)
	}
	return "", false
}

func (d *discordResolver) setCache(m map[string]cacheEntry, id, val string) {
	m[id] = cacheEntry{val: val, expiry: time.Now().Add(cacheTTL)}
}

func (d *discordResolver) UserName(userID string) string {
	if d.s == nil || userID == "" {
		return ""
	}
	d.mu.Lock()
	if v, ok := d.lookupCache(d.userCache, userID); ok {
		d.mu.Unlock()
		return v
	}
	d.mu.Unlock()
	if u, err := d.s.User(userID); err == nil && u != nil {
		name := u.Username
		d.mu.Lock()
		d.setCache(d.userCache, userID, name)
		d.mu.Unlock()
		return name
	}
	return ""
}

func (d *discordResolver) GuildName(guildID string) string {
	if d.s == nil || guildID == "" {
		return ""
	}
	d.mu.Lock()
	if v, ok := d.lookupCache(d.guildCache, guildID); ok {
		d.mu.Unlock()
		return v
	}
	d.mu.Unlock()
	if d.s.State != nil {
		if g, err := d.s.State.Guild(guildID); err == nil && g != nil {
			name := g.Name
			d.mu.Lock()
			d.setCache(d.guildCache, guildID, name)
			d.mu.Unlock()
			return name
		}
	}
	if g, err := d.s.Guild(guildID); err == nil && g != nil {
		name := g.Name
		d.mu.Lock()
		d.setCache(d.guildCache, guildID, name)
		d.mu.Unlock()
		return name
	}
	return ""
}

func (d *discordResolver) ChannelName(channelID string) string {
	if d.s == nil || channelID == "" {
		return ""
	}
	d.mu.Lock()
	if v, ok := d.lookupCache(d.channelCache, channelID); ok {
		d.mu.Unlock()
		return v
	}
	d.mu.Unlock()
	if d.s.State != nil {
		if c, err := d.s.State.Channel(channelID); err == nil && c != nil {
			name := c.Name
			d.mu.Lock()
			d.setCache(d.channelCache, channelID, name)
			d.mu.Unlock()
			return name
		}
	}
	if c, err := d.s.Channel(channelID); err == nil && c != nil {
		name := c.Name
		d.mu.Lock()
		d.setCache(d.channelCache, channelID, name)
		d.mu.Unlock()
		return name
	}
	return ""
}
