#!/usr/bin/env bash
# Pass-through entrypoint: compose `command:` selects the runner, e.g.
#   python -m producers.run_producer --all
#   python -m consumers.run_consumer --all
set -e
exec "$@"
