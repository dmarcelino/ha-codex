import re
import unittest
from pathlib import Path


CODEX_DIR = Path(__file__).resolve().parents[1]
PATCH = CODEX_DIR / "ttyd-mobile-keys/ttyd-1.7.7-mobile-keys.patch"


def added_lines(patch: str) -> str:
    return "\n".join(line[1:] for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++"))


def method_body(source: str, name: str) -> str:
    match = re.search(rf"private {name}\(\) \{{(.*?)\n    \}}\n", source, re.S)
    assert match, f"{name} not found in canonical patch"
    return match.group(1)


class DesktopSelectionTests(unittest.TestCase):
    def setUp(self):
        self.source = added_lines(PATCH.read_text(encoding="utf-8"))

    def test_desktop_selection_is_decided_per_gesture_from_pointer_type(self):
        # When a touchscreen laptop reports touch points and a coarse primary
        # pointer, then plain mouse left-drag must still be forced selection:
        # the decision comes from the gesture's pointer type, not device sniffing.
        body = method_body(self.source, "installDesktopSelectionPreference")

        self.assertNotIn("maxTouchPoints", body)
        self.assertNotIn("matchMedia", body)
        self.assertNotIn("pointer: coarse", body)
        self.assertNotIn("Android|iPhone|iPad|iPod", body)
        self.assertNotIn("userAgentData", body)

        self.assertIn("element.addEventListener('pointerdown', onPointerDown, true);", body)
        self.assertIn("this.lastPointerType = (event as PointerEvent).pointerType;", body)
        self.assertIn("if (this.lastPointerType === 'touch') return;", body)
        self.assertIn("element.removeEventListener('pointerdown', onPointerDown, true);", body)

        # Accepted desktop behavior stays intact: Alt keeps application mouse
        # handling and plain left-drag is decorated as xterm's forced selection.
        self.assertIn("if (mouseEvent.button !== 0 || mouseEvent.altKey) return;", body)
        self.assertIn("Object.defineProperty(event, 'shiftKey'", body)
        self.assertIn("private lastPointerType?: string;", self.source)

    def test_ctrl_shift_c_copies_selection_instead_of_opening_devtools(self):
        # When Ctrl+Shift+C is pressed with a terminal selection, then the
        # selection is copied and the event is consumed so Chrome does not
        # open DevTools; without a selection the key passes through untouched.
        body = method_body(self.source, "installCopyShortcut")

        self.assertIn("this.installCopyShortcut();", self.source)
        self.assertIn("this.terminal.attachCustomKeyEventHandler(", body)
        self.assertIn("if (event.type !== 'keydown') return true;", body)
        self.assertIn("if (!event.ctrlKey || !event.shiftKey || event.altKey || event.metaKey) return true;", body)
        self.assertIn("if (event.code !== 'KeyC') return true;", body)
        self.assertIn("if (!this.terminal.hasSelection()) return true;", body)
        self.assertIn("event.preventDefault();", body)
        self.assertIn("document.execCommand('copy');", body)
        self.assertIn("return false;", body)
        # Plain Ctrl+C must keep reaching the terminal as an interrupt.
        self.assertNotIn("event.code === 'KeyC' && event.ctrlKey && !event.shiftKey", body)


if __name__ == "__main__":
    unittest.main()
