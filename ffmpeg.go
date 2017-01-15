package main

import (
	"bytes"
	"context"
	"os/exec"
	"time"
)

// FFmpeg represents a ffmpeg process
type FFmpeg struct {
	started bool
	// cancel function to be called from Close
	cancel context.CancelFunc
	// indicates if close was called before
	closed bool
	// error returned from Close
	closeError error

	Filename string

	Cmd    *exec.Cmd
	Stdout *bytes.Buffer
	Stderr *bytes.Buffer
}

// Start starts the process
func (ff *FFmpeg) Start() error {
	if ff.started {
		panic("invalid usage of FFmpeg: Start called twice")
	}

	err := ff.Cmd.Start()
	if err != nil {
		return err
	}

	ff.started = true
	return nil
}

// Close waits for the process to complete, see os/exec.Cmd.Wait for
// extended documentation.
func (ff *FFmpeg) Close() error {
	// implement a timeout, we kill the process if waiting
	// takes too long.
	var done = make(chan struct{})
	go func() {
		select {
		case <-time.Tick(time.Second / 4):
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
