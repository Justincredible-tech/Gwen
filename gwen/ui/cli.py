"""Command-line interface for Gwen.

This is the Phase 1 user interface — a simple async input loop that
reads user input, passes it through the Orchestrator, and displays
the response. It will be replaced by a richer TUI or GUI in later phases.
"""

import asyncio
import logging
import sys

from gwen.core.orchestrator import Orchestrator


# Configure logging to stderr so it does not interfere with conversation
# displayed on stdout.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Run the Gwen CLI conversation loop.

    1. Creates and starts the Orchestrator.
    2. Prints a welcome message.
    3. Enters an input loop: read user input, process, display response.
    4. On "quit" or "exit": shuts down cleanly.
    5. On Ctrl+C: shuts down cleanly.
    6. On unexpected error: logs the error and shuts down.
    """
    orchestrator = Orchestrator()

    try:
        print("\n  Starting Gwen...\n")
        await orchestrator.startup()
        print("  ========================================")
        print("  Gwen is ready. Type 'quit' or 'exit' to end.")
        print("  ========================================\n")

    except FileNotFoundError as e:
        print(f"\n  Error: {e}\n", file=sys.stderr)
        print("  Could not start Gwen. Check that all files are in place.", file=sys.stderr)
        return
    except Exception as e:
        print(f"\n  Error during startup: {e}\n", file=sys.stderr)
        logger.exception("Startup failed")
        return

    try:
        while True:
            # Read user input without blocking the async event loop
            try:
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("You: ")
                )
            except EOFError:
                print("\n[Input stream ended. Shutting down.]")
                break

            # Check for quit commands
            stripped = user_input.strip().lower()
            if stripped in ("quit", "exit", "q"):
                print("\n  Gwen: Take care. Talk soon.\n")
                break

            # Skip empty input
            if not stripped:
                continue

            # Process message
            try:
                response = await orchestrator.process_message(user_input)
                print(f"\nGwen: {response}\n")
            except Exception as e:
                logger.exception("Error processing message")
                print(
                    f"\n  [Error: {e}. The message could not be processed.]\n",
                    file=sys.stderr,
                )

    except KeyboardInterrupt:
        print("\n\n  [Interrupted. Shutting down.]\n")

    finally:
        await orchestrator.shutdown()
        print("  Session ended. Goodbye.\n")
