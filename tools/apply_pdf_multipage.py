#!/usr/bin/env python3
"""Patch Main.py with multipage PDF support. Run from the project folder."""
from pathlib import Path
import shutil
import sys

p = Path("Main.py")
if not p.exists():
    print("Main.py not found in current folder")
    sys.exit(1)

s = p.read_text(encoding="utf-8")
if "pdf_multipage" in s and "apply_pdf_multipage" in s:
    print("Already patched")
    sys.exit(0)

replacements = [
(
'''        self.pdf_path = ""
        self.pdf_page = 0
        self.pdf_zoom_mode = "Fit"
''',
'''        self.pdf_path = ""
        self.pdf_page = 0
        self.pdf_zoom_mode = "Fit"
        self.pdf_multipage = False
'''
),
(
'''        "pdf_page": cue.pdf_page,
        "pdf_zoom_mode": cue.pdf_zoom_mode,
''',
'''        "pdf_page": cue.pdf_page,
        "pdf_zoom_mode": cue.pdf_zoom_mode,
        "pdf_multipage": getattr(cue, "pdf_multipage", False),
'''
),
(
'''    cue.pdf_page = data.get("pdf_page", 0)
    cue.pdf_zoom_mode = data.get("pdf_zoom_mode", "Fit")
''',
'''    cue.pdf_page = data.get("pdf_page", 0)
    cue.pdf_zoom_mode = data.get("pdf_zoom_mode", "Fit")
    cue.pdf_multipage = data.get("pdf_multipage", False)
'''
),
(
'''        self.view.setDocument(self.doc)
        self.view.setPageMode(QPdfView.PageMode.SinglePage)
        self.view.setZoomMode(QPdfView.ZoomMode.FitInView)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.current_cue = None
''',
'''        self.view.setDocument(self.doc)
        self.view.setPageMode(QPdfView.PageMode.SinglePage)
        self.view.setZoomMode(QPdfView.ZoomMode.FitInView)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.current_cue = None
'''
),
(
'''        self.doc.load(cue.pdf_path)
        count = self.doc.pageCount()
        if count <= 0:
            return
        page = max(0, min(int(cue.pdf_page), count - 1))
        self.view.pageNavigator().jump(page, QPoint(0, 0))
''',
'''        self.doc.load(cue.pdf_path)
        count = self.doc.pageCount()
        if count <= 0:
            return

        if getattr(cue, "pdf_multipage", False):
            self.view.setPageMode(QPdfView.PageMode.MultiPage)
        else:
            self.view.setPageMode(QPdfView.PageMode.SinglePage)

        page = max(0, min(int(cue.pdf_page), count - 1))
        self.view.pageNavigator().jump(page, QPoint(0, 0))
'''
),
(
'''        self.show()
        self.raise_()
        self.activateWindow()

    def close_window(self):
        if self.doc:
            self.doc.close()
        super().close_window()
''',
'''        self.show()
        self.raise_()
        self.activateWindow()

    def _goto_page(self, page):
        if not self.doc or self.doc.pageCount() <= 0 or not self.current_cue:
            return
        page = max(0, min(int(page), self.doc.pageCount() - 1))
        self.current_cue.pdf_page = page
        try:
            self.view.pageNavigator().jump(page, QPoint(0, 0))
        except Exception:
            pass

    def keyPressEvent(self, event):
        key = event.key()
        if self.doc and key in (Qt.Key.Key_Right, Qt.Key.Key_PageDown):
            if self.current_cue:
                self._goto_page(self.current_cue.pdf_page + 1)
            event.accept()
            return
        if self.doc and key in (Qt.Key.Key_Left, Qt.Key.Key_PageUp, Qt.Key.Key_Backspace):
            if self.current_cue:
                self._goto_page(self.current_cue.pdf_page - 1)
            event.accept()
            return
        super().keyPressEvent(event)

    def close_window(self):
        if self.doc:
            self.doc.close()
        super().close_window()
'''
),
(
'''        page_row.addWidget(self.pdf_zoom_combo)
        page_row.addStretch()
        playout.addLayout(page_row)
        if not HAS_PDF:
''',
'''        page_row.addWidget(self.pdf_zoom_combo)
        page_row.addStretch()
        playout.addLayout(page_row)
        self.pdf_multipage_cb = QCheckBox("Show all pages (scroll)")
        self.pdf_multipage_cb.toggled.connect(self.apply_pdf_multipage)
        playout.addWidget(self.pdf_multipage_cb)
        pdf_nav = QHBoxLayout()
        prev_btn = QPushButton("◀ Prev page")
        prev_btn.clicked.connect(self.pdf_prev_page)
        next_btn = QPushButton("Next page ▶")
        next_btn.clicked.connect(self.pdf_next_page)
        pdf_nav.addWidget(prev_btn)
        pdf_nav.addWidget(next_btn)
        playout.addLayout(pdf_nav)
        if not HAS_PDF:
'''
),
(
'''        if is_pdf:
            self.pdf_path_edit.setText(cue.pdf_path or "")
            self.pdf_page_spin.blockSignals(True)
            self.pdf_page_spin.setValue(cue.pdf_page + 1)
            self.pdf_page_spin.blockSignals(False)
            self.pdf_zoom_combo.blockSignals(True)
            self.pdf_zoom_combo.setCurrentText(cue.pdf_zoom_mode)
            self.pdf_zoom_combo.blockSignals(False)
            self.file_label.setText(cue.pdf_path or "-")
''',
'''        if is_pdf:
            self.pdf_path_edit.setText(cue.pdf_path or "")
            self.pdf_page_spin.blockSignals(True)
            self.pdf_page_spin.setValue(cue.pdf_page + 1)
            self.pdf_page_spin.blockSignals(False)
            self.pdf_zoom_combo.blockSignals(True)
            self.pdf_zoom_combo.setCurrentText(cue.pdf_zoom_mode)
            self.pdf_zoom_combo.blockSignals(False)
            self.pdf_multipage_cb.blockSignals(True)
            self.pdf_multipage_cb.setChecked(getattr(cue, "pdf_multipage", False))
            self.pdf_multipage_cb.blockSignals(False)
            self.file_label.setText(cue.pdf_path or "-")
'''
),
(
'''    def apply_pdf_page(self, value):
        cue = self.get_current_cue()
        if cue and cue.cue_type == "PDF":
            cue.pdf_page = max(0, value - 1)

    def apply_pdf_zoom(self, mode):
        cue = self.get_current_cue()
        if cue and cue.cue_type == "PDF":
            cue.pdf_zoom_mode = mode
''',
'''    def apply_pdf_page(self, value):
        cue = self.get_current_cue()
        if cue and cue.cue_type == "PDF":
            cue.pdf_page = max(0, value - 1)
            win = self.pdf_windows.get(cue.id)
            if win and win.current_cue is cue:
                win._goto_page(cue.pdf_page)

    def apply_pdf_zoom(self, mode):
        cue = self.get_current_cue()
        if cue and cue.cue_type == "PDF":
            cue.pdf_zoom_mode = mode
            win = self.pdf_windows.get(cue.id)
            if win and win.current_cue is cue:
                win.show_pdf(cue, self.get_screen_by_name(cue.screen_name), self.display_defaults)

    def apply_pdf_multipage(self, checked):
        cue = self.get_current_cue()
        if cue and cue.cue_type == "PDF":
            cue.pdf_multipage = bool(checked)
            win = self.pdf_windows.get(cue.id)
            if win and win.current_cue is cue:
                win.show_pdf(cue, self.get_screen_by_name(cue.screen_name), self.display_defaults)

    def pdf_prev_page(self):
        cue = self.get_current_cue()
        if cue and cue.cue_type == "PDF":
            self.pdf_page_spin.setValue(max(1, cue.pdf_page))

    def pdf_next_page(self):
        cue = self.get_current_cue()
        if cue and cue.cue_type == "PDF":
            self.pdf_page_spin.setValue(cue.pdf_page + 2)
'''
),
]

for i, (old, new) in enumerate(replacements, 1):
    if old not in s:
        print(f"Block {i} not found — abort (file may already differ)")
        sys.exit(1)
    s = s.replace(old, new, 1)

shutil.copy2(p, "Main.py.bak")
p.write_text(s, encoding="utf-8")
print("OK – multipage PDF patched")
print("Backup: Main.py.bak")
