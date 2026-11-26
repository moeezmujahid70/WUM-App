import unittest
from types import SimpleNamespace

import requests

import ai_client


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.ok = 200 <= status_code < 300
        self.text = str(payload)

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error:
            raise self.error
        return self.response


def settings(**overrides):
    values = {
        "api": "https://server.example/",
        "openai_api_key": "",
        "openai_model": "gpt-4o-mini",
        "openai_base_url": "https://api.openai.com/v1",
        "openai_timeout": 45,
        "login_email": "user@example.com",
        "login_password": "secret",
        "login_machine_uuid": "machine",
        "login_processor_id": "cpu",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class ServerAITest(unittest.TestCase):

    def test_without_own_key_the_server_generates_the_text(self):
        session = FakeSession(FakeResponse(200, {"status": "ok", "answer": "Hello there"}))

        answer = ai_client.generate_text(
            "Write an email", "Be brief", config=settings(), session=session
        )

        self.assertEqual(answer, "Hello there")
        url, kwargs = session.calls[0]
        self.assertEqual(url, "https://server.example/verify/ai_response")
        payload = kwargs["json"]
        self.assertEqual(payload["email"], "user@example.com")
        self.assertEqual(payload["password"], "secret")
        self.assertEqual(payload["machine_uuid"], "machine")
        self.assertEqual(payload["processor_id"], "cpu")
        self.assertIn("Be brief", payload["prompt"])
        self.assertIn("Write an email", payload["prompt"])

    def test_server_error_message_is_raised(self):
        session = FakeSession(FakeResponse(401, {"error": "Unauthorized"}))

        with self.assertRaises(ai_client.AIError) as caught:
            ai_client.generate_text("p", config=settings(), session=session)

        self.assertIn("Unauthorized", str(caught.exception))

    def test_missing_login_session_fails_before_calling_server(self):
        session = FakeSession(FakeResponse(200, {"status": "ok", "answer": "x"}))

        with self.assertRaises(ai_client.AIError):
            ai_client.generate_text(
                "p", config=settings(login_password=""), session=session
            )

        self.assertEqual(session.calls, [])

    def test_empty_answer_is_an_error(self):
        session = FakeSession(FakeResponse(200, {"status": "ok", "answer": "  "}))

        with self.assertRaises(ai_client.AIError):
            ai_client.generate_text("p", config=settings(), session=session)

    def test_network_failure_is_an_ai_error(self):
        session = FakeSession(error=requests.exceptions.ConnectionError("down"))

        with self.assertRaises(ai_client.AIError):
            ai_client.generate_text("p", config=settings(), session=session)


class ServerOnlyTest(unittest.TestCase):

    def test_configured_openai_key_is_ignored_and_server_is_used(self):
        session = FakeSession(FakeResponse(200, {"status": "ok", "answer": "From server"}))

        answer = ai_client.generate_text(
            "p", "sys", config=settings(openai_api_key="sk-test"), session=session
        )

        self.assertEqual(answer, "From server")
        url, kwargs = session.calls[0]
        self.assertEqual(url, "https://server.example/verify/ai_response")
        self.assertNotIn("headers", kwargs)


if __name__ == "__main__":
    unittest.main()
