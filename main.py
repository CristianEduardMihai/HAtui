from components.main_tui import MainTUI


def main():
    """Entry point for HAtui application."""
    app = MainTUI()
    app.sub_title = "HAtui"
    app.run()


if __name__ == "__main__":
    main()
