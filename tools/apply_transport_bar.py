#!/usr/bin/env python3
"""Replace the bottom GO/STOP/Fade bar with equal-width rounded buttons."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN = ROOT / "Main.py"
BACKUP = ROOT / "Main.py.transport.bak"

OLD = '''        # GO / STOP bar
        bar = QFrame()
        bar.setFrameShape(QFrame.StyledPanel)
        bar.setFixedHeight(80)
        bl = QHBoxLayout(bar)
        self.go_btn = QPushButton("GO")
        self.go_btn.setStyleSheet(
            "background-color:#00AA00; color:white; font-size:24px; font-weight:bold; padding:15px;"
        )
        self.go_btn.clicked.connect(self.go_pressed)
        self.stop_btn = QPushButton("STOP ALL")
        self.stop_btn.setStyleSheet(
            "background-color:#CC0000; color:white; font-size:18px; padding:12px;"
        )
        self.stop_btn.clicked.connect(self.stop_all)
        self.fade_btn = QPushButton("Fade && Stop")
        self.fade_btn.clicked.connect(self.fade_and_stop)
        bl.addWidget(self.go_btn, 1)
        bl.addWidget(self.stop_btn, 1)
        bl.addWidget(self.fade_btn, 1)
        content.addWidget(bar)'''

NEW = '''        # GO / STOP bar – equal-width rounded controls
        bar = QFrame()
        bar.setObjectName("transportBar")
        bar.setFixedHeight(88)
        bar.setStyleSheet("""
            QFrame#transportBar {
                background-color: #1a1a1a;
                border-top: 1px solid #444;
            }
        """)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(12, 10, 12, 10)
        bl.setSpacing(12)

        btn_base = """
            QPushButton {
                color: white;
                font-size: 18px;
                font-weight: bold;
                border: none;
                border-radius: 12px;
                padding: 14px 20px;
                min-height: 56px;
            }
            QPushButton:pressed {
                padding-top: 16px;
                padding-bottom: 12px;
            }
        """

        self.go_btn = QPushButton("GO")
        self.go_btn.setStyleSheet(btn_base + """
            QPushButton {
                background-color: #00AA00;
            }
            QPushButton:hover {
                background-color: #00CC22;
            }
            QPushButton:pressed {
                background-color: #008800;
            }
        """)
        self.go_btn.clicked.connect(self.go_pressed)

        self.stop_btn = QPushButton("STOP ALL")
        self.stop_btn.setStyleSheet(btn_base + """
            QPushButton {
                background-color: #CC0000;
            }
            QPushButton:hover {
                background-color: #EE2222;
            }
            QPushButton:pressed {
                background-color: #990000;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_all)

        self.fade_btn = QPushButton("Fade & Stop")
        self.fade_btn.setStyleSheet(btn_base + """
            QPushButton {
                background-color: #CC7700;
            }
            QPushButton:hover {
                background-color: #EE9900;
            }
            QPushButton:pressed {
                background-color: #AA5500;
            }
        """)
        self.fade_btn.clicked.connect(self.fade_and_stop)

        bl.addWidget(self.go_btn, 1)
        bl.addWidget(self.stop_btn, 1)
        bl.addWidget(self.fade_btn, 1)
        content.addWidget(bar)'''

def main() -> None:
    if not MAIN.exists():
        raise SystemExit(f"Main.py not found at {MAIN}")
    src = MAIN.read_text(encoding="utf-8")
    if "transportBar" in src and "border-radius: 12px" in src:
        print("Transport bar already looks updated – nothing to do")
        return
    if OLD not in src:
        raise SystemExit(
            "Could not find the old GO/STOP bar block.\n"
            "Paste the bar replacement manually from the last chat message."
        )
    BACKUP.write_text(src, encoding="utf-8")
    MAIN.write_text(src.replace(OLD, NEW, 1), encoding="utf-8")
    print("OK – transport bar updated")
    print(f"  Backup: {BACKUP}")
    print(f"  Updated: {MAIN}")

if __name__ == "__main__":
    main()
