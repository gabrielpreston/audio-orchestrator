package logging

import (
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
