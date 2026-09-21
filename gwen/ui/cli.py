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
        print("  Commands: /docs  /read  /models  /profile  /model  /help")
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

            # --- Slash commands (model switching) ---
            if stripped.startswith("/"):
                parts = stripped.split()
                cmd = parts[0]

                if cmd == "/models":
                    try:
                        models = await orchestrator.model_manager.list_available_models()
                        print("\n  Installed models:")
                        for m in models:
                            name = m.get("name", "unknown")
                            size_gb = m.get("size", 0) / (1024 ** 3)
                            remote = m.get("remote_model")
                            tag = " (cloud)" if remote else ""
                            print(f"    - {name}{tag} ({size_gb:.1f} GB)")
                        print()
                    except Exception as e:
                        print(f"\n  [Could not list models: {e}]\n", file=sys.stderr)
                    continue

                if cmd == "/profile":
                    mm = orchestrator.model_manager
                    print(f"\n  Hardware profile: {mm.profile.value}")
                    for t in (0, 1, 2):
                        model = mm.get_active_model(t)
                        is_override = t in mm._overrides
                        tag = " [OVERRIDE]" if is_override else ""
                        print(f"    Tier {t}: {model}{tag}")
                    print()
                    continue

                if cmd == "/model":
                    if len(parts) < 2:
                        print("\n  Usage: /model <tier> <name>  or  /model reset <tier>\n")
                        continue
                    mm = orchestrator.model_manager
                    if parts[1] == "reset":
                        if len(parts) < 3:
                            print("\n  Usage: /model reset <tier>\n")
                            continue
                        try:
                            tier = int(parts[2])
                            mm.clear_tier_override(tier)
                            print(f"\n  Tier {tier} restored to default.\n")
                        except Exception as e:
                            print(f"\n  [Error: {e}]\n", file=sys.stderr)
                        continue
                    try:
                        tier = int(parts[1])
                        model_name = parts[2]
                        mm.set_tier_override(tier, model_name)
                        print(f"\n  Tier {tier} set to {model_name}.\n")
                    except Exception as e:
                        print(f"\n  [Error: {e}]\n", file=sys.stderr)
                    continue

                if cmd == "/docs":
                    ds = orchestrator.document_store
                    if ds is None:
                        print("\n  [DocumentStore not initialized]\n")
                        continue
                    docs = ds.list_documents()
                    active = set(ds.active_names())
                    if not docs:
                        print("\n  No documents found. Drop .txt, .md, or .html files into:")
                        print(f"    {ds.docs_path}\n")
                    else:
                        print(f"\n  Documents in {ds.docs_path}:")
                        for name, label, length in docs:
                            tag = " [ACTIVE]" if name in active else ""
                            print(f"    - {name} ({label}, {length} chars){tag}")
                        print()
                    continue

                if cmd == "/read":
                    ds = orchestrator.document_store
                    if ds is None:
                        print("\n  [DocumentStore not initialized]\n")
                        continue
                    if len(parts) < 2:
                        print("\n  Usage: /read <filename>\n")
                        continue
                    filename = parts[1]
                    if ds.set_active(filename):
                        print(f"\n  '{filename}' is now active for this session.\n")
                    else:
                        available = [d[0] for d in ds.list_documents()]
                        print(f"\n  '{filename}' not found. Available:")
                        for name in available:
                            print(f"    - {name}")
                        print()
                    continue

                if cmd == "/clear":
                    ds = orchestrator.document_store
                    if ds is None:
                        print("\n  [DocumentStore not initialized]\n")
                        continue
                    if len(parts) >= 2 and parts[1] == "docs":
                        ds.clear_active()
                        print("\n  All document context cleared.\n")
                    else:
                        print("\n  Usage: /clear docs\n")
                    continue

                if cmd == "/help":
                    print("\n  Commands:")
                    print("    /docs            — List documents in the working directory")
                    print("    /read <filename>    — Activate a document for context")
                    print("    /clear docs      — Clear active document context")
                    print("    /models          — List all installed Ollama models")
                    print("    /profile         — Show current profile and active models")
                    print("    /model <tier> <name>  — Override a tier to any model")
                    print("    /model reset <tier>  — Restore tier to default")
                    print("    /help            — Show this message")
                    print("    quit / exit / q  — End session")
                    print()
                    continue

                print(f"\n  Unknown command: {cmd}. Try /help.\n")
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
