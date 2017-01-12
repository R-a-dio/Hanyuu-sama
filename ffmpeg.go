package main

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"os/exec"
)

// FFmpegExecutable is the filename/name of the ffmpeg executable
const FFmpegExecutable = "ffmpeg"

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
	Stdout io.ReadCloser
	Stderr io.ReadCloser
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
	go ff.handleErrors()
}

// Close waits for the process to complete, see os/exec.Cmd.Wait for
// extended documentation.
func (ff *FFmpeg) Close() error {
	if ff.closed {
		return ff.closeError
	}

	ff.cancel()
	ff.closed = true
	ff.closeError = ff.Cmd.Wait()
	return ff.closeError
}

func (ff *FFmpeg) handleErrors() {
	s := bufio.NewScanner(ff.Stderr)
	for s.Scan() {
		fmt.Println(s.Text())
	}
}

func (ff *FFmpeg) Read(p []byte) (n int, err error) {
	if !ff.started {
		if err = ff.Start(); err != nil {
			return 0, err
		}
	}

	return ff.Stdout.Read(p)
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
	ff.Cmd = exec.CommandContext(ctx, FFmpegExecutable, args...)
	ff.Stdout, err = ff.Cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}

	ff.Stderr, err = ff.Cmd.StderrPipe()
	if err != nil {
		return nil, err
	}

	return ff, nil
}
