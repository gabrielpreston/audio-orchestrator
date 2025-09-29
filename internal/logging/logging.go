package logging

import (
	"fmt"
	"os"
	"strings"
	"sync"

	"go.uber.org/zap"
)

var (
	sugar *zap.SugaredLogger
	once  sync.Once
)

// Init initializes the global sugared logger based on LOG_LEVEL and redirects
// the standard library logger to zap. It's safe to call multiple times.
func Init() *zap.SugaredLogger {
	once.Do(func() {
		level := strings.ToLower(os.Getenv("LOG_LEVEL"))
		var logger *zap.Logger
		if level == "debug" {
			l, _ := zap.NewDevelopment()
			logger = l
		} else {
			l, _ := zap.NewProduction()
			logger = l
		}
		// Redirect standard library logs into zap so all logs are unified.
		_ = zap.RedirectStdLog(logger)
		sugar = logger.Sugar()
	})
	return sugar
}

// Sugar returns the initialized sugared logger. Call Init first.
func Sugar() *zap.SugaredLogger { return sugar }

func init() {
	Init()
}

// Helper functions that return sugared logger key/value pairs for common
// Discord entities. They include both the numeric ID and an optional human
// readable name. Callers can use them with the SugaredLogger's structured
// logging helpers, for example:
//
//	logging.Sugar().Infow("joined voice", logging.UserFields("12345", "alice")...)
//
// These helpers are intentionally small and return []interface{} so they
// can be spliced into the variadic key/value list that Infow/Debugw expect.
func UserFields(userID, userName string) []interface{} {
	if userName == "" {
		return []interface{}{"user_id", userID}
	}
	return []interface{}{"user_id", userID, "user_name", userName, "user", fmt.Sprintf("%s (%s)", userName, userID)}
}

func GuildFields(guildID, guildName string) []interface{} {
	if guildName == "" {
		return []interface{}{"guild_id", guildID}
	}
	return []interface{}{"guild_id", guildID, "guild_name", guildName, "guild", fmt.Sprintf("%s (%s)", guildName, guildID)}
}

func ChannelFields(channelID, channelName string) []interface{} {
	if channelName == "" {
		return []interface{}{"channel_id", channelID}
	}
	return []interface{}{"channel_id", channelID, "channel_name", channelName, "channel", fmt.Sprintf("%s (%s)", channelName, channelID)}
}
