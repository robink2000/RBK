"""Entry point for the packaged Windows program."""
import multiprocessing

from neuranova.launcher import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
