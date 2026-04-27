# Work Lifecycle Vocabulary

## Purpose

This document defines the shared loop-state vocabulary used across:

- Brain signals
- standup outcomes
- PM execution
- execution-result write-back

The sequence is:

`captured -> interpreted -> promoted -> routed -> executing -> written_back -> closed`

## Stage meanings

### `captured`

The system has observed the signal or work item, but it has not yet been meaningfully reviewed.

Typical examples:

- a new Brain signal
- a newly captured source

### `interpreted`

The item has started review or interpretation, but it has not yet become a durable promotion or routed work packet.

Typical examples:

- Brain signal in review
- standup reasoning still being shaped

### `promoted`

The item has crossed out of raw capture and into a durable or action-ready layer, but it is not yet actively routed into an execution lane.

Typical examples:

- reviewed Brain signal
- prepared standup packet
- PM-worthy item not yet queued

### `routed`

The item has a declared downstream destination.

Typical examples:

- Brain signal routed to PM or standup
- PM card queued with an execution owner
- completed standup packet that has created routing targets

### `executing`

Active work is in flight.

Typical examples:

- PM card in progress
- delegated or direct execution actively running

### `written_back`

Execution or interpretation has returned a concrete result, but the item is not fully closed yet.

Typical examples:

- PM card with a latest execution result waiting in review
- result written, but manager/operator decision still pending

### `closed`

The loop is complete for now.

Typical examples:

- ignored Brain signal
- completed PM card
- execution result accepted and card closed

## Rule

“Done” should not mean “some prose artifact exists somewhere.”

It should mean the relevant surface has reached either:

- `written_back`
- or `closed`

and that state should be visible in machine-readable payloads.
