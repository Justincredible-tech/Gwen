"""Entry point for `python -m gwen`.

This file is executed when the user runs `python -m gwen` from
the command line. It imports the CLI main function and runs it
using asyncio.
"""

import asyncio

from gwen.ui.cli import main


if __name__ == "__main__":
    asyncio.run(main())
