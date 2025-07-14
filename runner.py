import sys
import importlib


def main():
    if len(sys.argv) < 2:
        print("Usage: python runner.py <script> [args...]")
        sys.exit(1)

    script_name = sys.argv[1]
    script_args = sys.argv[2:]

    if script_name == "initialize":
        # Dynamically import the initialize module
        initialize = importlib.import_module("initialize")
        # Call the run function with positional arguments
        initialize.run(*script_args)
    else:
        print(f"Unknown script: {script_name}")
        sys.exit(1)


if __name__ == "__main__":
    main() 