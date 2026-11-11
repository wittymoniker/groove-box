"""seed_editor_support.py — R32: code-editor conveniences for the Seed Script QTextEdit.

* Enter keeps the current line's indentation; a line ending in ``:`` indents one level.
* Backspace at the start of an indented line removes one level (4 spaces).
* Tab inserts 4 spaces; Shift+Tab removes them.
Visual only — nothing here evaluates the seed.
"""
from PyQt6.QtCore import QObject, QEvent, Qt
from PyQt6.QtGui import QTextCursor

INDENT = "    "


class _AutoIndent(QObject):
    def eventFilter(self, obj, ev):
        if ev.type() != QEvent.Type.KeyPress:
            return False
        key = ev.key()
        try:
            cur = obj.textCursor()
        except Exception:
            return False
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (ev.modifiers() & Qt.KeyboardModifier.ControlModifier):
            block = cur.block().text()
            lead = block[: len(block) - len(block.lstrip(" "))]
            stripped = block.rstrip()
            if stripped.endswith(":"):
                lead += INDENT
            elif stripped.startswith(("return", "break", "continue", "pass")) and len(lead) >= len(INDENT):
                lead = lead[: -len(INDENT)]
            cur.insertText("\n" + lead)
            obj.setTextCursor(cur)
            return True
        if key == Qt.Key.Key_Tab:
            if cur.hasSelection():
                self._shift_selection(obj, cur, +1)
            else:
                cur.insertText(INDENT)
            return True
        if key == Qt.Key.Key_Backtab:
            self._shift_selection(obj, cur, -1)
            return True
        if key == Qt.Key.Key_Backspace and not cur.hasSelection():
            block = cur.block().text()
            col = cur.positionInBlock()
            if col > 0 and block[:col].strip() == "" and col % len(INDENT) == 0:
                cur.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, len(INDENT))
                cur.removeSelectedText()
                return True
        return False

    @staticmethod
    def _shift_selection(obj, cur, direction):
        doc = obj.document()
        start, end = cur.selectionStart(), cur.selectionEnd()
        b0 = doc.findBlock(start).blockNumber()
        b1 = doc.findBlock(max(start, end - 1)).blockNumber()
        cur.beginEditBlock()
        for n in range(b0, b1 + 1):
            block = doc.findBlockByNumber(n)
            c = QTextCursor(block)
            if direction > 0:
                c.insertText(INDENT)
            else:
                text = block.text()
                k = min(len(INDENT), len(text) - len(text.lstrip(" ")))
                if k:
                    c.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, k)
                    c.removeSelectedText()
        cur.endEditBlock()


def install_auto_indent(editor):
    f = _AutoIndent(editor)
    editor.installEventFilter(f)
    editor._seed_auto_indent_filter = f
    return f
