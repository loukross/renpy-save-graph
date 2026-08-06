from renpy_save_graph.server import _main
import sys

if __name__ == "__main__":
    try:
        raise SystemExit(_main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(0)
