package main

import (
	"bytes"
	"context"
	"os/exec"
	"time"
)

// FFmpeg represents a ffmpeg process
//
// FFmpeg decodes audio from the filename given and outputs
// PCM data in 16-bit little-endian stereo format
type FFmpeg struct {
	Filename string
	Cmd      *exec.Cmd
	cancel   context.CancelFunc

	Stdout *bytes.Buffer
	Stderr *bytes.Buffer
}

// Start starts the process
func (ff *FFmpeg) Start() error {
	return ff.Cmd.Start()
}

// Wait waits for the process to complete for the maximum amount of
// time as given by timeout.
func (ff *FFmpeg) Wait(timeout time.Duration) error {
	var done = make(chan struct{})
	go func() {
		select {
		case <-time.Tick(timeout):
			ff.cancel()
		case <-done:
		}
	}()

	err := ff.Cmd.Wait()
	close(done)
	return err
}

// NewFFmpeg prepares a new ffmpeg process for decoding the filename given. The context
// given is passed to os/exec.Cmd
func NewFFmpeg(ctx context.Context, filename string) (ff *FFmpeg, err error) {
	ff = &FFmpeg{Filename: filename}

	// prepare arguments
	args := []string{
		"-hide_banner",
		"-loglevel", "error",
		"-i", filename,
		"-f", "s16le",
		"-ac", "2",
		"-acodec", "pcm_s16le",
		"-",
	}

	ctx, ff.cancel = context.WithCancel(ctx)
	// prepare the os/exec command and give us access to output pipes
	ff.Cmd = exec.CommandContext(ctx, "ffmpeg", args...)
	ff.Stdout = new(bytes.Buffer)
	ff.Cmd.Stdout = ff.Stdout

	// stderr is only used when an error is reported by exec.Cmd
	ff.Stderr = new(bytes.Buffer)
	ff.Cmd.Stderr = ff.Stderr

	return ff, nil
}
