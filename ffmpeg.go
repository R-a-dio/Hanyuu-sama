package ffmpeg

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"os/exec"
)

// ExecutableName is the filename/name of the ffmpeg executable
var ExecutableName = "ffmpeg"

// Arguments is the argument list passed to the ffmpeg executable with
// all occurences of {filename} replaced with the given filename
var Arguments = []string{
	"-hide_banner",
	"-loglevel", "error",
	"-i", "{filename}",
	"-f", "s16le",
	"-acodec", "pcm_s16le",
	"-",
}

// Error represents a ffmpeg error
type Error struct {
}

// Process represents a ffmpeg process
type Process struct {
	started    bool
	closed     bool
	closeError error

	Ctx context.Context

	Filename string

	Cmd    *exec.Cmd
	Stdout io.ReadCloser
	Stderr io.ReadCloser
}

// Start starts the process
func (pr *Process) Start() error {
	if pr.started {
		panic("invalid usage of process: Start called twice")
	}

	err := pr.Cmd.Start()
	if err != nil {
		return err
	}

	pr.started = true
	go pr.handleErrors()
}

// Close waits for the process to complete, see os/exec.Cmd.Wait for
// extended documentation.
func (pr *Process) Close() error {
	if pr.closed {
		return pr.closeError
	}

	pr.closed = true
	pr.closeError = pr.Cmd.Wait()
	return pr.closeError
}

func (pr *Process) handleErrors() {
	s := bufio.NewScanner(pr.Stderr)
	for s.Scan() {
		fmt.Println(s.Text())
	}
}

func (pr *Process) Read(p []byte) (n int, err error) {
	if !pr.started {
		if err = pr.Start(); err != nil {
			return 0, err
		}
	}

	return pr.Stdout.Read(p)
}

// NewProcess prepares a new ffmpeg process for decoding the filename given.
func NewProcess(filename string) (pr *Process, err error) {
	return NewProcessContext(context.Background(), filename)
}

// NewProcessContext prepares a new ffmpeg process for decoding the filename given, while
// supporting the Context interface.
func NewProcessContext(ctx context.Context, filename string) (pr *Process, err error) {
	pr = &Process{Filename: filename, Ctx: ctx}

	// prepare executable arguments
	var args = make([]string, len(Arguments))
	copy(args, Arguments)
	for i, f := range args {
		if f == "{filename}" {
			args[i] = pr.Filename
		}
	}

	// prepare the os/exec command and give us access to output pipes
	pr.Cmd = exec.CommandContext(pr.Ctx, ExecutableName, args...)
	pr.Stdout, err = pr.Cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}

	pr.Stderr, err = pr.Cmd.StderrPipe()
	if err != nil {
		return nil, err
	}

	return pr, nil
}
