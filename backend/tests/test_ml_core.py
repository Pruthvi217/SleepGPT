"""Core ML + persistence tests (no web framework needed). Run: python -m pytest backend/tests -v
These prove the code runs and is internally consistent. They do NOT prove clinical accuracy."""
import os, sqlite3, unittest
from pathlib import Path
import numpy as np
from tests import conftest  # noqa: F401  (sets env + isolated stores)
from ml import config as C, service, ubidots, db
from ml.events import aggregate_events, estimated_ahi
from ml.pipeline import parse_csv, run_pipeline
from ml.preprocessing import SpO2ValidationError, clean_series, make_windows, normalise, resample_8hz
from ml.somnnet import SomnNet, _conv1d_same, _read_weights
from utils import storage
from utils.tokens import create_token, verify_token

DATA = Path(__file__).parent / "data" / "synthetic_spo2.csv"
WEIGHTS = C.load_settings().weights_path


def synth(n=1800, step=1.0, seed=3):
    rng = np.random.default_rng(seed)
    t = 1.79e9 + np.arange(n) * step
    v = 96 + rng.normal(0, .3, n)
    for s in range(300, n - 60, 240):
        v[s:s + 25] -= 6
    return t, np.clip(v, 70, 100)


def new_patient(name="Test"):
    from utils.patient_id import generate_patient_id
    pid = generate_patient_id(); storage.create_patient(pid, name); return pid


class ModelTests(unittest.TestCase):
    def test_weights_load_and_are_binary(self):
        w = _read_weights(WEIGHTS)
        for k in ("conv1/kernel", "conv2/kernel", "conv3/kernel", "dense1/kernel"):
            self.assertEqual(set(np.unique(w[k])), {-1.0, 1.0}, k)
        self.assertEqual(w["dense1/kernel"].shape, (660, 2))
        SomnNet(WEIGHTS)

    def test_wrong_weights_file_rejected(self):
        with self.assertRaises(Exception):
            SomnNet(Path(__file__))

    def test_window_shape_enforced(self):
        m = SomnNet(WEIGHTS)
        self.assertEqual(C.WINDOW_SAMPLES, 88); self.assertEqual(C.SAMPLE_RATE_HZ, 8); self.assertEqual(C.WINDOW_SECONDS, 11)
        for bad in (np.zeros((2, 87)), np.zeros((2, 89)), np.zeros((88,))):
            with self.assertRaises(ValueError):
                m.predict_proba(bad)

    def test_inference_valid_probabilities_deterministic(self):
        m = SomnNet(WEIGHTS); x = np.random.default_rng(0).normal(size=(16, 88))
        p = m.predict_proba(x)
        self.assertEqual(p.shape, (16, 2)); np.testing.assert_allclose(p.sum(1), 1, atol=1e-5)
        np.testing.assert_array_equal(p, m.predict_proba(x))
        np.testing.assert_allclose(p[:3], m.predict_proba(x[:3]), atol=1e-6)   # batch-independent

    def test_conv_matches_naive_reference(self):
        rng = np.random.default_rng(1)
        for ks in (25, 10, 15):
            x = rng.normal(size=(2, 44, 3)); k = rng.choice([-1., 1.], size=(ks, 3, 4))
            total = ks - 1; left = total // 2
            xp = np.pad(x, ((0, 0), (left, total - left), (0, 0)))
            ref = np.zeros((2, 44, 4))
            for n in range(2):
                for i in range(44):
                    for o in range(4):
                        ref[n, i, o] = sum(xp[n, i + j, c] * k[j, c, o] for j in range(ks) for c in range(3))
            np.testing.assert_allclose(_conv1d_same(x, k), ref, atol=1e-9)


class PreprocessingTests(unittest.TestCase):
    def test_windows_88_samples_and_count(self):
        t, v = synth(); s = C.load_settings()
        cs = clean_series(t, v, s); g, y, ok = resample_8hz(cs, s.max_gap_s)
        starts, wins, okw = make_windows(g, y, ok, 88)
        self.assertEqual(wins.shape[1], 88); self.assertEqual(len(starts), len(y) // 88); self.assertTrue(okw.all())

    def test_too_short_for_a_window(self):
        with self.assertRaises(SpO2ValidationError):
            make_windows(np.arange(50), np.zeros(50, np.float32), np.ones(50, bool), 88)

    def test_window_normalisation_and_global_config(self):
        w = np.random.default_rng(0).normal(95, 3, (4, 88)).astype(np.float32)
        z = normalise(w, C.load_settings())
        np.testing.assert_allclose(z.mean(1), 0, atol=1e-4); np.testing.assert_allclose(z.std(1), 1, atol=1e-3)
        os.environ.update(SOMNNET_NORMALIZATION_MODE="global", SOMNNET_TRAIN_MEAN="95", SOMNNET_TRAIN_STD="2")
        try:
            s = C.load_settings(); np.testing.assert_allclose(normalise(w, s), (w - 95) / 2)
        finally:
            for k in ("SOMNNET_NORMALIZATION_MODE", "SOMNNET_TRAIN_MEAN", "SOMNNET_TRAIN_STD"): os.environ.pop(k)

    def test_global_mode_requires_constants(self):
        os.environ["SOMNNET_NORMALIZATION_MODE"] = "global"
        try:
            with self.assertRaises(ValueError): C.load_settings()
        finally:
            os.environ.pop("SOMNNET_NORMALIZATION_MODE")

    def test_default_is_window_mode_unvalidated(self):
        t, v = synth(); r = run_pipeline(t, v)
        self.assertEqual(r["normalization_mode"], "window"); self.assertEqual(r["validation_status"], "unvalidated")
        self.assertTrue(any("normalisation" in w for w in r["warnings"]))

    def test_config_switch_changes_pipeline_without_code_change(self):
        t, v = synth(); a = run_pipeline(t, v)
        os.environ.update(SOMNNET_TRAIN_MEAN="95", SOMNNET_TRAIN_STD="3")
        try: b = run_pipeline(t, v)
        finally: os.environ.pop("SOMNNET_TRAIN_MEAN"); os.environ.pop("SOMNNET_TRAIN_STD")
        self.assertEqual(b["normalization_mode"], "global"); self.assertEqual(b["config"]["train_std"], 3.0)
        self.assertNotEqual(a["normalization_mode"], b["normalization_mode"])

    def test_invalid_data_errors(self):
        t, v = synth()
        for bad_t, bad_v, frag in [([], [], "No SpO2"), (t[:10], v[:10], "too short"),
                                   (t, np.full_like(v, 20.0), "invalid rows"), (t[::20], v[::20], "too coarse")]:
            with self.assertRaises(SpO2ValidationError) as cm:
                run_pipeline(bad_t, bad_v)
            self.assertIn(frag.lower(), str(cm.exception).lower())

    def test_gap_windows_are_skipped(self):
        t, v = synth(); keep = (np.arange(len(t)) < 600) | (np.arange(len(t)) > 900)
        r = run_pipeline(t[keep], v[keep])
        self.assertLess(r["windows_analysed"], r["windows_total"])


class CsvTests(unittest.TestCase):
    def test_parse_ok(self):
        t, v = parse_csv(DATA.read_bytes()); self.assertEqual(len(t), 1800); self.assertEqual(v[0], 96)

    def test_errors(self):
        for content, frag in [(b"", "empty"), (b"time,value\n1,2\n", "missing"), (b"\xff\xfe\x00", "utf-8")]:
            with self.assertRaises(SpO2ValidationError) as cm: parse_csv(content)
            self.assertIn(frag, str(cm.exception).lower())
        t, v = parse_csv("timestamp,spo2\n2026-10-01T22:00:00,abc\nnot-a-date,95\n2026-10-01T22:00:02,150\n")
        self.assertTrue(np.isnan(v[0]) and np.isnan(t[1]))
        with self.assertRaises(SpO2ValidationError): clean_series(t, v)

    def test_preview(self):
        p = service.preview_csv(DATA.read_bytes())
        self.assertTrue(p["valid"]); self.assertEqual(p["rows_total"], 1800); self.assertLessEqual(len(p["chart"]), 700)
        self.assertFalse(service.preview_csv(b"a,b\n1,2")["valid"])


class EventTests(unittest.TestCase):
    def test_merge_and_ahi(self):
        starts = np.arange(0, 88 * 8, 88); pos = np.array([0, 1, 1, 0, 1, 0, 0, 1], bool)
        ev = aggregate_events(starts, pos, np.ones(8, bool), 0.0)
        self.assertEqual([e["windows"] for e in ev], [2, 1, 1])
        ev2 = aggregate_events(starts, pos, np.array([1, 1, 0, 1, 1, 1, 1, 1], bool), 0.0)  # invalid window splits run
        self.assertEqual([e["windows"] for e in ev2], [1, 1, 1])
        self.assertEqual(aggregate_events(starts, ~np.ones(8, bool), np.ones(8, bool), 0.0), [])
        self.assertEqual(len(aggregate_events(starts, pos, np.ones(8, bool), 0.0, min_event_windows=2)), 1)

    def test_ahi_formula(self):
        self.assertAlmostEqual(estimated_ahi(47, 6.5), 7.2308, places=3)
        with self.assertRaises(ValueError): estimated_ahi(1, 0)

    def test_pipeline_structure(self):
        t, v = synth(); r = run_pipeline(t, v)
        self.assertAlmostEqual(r["estimated_ahi"], r["detected_events"] / r["sleep_duration_hours"], delta=0.02)
        self.assertEqual(r["model_name"], "SomnNET-SpO2-Binary"); self.assertLessEqual(r["minimum_spo2"], r["average_spo2"])


class FakeHTTP:
    def __init__(self, pages): self.pages, self.calls = pages, []
    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params, headers)); body = self.pages[len(self.calls) - 1]
        class R:
            status_code = body.get("_status", 200)
            def json(s): return body
        return R()


class UbidotsTests(unittest.TestCase):
    def setUp(self): os.environ["UBIDOTS_TOKEN"] = "fake-token"
    def tearDown(self): os.environ.pop("UBIDOTS_TOKEN", None)

    def test_parse_values(self):
        out = ubidots.parse_values({"results": [{"value": 97.0, "timestamp": 1790000000000}, {"value": None, "timestamp": 1790000001000},
                                                {"value": "x", "timestamp": 1790000002000}, {"value": 1}]})
        self.assertEqual(out, [(1790000000.0, 97.0), (1790000001.0, None), (1790000002.0, None)])

    def test_missing_credentials(self):
        os.environ.pop("UBIDOTS_TOKEN")
        with self.assertRaises(ubidots.UbidotsConfigError): ubidots.fetch_spo2(0, 10)
        pid = new_patient()
        with self.assertRaises(ubidots.UbidotsConfigError): service.analyze_ubidots(pid, 0, 3600)

    def test_pagination_auth_and_end_to_end(self):
        t, v = synth(1200)
        def page(lo, hi, nxt): return {"results": [{"value": float(v[i]), "timestamp": int(t[i] * 1000)} for i in range(hi - 1, lo - 1, -1)], "next": nxt}
        http = FakeHTTP([page(600, 1200, "https://x/next?page=2"), page(0, 600, None)])
        pid = new_patient()
        r = service.analyze_ubidots(pid, t[0], t[-1], http=http)
        self.assertEqual(len(http.calls), 2); self.assertEqual(http.calls[0][2]["X-Auth-Token"], "fake-token")
        self.assertIn("/devices/esp32_health_monitor/spo2/values/", http.calls[0][0])
        self.assertEqual((r["source"], r["patient_id"], r["device_label"]), ("ubidots", pid, "esp32_health_monitor"))

    def test_error_statuses(self):
        for st, exc in ((401, ubidots.UbidotsError), (404, ubidots.UbidotsError), (500, ubidots.UbidotsError)):
            with self.assertRaises(exc): ubidots.fetch_spo2(0, 10, http=FakeHTTP([{"_status": st}]))

    def test_empty_range(self):
        with self.assertRaises(SpO2ValidationError):
            service.analyze_ubidots(new_patient(), 0, 10, http=FakeHTTP([{"results": [], "next": None}]))


class PersistenceTests(unittest.TestCase):
    def test_save_and_patient_association(self):
        a, b = new_patient("A"), new_patient("B")
        r = service.analyze_csv(a, DATA.read_bytes())
        self.assertEqual(r["patient_id"], a); self.assertTrue(a.startswith("SGP-"))
        for f in ("source estimated_ahi detected_events sleep_duration_hours average_spo2 minimum_spo2 maximum_spo2 analysis_start "
                  "analysis_end model_name model_version normalization_mode created_at validation_status").split():
            self.assertIsNotNone(r[f], f)
        self.assertEqual(r["source"], "manual"); self.assertEqual(r["validation_status"], "unvalidated")
        self.assertEqual(service.latest(a)["analysis_id"], r["analysis_id"])
        self.assertIsNone(service.latest(b)); self.assertEqual(service.history(b), [])
        self.assertEqual(len(service.history(a)), 1)
        self.assertEqual(service.latest_for_all()[a]["analysis_id"], r["analysis_id"])

    def test_manual_and_ubidots_use_identical_pipeline(self):
        os.environ["UBIDOTS_TOKEN"] = "t"
        try:
            t, v = synth(1200); pid = new_patient()
            m = service.analyze_and_save(pid, "manual", t, v)
            http = FakeHTTP([{"results": [{"value": float(x), "timestamp": int(a * 1000)} for a, x in zip(t, v)], "next": None}])
            u = service.analyze_ubidots(pid, t[0], t[-1], http=http)
        finally: os.environ.pop("UBIDOTS_TOKEN")
        for k in ("estimated_ahi", "detected_events", "sleep_duration_hours", "average_spo2", "minimum_spo2"):
            self.assertEqual(m[k], u[k], k)

    def test_unknown_patient_rejected(self):
        with self.assertRaises(service.PatientNotFound): service.analyze_csv("SGP-999999", DATA.read_bytes())
        with db.connect() as con: self.assertEqual(con.execute("SELECT COUNT(*) FROM ml_analyses WHERE patient_id='SGP-999999'").fetchone()[0], 0)

    def test_db_enforces_id_format(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with db.connect() as con:
                con.execute("INSERT INTO ml_analyses (id,patient_id,source,status,model_name,model_version,normalization_mode,created_at) "
                            "VALUES ('x','P001','manual','completed','m','v','window','now')")

    def test_failed_analysis_is_recorded_not_in_latest(self):
        pid = new_patient()
        with self.assertRaises(SpO2ValidationError): service.analyze_csv(pid, b"timestamp,spo2\n2026-10-01T22:00:00,96\n")
        self.assertIsNone(service.latest(pid)); h = service.history(pid, include_failed=True)
        self.assertEqual(h[0]["status"], "failed"); self.assertTrue(h[0]["error_message"])

    def test_chat_context_never_invents(self):
        pid = new_patient(); self.assertIsNone(service.chat_context(pid))
        self.assertIn("No ML sleep analysis", service.deterministic_explanation(pid))
        r = service.analyze_csv(pid, DATA.read_bytes()); ctx = service.chat_context(pid)
        self.assertIn(f"Estimated AHI (unvalidated ML estimate): {r['estimated_ahi']}", ctx); self.assertIn(pid, ctx)
        self.assertIn("not a diagnosis", service.deterministic_explanation(pid))


class TokenTests(unittest.TestCase):
    def test_roundtrip_tamper_expiry(self):
        t = create_token("SGP-000001", "patient"); p = verify_token(t)
        self.assertEqual((p["sub"], p["role"]), ("SGP-000001", "patient"))
        with self.assertRaises(ValueError): verify_token(t[:-2] + "xx")
        with self.assertRaises(ValueError): verify_token(create_token("a", "admin", ttl_seconds=-1))
        with self.assertRaises(ValueError): verify_token("garbage")
        body, sig = t.split("."); forged = create_token("SGP-000002", "patient").split(".")[0] + "." + sig
        with self.assertRaises(ValueError): verify_token(forged)


class FinalRequirementTests(unittest.TestCase):
    """Requirements from the final change request. Data is SYNTHETIC."""

    def test_empty_csv_raises_validation_error_for_422(self):
        pid = new_patient()
        for content in (b"", b"   \n", ""):
            with self.assertRaises(SpO2ValidationError) as cm: service.analyze_csv(pid, content)
            self.assertIn("empty", str(cm.exception).lower())

    def test_reproducibility_and_label_fields(self):
        pid = new_patient(); r = service.analyze_csv(pid, DATA.read_bytes())
        self.assertEqual(r["sampling_rate_hz"], 8); self.assertEqual(r["analysed_samples"], r["windows_analysed"] * 88)
        self.assertGreater(r["input_samples"], 0); self.assertEqual(r["ahi_label"], "Estimated AHI — Unvalidated")
        self.assertIn("Not a clinical diagnosis", r["disclaimer"]); self.assertEqual(r["config"]["normalization_mode"], "window")
        self.assertAlmostEqual(r["estimated_ahi"], r["detected_events"] / r["sleep_duration_hours"], delta=0.02)
        self.assertIn("Analysed samples", service.chat_context(pid))

    def test_only_spo2_variable_is_requested_for_the_model(self):
        os.environ["UBIDOTS_TOKEN"] = "secret-token-xyz"
        try:
            t, v = synth(1200)
            http = FakeHTTP([{"results": [{"value": float(x), "timestamp": int(a * 1000)} for a, x in zip(t, v)], "next": None}])
            service.analyze_ubidots(new_patient(), t[0], t[-1], http=http)
            self.assertEqual(len(http.calls), 1); self.assertIn("/spo2/values/", http.calls[0][0])
            for other in ("heart_rate", "ecg", "respiratory_pressure", "temperature"):
                self.assertNotIn(f"/{other}/", http.calls[0][0])
            all_http = FakeHTTP([{"results": [], "next": None}] * 5)
            ubidots.fetch_all_sensor_data(0, 10, http=all_http)
            self.assertEqual(sorted(c[0].split("/")[-3] for c in all_http.calls),
                             ["ecg", "heart_rate", "respiratory_pressure", "spo2", "temperature"])
            self.assertEqual({c[0].split("/devices/")[1].split("/")[0] for c in all_http.calls}, {"esp32_health_monitor"})
        finally: os.environ.pop("UBIDOTS_TOKEN")

    def test_variable_and_device_env_overrides(self):
        os.environ.update(UBIDOTS_SPO2_VARIABLE="o2", UBIDOTS_DEVICE_LABEL="dev2", UBIDOTS_TOKEN="x")
        try:
            http = FakeHTTP([{"results": [], "next": None}]); ubidots.fetch_spo2(0, 10, http=http)
            self.assertIn("/devices/dev2/o2/values/", http.calls[0][0])
        finally:
            for k in ("UBIDOTS_SPO2_VARIABLE", "UBIDOTS_DEVICE_LABEL", "UBIDOTS_TOKEN"): os.environ.pop(k)

    def test_token_never_in_errors_or_results(self):
        os.environ["UBIDOTS_TOKEN"] = "secret-token-xyz"
        try:
            for st in (401, 404, 500):
                try: ubidots.fetch_spo2(0, 10, http=FakeHTTP([{"_status": st}]))
                except ubidots.UbidotsError as e: self.assertNotIn("secret-token-xyz", str(e))
            class Boom:
                def get(self, *a, **k): raise ConnectionError("failed for X-Auth-Token secret-token-xyz")
            try: ubidots.fetch_spo2(0, 10, http=Boom())
            except ubidots.UbidotsError as e: self.assertNotIn("secret-token-xyz", str(e) + repr(e.__cause__ and type(e.__cause__)))
        finally: os.environ.pop("UBIDOTS_TOKEN")

    def test_canonical_id_chain(self):
        import re, json
        pid = new_patient("Chain"); self.assertRegex(pid, r"^SGP-\d{6}$")
        service.analyze_csv(pid, DATA.read_bytes())
        self.assertEqual(storage.get_patient(pid)["patient_id"], pid)
        self.assertEqual(service.latest(pid)["patient_id"], pid); self.assertIn(f"Patient ID: {pid}", service.chat_context(pid))
        with db.connect() as con:
            ids = {r[0] for r in con.execute("SELECT DISTINCT patient_id FROM ml_analyses")}
        self.assertTrue(all(storage.get_patient(i) is not None or i == "SGP-999999" for i in ids))
        self.assertFalse(any(not re.match(r"^SGP-\d{6}$", i) for i in ids))

    def test_expired_and_malformed_tokens(self):
        for bad in ("", "Bearer", "abc.def", create_token("SGP-000001", "patient", ttl_seconds=-5)):
            with self.assertRaises(ValueError): verify_token(bad)


if __name__ == "__main__":
    unittest.main()
