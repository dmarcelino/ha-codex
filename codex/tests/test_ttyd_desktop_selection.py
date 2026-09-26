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
    """Behaviour observed with the headless-Chromium harness described in
    codex/ttyd-mobile-keys/README.md (touchscreen-laptop profile: touch points
    present, coarse non-hover primary pointer, mouse input)."""

    def setUp(self):
        self.source = added_lines(PATCH.read_text(encoding="utf-8"))
        self.body = method_body(self.source, "installDesktopSelectionPreference")

    def test_desktop_selection_is_decided_per_gesture_from_pointer_type(self):
        # When a touchscreen laptop reports touch points and a coarse primary
        # pointer, then plain mouse left-drag must still be forced selection:
        # the decision comes from the gesture's pointer type, not device sniffing.
        self.assertNotIn("maxTouchPoints", self.body)
        self.assertNotIn("matchMedia", self.body)
        self.assertNotIn("pointer: coarse", self.body)
        self.assertNotIn("Android|iPhone|iPad|iPod", self.body)
        self.assertNotIn("userAgentData", self.body)

        self.assertIn("element.addEventListener('pointerdown', onPointerDown, true);", self.body)
        self.assertIn("this.lastPointerType = (event as PointerEvent).pointerType;", self.body)
        self.assertIn("if (this.lastPointerType === 'touch') return;", self.body)
        self.assertIn("element.removeEventListener('pointerdown', onPointerDown, true);", self.body)
        self.assertIn("private lastPointerType?: string;", self.source)

    def test_forced_shift_is_applied_only_while_application_mouse_tracking_is_on(self):
        # When the application has not enabled mouse tracking, then a plain
        # left-drag must reach xterm undecorated: forcing Shift there turns the
        # gesture into "extend selection" and selects nothing (0.4.10 regression).
        self.assertIn("if (this.terminal.modes.mouseTrackingMode === 'none') return;", self.body)
        # The gate must run before the gesture is marked active.
        gate = self.body.index("mouseTrackingMode === 'none'")
        active = self.body.index("this.desktopSelectionActive = true;")
        self.assertLess(gate, active)

    def test_accepted_desktop_behavior_is_preserved(self):
        # Alt keeps application mouse handling; plain left-drag is decorated
        # as xterm's forced-selection gesture while tracking is on.
        self.assertIn("if (mouseEvent.button !== 0 || mouseEvent.altKey) return;", self.body)
        self.assertIn("Object.defineProperty(event, 'shiftKey'", self.body)
        # The Ctrl+Shift+C copy shortcut from 0.4.10 is intentionally not part of this release.
        self.assertNotIn("installCopyShortcut", self.source)
        self.assertNotIn("attachCustomKeyEventHandler", self.source)


if __name__ == "__main__":
    unittest.main()
