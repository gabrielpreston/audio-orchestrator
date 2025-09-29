package voice

// NameResolver provides human-friendly names for IDs when available.
// Implementations may consult caches or the Discord session state.
type NameResolver interface {
	UserName(userID string) string
	GuildName(guildID string) string
	ChannelName(channelID string) string
}
