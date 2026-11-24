"""Pure-Python regressions for the v0.9 fail-closed XR rollback latch."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "input_ownership_v080", ROOT / "blender_xr" / "input_ownership_v080.py")
ownership = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ownership)


class Radial:
    def __init__(self, active=False):
        self.active = active
        self.reset_calls = 0
        self.require_release = False

    def reset(self, require_release=False):
        self.reset_calls += 1
        self.require_release = require_release
        self.active = False


def make_session(*, conflict=False, live=True, fail=True, blocked=False):
    radial = Radial()
    session = NS(
        radial=radial,
        _weight_stroke=object() if live else None,
        _xr_gesture=object() if conflict else None,
        transaction=None,
        two_hand_scale=None,
        axis_move=None,
        axis_drag=None,
        grab=None,
        air_grab=None,
        bone_drag=None,
        _xr_curve_pending=None,
        _xr_light_pending=None,
        _xr_paint_pending=None,
        _xr_rearm_required=False,
        _xr_neutral_count=1,
        _xr_rollback_blocked=blocked,
        _xr_validated_controls=((1.0, 1.0), (1.0, 1.0)),
        _xr_validated_poses={"stale": True},
        _xr_validated_sticks=((1.0, 1.0), (1.0, 1.0)),
        status="ACTIVE",
        cancel_calls=0,
    )

    def cancel_work():
        session.cancel_calls += 1
        if fail:
            raise ValueError("external Blender edit changed the rollback target")

    session.cancel_work = cancel_work
    return session


class RollbackLatchTests(unittest.TestCase):
    def assert_latched(self, session):
        self.assertTrue(session._xr_rollback_blocked)
        self.assertTrue(session._xr_rearm_required)
        self.assertEqual(session._xr_neutral_count, 0)
        self.assertIsNone(session._xr_validated_controls)
        self.assertIsNone(session._xr_validated_poses)
        self.assertIsNone(session._xr_validated_sticks)
        self.assertIn("ROLLBACK BLOCKED", session.status)

    def test_session_loss_latches_failed_native_rollback(self):
        session = make_session()
        self.assertTrue(ownership.cancel_session_loss(session))
        self.assert_latched(session)
        self.assertEqual(session.cancel_calls, 1)
        self.assertEqual(session.radial.reset_calls, 1)
        self.assertTrue(session.radial.require_release)

    def test_repeated_session_loss_cannot_clear_or_retry_failed_rollback(self):
        session = make_session()
        ownership.cancel_session_loss(session)
        session._xr_validated_controls = ((0.0, 0.0), (0.0, 0.0))
        session._xr_validated_poses = {"new": True}
        session._xr_validated_sticks = ((0.0, 0.0), (0.0, 0.0))
        self.assertTrue(ownership.cancel_session_loss(session))
        self.assert_latched(session)
        self.assertEqual(session.cancel_calls, 1)
        self.assertEqual(session.radial.reset_calls, 1)

    def test_tracking_loss_preserves_blocked_warning(self):
        session = make_session()
        ownership.cancel_session_loss(session)
        self.assertTrue(ownership.cancel_tracking_loss(session))
        self.assert_latched(session)
        self.assertEqual(
            session.status,
            "XR ROLLBACK BLOCKED / REVIEW SCENE / RESTART XR")

    def test_conflict_rollback_failure_blocks_next_conflict_dispatch(self):
        session = make_session(conflict=True)
        self.assertTrue(ownership.cancel_conflict(session))
        self.assert_latched(session)
        self.assertEqual(session.cancel_calls, 1)
        self.assertEqual(session.radial.reset_calls, 1)
        self.assertTrue(session.radial.require_release)

        # A later tick must stop before trying another rollback or accepting
        # a new overlapping gesture.
        self.assertTrue(ownership.cancel_conflict(session))
        self.assertEqual(session.cancel_calls, 1)
        self.assertEqual(session.radial.reset_calls, 1)
        self.assertIn("ROLLBACK BLOCKED", session.status)

    def test_successful_conflict_rollback_requires_rearm_without_blocking(self):
        session = make_session(conflict=True, fail=False)
        self.assertTrue(ownership.cancel_conflict(session))
        self.assertFalse(session._xr_rollback_blocked)
        self.assertTrue(session._xr_rearm_required)
        self.assertEqual(session._xr_neutral_count, 0)
        self.assertEqual(session.cancel_calls, 1)
        self.assertEqual(session.radial.reset_calls, 1)
        self.assertIn("RELEASE BOTH HANDS", session.status)

    def test_rollback_blocked_session_rejects_mutations_but_allows_diagnostics(self):
        session = make_session(blocked=True, live=False)
        session._xr_rearm_required = True
        ownership.validate_command(session, "FOCUS_INPUT")
        with self.assertRaises(ValueError):
            ownership.validate_command(session, "SAVE")
        with self.assertRaises(ValueError):
            ownership.validate_command(session, "UNDO")


if __name__ == "__main__":
    unittest.main()
