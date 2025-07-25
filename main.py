import os
from components.main_tui import MainTUI

def main():
    """Entry point for HAtui application."""
    try:
        app = MainTUI()
        app.sub_title = "HAtui"
        app.run()
    except Exception as e:
        print(f"Unhandled exception: {e}")
        raise


if __name__ == "__main__":
    main()
