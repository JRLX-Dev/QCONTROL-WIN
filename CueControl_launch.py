"""CueControl portable entry point.

Used by CueControl.exe (PyInstaller) and by Run CueControl.bat.
Does not replace Main.py — it bootstraps the USB kit, then starts the app.
"""
import os
import sys

if getattr(sys, "frozen", False):
    HERE = os.path.dirname(os.path.abspath(sys.executable))
else:
    HERE = os.path.dirname(os.path.abspath(__file__))

os.chdir(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import cc_portable  # noqa: E402

cc_portable.bootstrap()


def main():
    from PySide6.QtWidgets import QApplication
    import Main

    cc_portable.install_hooks(Main)

    app = QApplication(sys.argv)
    app.setApplicationName("CueControl")
    app.setOrganizationName("CueControl")
    window = Main.MainWindow()
    window.show()
    try:
        window.statusBar.showMessage(
            "Ready  ·  kit " + cc_portable.kit_root()
        )
    except Exception:
        pass
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
