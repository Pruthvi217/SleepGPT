"""HTTP-level tests: auth, patient/admin dashboards, ML endpoints, authorization.
Needs fastapi + httpx (pip install -r backend/requirements-dev.txt); skipped otherwise."""
import os, unittest
from pathlib import Path
from tests import conftest  # noqa: F401

try:
    from fastapi.testclient import TestClient
    HAVE = True
except Exception:  # pragma: no cover
    HAVE = False

DATA = Path(__file__).parent / "data" / "synthetic_spo2.csv"


@unittest.skipUnless(HAVE, "fastapi/httpx not installed")
class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app as app_module
        cls.c = TestClient(app_module.app)
        cls.admin = {"Authorization": "Bearer " + cls.c.post("/api/admin/login", json={"username": "admin", "password": "admin-test-pw"}).json()["token"]}
        cls.pid = cls._register("Alice"); cls.other = cls._register("Bob")
        cls.hp = cls._login(cls.pid); cls.ho = cls._login(cls.other)

    @classmethod
    def _register(cls, name):
        return cls.c.post("/api/patient/register", json={"username": name}).json()["patient_id"]

    @classmethod
    def _login(cls, pid):
        r = cls.c.post("/api/patient/login", json={"patient_id": pid}); assert r.status_code == 200
        return {"Authorization": "Bearer " + r.json()["token"]}

    def _upload(self, pid, path="manual", content=None, headers=None):
        return self.c.post(f"/api/ml/patients/{pid}/{path}", headers=headers or self.admin,
                           files={"file": ("s.csv", content if content is not None else DATA.read_bytes(), "text/csv")})

    def test_01_login_bad_credentials(self):
        self.assertEqual(self.c.post("/api/admin/login", json={"username": "admin", "password": "x"}).status_code, 401)
        self.assertEqual(self.c.post("/api/patient/login", json={"patient_id": "SGP-999999"}).status_code, 404)

    def test_02_protected_endpoints_need_token(self):
        for method, url in [("get", "/api/admin/patients"), ("get", f"/api/ml/patients/{self.pid}/latest"),
                            ("get", f"/api/assessment/start?patient_id={self.pid}"), ("get", f"/api/sensors/{self.pid}"),
                            ("get", "/api/ml/admin/summary")]:
            self.assertEqual(getattr(self.c, method)(url).status_code, 401, url)
        self.assertEqual(self.c.post("/api/chat", json={"message": "hi"}).status_code, 401)
        self.assertEqual(self.c.get("/api/ml/health").status_code, 200)

    def test_03_manual_run_save_and_dashboards(self):
        r = self._upload(self.pid); self.assertEqual(r.status_code, 200, r.text); a = r.json()
        self.assertEqual((a["patient_id"], a["source"], a["status"]), (self.pid, "manual", "completed"))
        self.assertEqual(a["validation_status"], "unvalidated")
        lat = self.c.get(f"/api/ml/patients/{self.pid}/latest", headers=self.hp).json()
        self.assertEqual(lat["latest"]["analysis_id"], a["analysis_id"]); self.assertIn("not a clinical diagnosis", lat["disclaimer"])
        self.assertEqual(len(self.c.get(f"/api/ml/patients/{self.pid}/history", headers=self.hp).json()["history"]), 1)
        d = self.c.get(f"/api/admin/patient/{self.pid}", headers=self.admin).json()
        self.assertEqual(d["ml_latest"]["analysis_id"], a["analysis_id"])
        self.assertEqual(self.c.get("/api/ml/admin/summary", headers=self.admin).json()["latest"][self.pid]["analysis_id"], a["analysis_id"])

    def test_04_patient_cannot_see_other_patient(self):
        self._upload(self.pid)
        for url in (f"/api/ml/patients/{self.pid}/latest", f"/api/ml/patients/{self.pid}/history", f"/api/sensors/{self.pid}",
                    f"/api/assessment/results?patient_id={self.pid}"):
            self.assertEqual(self.c.get(url, headers=self.ho).status_code, 403, url)
        self.assertEqual(self.c.post("/api/chat", headers=self.ho, json={"message": "my AHI", "patient_id": self.pid}).status_code, 403)
        self.assertEqual(self.c.post("/api/assessment/answer", headers=self.ho, json={"patient_id": self.pid, "question_id": 1, "value": 1}).status_code, 403)

    def test_05_patient_cannot_run_analysis_or_admin_routes(self):
        self.assertEqual(self._upload(self.other, headers=self.ho).status_code, 403)
        self.assertEqual(self.c.post(f"/api/ml/patients/{self.other}/ubidots", headers=self.ho, json={"start": "2026-10-01T00:00:00Z", "end": "2026-10-01T06:00:00Z"}).status_code, 403)
        self.assertEqual(self.c.get("/api/admin/patients", headers=self.ho).status_code, 403)

    def test_06_unknown_patient_and_invalid_csv(self):
        self.assertEqual(self._upload("SGP-999999").status_code, 404)
        r = self._upload(self.pid, content=b"timestamp,spo2\n2026-10-01T22:00:00,96\n"); self.assertEqual(r.status_code, 422)
        self.assertEqual(self._upload(self.pid, content=b"").status_code, 422)
        self.assertEqual(self._upload(self.pid, content=b"a,b\n1,2").status_code, 422)

    def test_07_preview_does_not_save(self):
        before = len(self.c.get(f"/api/ml/patients/{self.pid}/history", headers=self.admin).json()["history"])
        p = self._upload(self.pid, "manual/preview").json()
        self.assertTrue(p["valid"]); self.assertEqual(p["rows_total"], 1800)
        self.assertEqual(len(self.c.get(f"/api/ml/patients/{self.pid}/history", headers=self.admin).json()["history"]), before)

    def test_08_ubidots_missing_credentials(self):
        body = {"start": "2026-10-01T00:00:00Z", "end": "2026-10-01T06:00:00Z"}
        self.assertEqual(self.c.post(f"/api/ml/patients/{self.pid}/ubidots", headers=self.admin, json=body).status_code, 503)
        self.assertEqual(self.c.get(f"/api/ml/patients/{self.pid}/sensor-data", headers=self.admin, params=body).status_code, 503)
        self.assertEqual(self.c.post(f"/api/ml/patients/{self.pid}/ubidots", headers=self.admin, json={"start": "x", "end": "y"}).status_code, 422)
        self.assertFalse(self.c.get("/api/ml/health").json()["ubidots_configured"])

    def test_09_chat_without_and_with_ml(self):
        r = self.c.post("/api/chat", headers=self.ho, json={"message": "What is my AHI?", "patient_id": self.other}).json()
        self.assertIn("No ML sleep analysis", r["response"])
        self._upload(self.pid)
        r = self.c.post("/api/chat", headers=self.hp, json={"message": "Explain my AHI", "patient_id": self.pid}).json()
        self.assertTrue(r["response"])   # LLM text if Ollama is up, deterministic explanation otherwise

    def test_10_health_exposes_no_secrets(self):
        h = self.c.get("/api/ml/health").json()
        self.assertTrue(h["model_loaded"]); self.assertNotIn("token", str(h).lower().replace("ubidots_configured", ""))

    # ---- final-request additions ----
    def test_11_empty_csv_is_422(self):
        r = self._upload(self.pid, content=b""); self.assertEqual(r.status_code, 422, r.text)
        r = self._upload(self.pid, "manual/preview", content=b""); self.assertFalse(r.json()["valid"])

    def test_12_invalid_expired_and_wrong_role_tokens(self):
        from utils.tokens import create_token
        expired = {"Authorization": "Bearer " + create_token(self.pid, "patient", ttl_seconds=-5)}
        forged = {"Authorization": "Bearer garbage.token"}
        for h in (expired, forged, {"Authorization": "Basic abc"}):
            self.assertEqual(self.c.get(f"/api/ml/patients/{self.pid}/latest", headers=h).status_code, 401)
            self.assertEqual(self.c.get("/api/admin/patients", headers=h).status_code, 401)
        self.assertEqual(self.c.get("/api/admin/patients", headers=self.hp).status_code, 403)

    def test_13_malformed_and_unknown_ids(self):
        for bad in ("SGP-999999", "not-an-id", "P001"):
            self.assertEqual(self.c.get(f"/api/ml/patients/{bad}/latest", headers=self.admin).status_code, 404, bad)
            self.assertEqual(self.c.get(f"/api/ml/patients/{bad}/latest", headers=self.hp).status_code, 403, bad)

    def test_14_every_route_requires_auth_except_allowlist(self):
        import app as app_module
        from fastapi.routing import APIRoute
        public = {"/", "/health", "/api/ml/health", "/api/patient/register", "/api/patient/login", "/api/admin/login"}
        checked = 0
        for route in app_module.app.routes:
            if not isinstance(route, APIRoute) or route.path in public:
                continue
            path = route.path.replace("{patient_id}", "SGP-000001").replace("{analysis_id}", "x")
            for m in route.methods - {"HEAD", "OPTIONS"}:
                r = self.c.request(m, path + "?patient_id=SGP-000001")
                self.assertEqual(r.status_code, 401, f"{m} {route.path} is not protected (got {r.status_code})")
                checked += 1
        self.assertGreater(checked, 15)

    def test_15_token_not_leaked_by_api(self):
        os.environ["UBIDOTS_TOKEN"] = "secret-token-xyz"
        try:
            for url in ("/api/ml/health",):
                self.assertNotIn("secret-token-xyz", self.c.get(url).text)
            from unittest import mock
            with mock.patch("requests.get", side_effect=ConnectionError("boom X-Auth-Token secret-token-xyz")):  # no real network call
                r = self.c.post(f"/api/ml/patients/{self.pid}/ubidots", headers=self.admin,
                                json={"start": "2026-10-01T00:00:00Z", "end": "2026-10-01T06:00:00Z"})
            self.assertEqual(r.status_code, 502); self.assertNotIn("secret-token-xyz", r.text)
            self.assertTrue(self.c.get("/api/ml/health").json()["ubidots_configured"])
        finally: os.environ.pop("UBIDOTS_TOKEN")

    def test_16_response_labels_unvalidated(self):
        a = self._upload(self.pid).json()
        self.assertEqual(a["ahi_label"], "Estimated AHI — Unvalidated"); self.assertIn("Not a clinical diagnosis", a["disclaimer"])
        self.assertEqual(a["sampling_rate_hz"], 8)


if __name__ == "__main__":
    unittest.main()
