package voice

// NoopResolver implements NameResolver but returns empty names. Useful for
// tests or when you want to disable REST lookups for user/guild/channel names.
type NoopResolver struct{}

func NewNoopResolver() *NoopResolver { return &NoopResolver{} }

func (n *NoopResolver) UserName(userID string) string       { return "" }
func (n *NoopResolver) GuildName(guildID string) string     { return "" }
func (n *NoopResolver) ChannelName(channelID string) string { return "" }
