from __future__ import annotations

import unittest
from unittest.mock import patch

from app.modules.runtime_catalog.application.model_connection import (
    ModelReferenceError,
    create_model_reference,
    parse_model_reference,
)


class ModelReferenceTests(unittest.TestCase):
    def test_model_reference_is_signed_and_scoped(self) -> None:
        reference = create_model_reference(
            project_id="project-1", model_id="deepseek:chat", secret="x" * 32
        )
        self.assertEqual(
            parse_model_reference(reference, secret="x" * 32)["project_id"], "project-1"
        )
        with self.assertRaises(ModelReferenceError):
            parse_model_reference(reference + "x", secret="x" * 32)

    def test_model_reference_expires(self) -> None:
        with patch("app.modules.runtime_catalog.application.model_connection.time.time", return_value=100):
            reference = create_model_reference(
                project_id="project-1", model_id="deepseek:chat", secret="x" * 32
            )
        with patch("app.modules.runtime_catalog.application.model_connection.time.time", return_value=1000):
            with self.assertRaises(ModelReferenceError):
                parse_model_reference(reference, secret="x" * 32)
