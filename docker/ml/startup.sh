#!/usr/bin/env bash
# Pass-through: compose CMD selects train (python -m ml.train) or
# serve (python -m ml.serve). Code delivered in the ML phase.
set -e
exec "$@"
