"""Real public WSS/TURN acceptance using only a loopback app backed by mocked providers.

The app must be an isolated remote mock instance reached through an operator's
SSH tunnel. It must advertise hosted LiveKit and blank provider keys. Explicit
--signal-url and --rtc-host allow only that SFU; --require-relay proves TURN.
No production app/demo writes, physical microphone or paid model calls.
"""
from livekit_trial_browser import main


if __name__ == "__main__":
    main(hosted=True)
