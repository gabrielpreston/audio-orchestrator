package logging

import (
	"context"
	"os"
	"strings"
	"sync"

	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
)

var (
	sugar *zap.SugaredLogger
	once  sync.Once
)

// Logger is the canonical structured logging interface used by the project.
// Keep it small and focused on key/value structured events.
type Logger interface {
	Infow(msg string, keysAndValues ...interface{})
	Debugw(msg string, keysAndValues ...interface{})
	Warnw(msg string, keysAndValues ...interface{})
	Errorw(msg string, keysAndValues ...interface{})
	Fatalw(msg string, keysAndValues ...interface{})
	Sync() error
}

// noopLogger is a tiny, extremely cheap logger that does nothing. We use
// this as the default to make logging calls safe before Init is invoked.
type noopLogger struct{}

func (n noopLogger) Infow(msg string, keysAndValues ...interface{})  {}
func (n noopLogger) Debugw(msg string, keysAndValues ...interface{}) {}
func (n noopLogger) Warnw(msg string, keysAndValues ...interface{})  {}
func (n noopLogger) Errorw(msg string, keysAndValues ...interface{}) {}
func (n noopLogger) Fatalw(msg string, keysAndValues ...interface{}) {}
func (n noopLogger) Sync() error                                     { return nil }

// current holds the active Logger. Initialize to noopLogger so calls are
// always safe even if Init() hasn't been called yet.
var current Logger = noopLogger{}

// Init initializes the global sugared logger based on LOG_LEVEL and
// redirects the standard library logger into zap. Callers must invoke this
// in main() to enable structured logging. It's safe to call multiple times.
func Init() *zap.SugaredLogger {
	once.Do(func() {
		level := strings.ToLower(os.Getenv("LOG_LEVEL"))
		// Configure JSON encoder with ISO8601 time and canonical field names
		cfg := zap.Config{
			Encoding:         "json",
			EncoderConfig:    zap.NewProductionEncoderConfig(),
			OutputPaths:      []string{"stdout"},
			ErrorOutputPaths: []string{"stderr"},
		}
		// Use ISO8601 time format for easier ingestion
		cfg.EncoderConfig.TimeKey = "ts"
		cfg.EncoderConfig.EncodeTime = zapcore.ISO8601TimeEncoder
		// Include caller and stacktrace for error-level logs
		cfg.EncoderConfig.CallerKey = "caller"
		// Set level from LOG_LEVEL env
		lvl := zap.InfoLevel
		if level == "debug" {
			lvl = zap.DebugLevel
		} else if level == "warn" {
			lvl = zap.WarnLevel
		} else if level == "error" {
			lvl = zap.ErrorLevel
		}
		cfg.Level = zap.NewAtomicLevelAt(lvl)

		logger, _ := cfg.Build(zap.AddCaller(), zap.AddStacktrace(zap.ErrorLevel))
		// Redirect standard library logs into zap so all logs are unified.
		_ = zap.RedirectStdLog(logger)
		sugar = logger.Sugar()
		current = sugar
	})
	return sugar
}

// Sugar returns the initialized sugared logger (may be nil if Init not called).
func Sugar() *zap.SugaredLogger { return sugar }

// SetLogger replaces the package-level logger. Pass nil to reset to the
// sugared logger initialized by Init() (if any). Useful for tests.
func SetLogger(l Logger) {
	if l == nil {
		if sugar != nil {
			current = sugar
		} else {
			current = noopLogger{}
		}
	} else {
		current = l
	}
}

// GetLogger returns the current Logger.
func GetLogger() Logger { return current }

// Infow forwards to current logger if present.
func Infow(msg string, keysAndValues ...interface{}) {
	if current != nil {
		current.Infow(msg, keysAndValues...)
	}
}
func Debugw(msg string, keysAndValues ...interface{}) {
	if current != nil {
		current.Debugw(msg, keysAndValues...)
	}
}
func Warnw(msg string, keysAndValues ...interface{}) {
	if current != nil {
		current.Warnw(msg, keysAndValues...)
	}
}
func Errorw(msg string, keysAndValues ...interface{}) {
	if current != nil {
		current.Errorw(msg, keysAndValues...)
	}
}
func Fatalw(msg string, keysAndValues ...interface{}) {
	if current != nil {
		current.Fatalw(msg, keysAndValues...)
	}
}

// FatalExitf logs a fatal message and exits the process with code 1. Tests
// can replace the logger via SetLogger to avoid process exit during test runs.
func FatalExitf(msg string, keysAndValues ...interface{}) {
	if current != nil {
		current.Fatalw(msg, keysAndValues...)
	}
	os.Exit(1)
}

// Sync flushes any buffered logs.
func Sync() error {
	if current != nil {
		return current.Sync()
	}
	return nil
}

// Context helpers: attach small canonical key/value slices to context.Context
// so they can be merged into log calls downstream.
type ctxKeyType struct{}

// WithFields returns a context containing the provided key/value pairs. If
// the context already contains fields they are appended (preserving order).
func WithFields(ctx context.Context, kv ...interface{}) context.Context {
	if len(kv) == 0 {
		return ctx
	}
	prev, _ := ctx.Value(ctxKeyType{}).([]interface{})
	merged := make([]interface{}, 0, len(prev)+len(kv))
	merged = append(merged, prev...)
	merged = append(merged, kv...)
	return context.WithValue(ctx, ctxKeyType{}, merged)
}

// FromContext returns any fields previously attached with WithFields.
func FromContext(ctx context.Context) []interface{} {
	if ctx == nil {
		return nil
	}
	if v, ok := ctx.Value(ctxKeyType{}).([]interface{}); ok {
		return v
	}
	return nil
}

// InfowCtx merges fields from ctx and the provided kv and emits a structured
// log entry via the current logger.
func InfowCtx(ctx context.Context, msg string, kv ...interface{}) {
	ctxFields := FromContext(ctx)
	if len(ctxFields) == 0 && len(kv) == 0 {
		Infow(msg)
		return
	}
	if len(ctxFields) == 0 {
		Infow(msg, kv...)
		return
	}
	merged := make([]interface{}, 0, len(ctxFields)+len(kv))
	merged = append(merged, ctxFields...)
	merged = append(merged, kv...)
	Infow(msg, merged...)
}

// Helper functions that return sugared logger key/value pairs for common
// Discord entities. Use canonical dot-separated keys to make queries easier
// in downstream log analysis tooling.
func UserFields(userID, userName string) []interface{} {
	if userName == "" {
		return []interface{}{"user.id", userID}
	}
	return []interface{}{"user.id", userID, "user.name", userName}
}

func GuildFields(guildID, guildName string) []interface{} {
	if guildName == "" {
		return []interface{}{"guild.id", guildID}
	}
	return []interface{}{"guild.id", guildID, "guild.name", guildName}
}

func ChannelFields(channelID, channelName string) []interface{} {
	if channelName == "" {
		return []interface{}{"channel.id", channelID}
	}
	return []interface{}{"channel.id", channelID, "channel.name", channelName}
}

// AccumFields returns structured fields useful when logging accumulator state
// for a given SSRC. samples is the number of int16 samples in the accumulator
// and durationMs is the computed duration of those samples in milliseconds.
func AccumFields(ssrc uint32, samples int, durationMs int) []interface{} {
	return []interface{}{"ssrc", ssrc, "samples", samples, "duration_ms", durationMs}
}
