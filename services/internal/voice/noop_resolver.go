package voice

// NoopResolver implements NameResolver and always returns empty names.
// Useful for tests or when REST lookups are disabled.
type NoopResolver struct{}

func NewNoopResolver() *NoopResolver { return &NoopResolver{} }

func (n *NoopResolver) UserName(userID string) string       { return "" }
func (n *NoopResolver) GuildName(guildID string) string     { return "" }
func (n *NoopResolver) ChannelName(channelID string) string { return "" }
