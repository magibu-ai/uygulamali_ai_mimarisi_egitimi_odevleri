"""Arac semasi (TOOL_SCHEMAS) ve TOOLS kaydinin dogrulugu."""

import json
import unittest

import tools

EXPECTED = {"internet_search", "get_weather", "check_part_status", "get_race_regulations"}


class ToolRegistryTests(unittest.TestCase):
    def test_exactly_four_tools(self):
        self.assertEqual(len(tools.TOOLS), 4)
        self.assertEqual(set(tools.TOOLS), EXPECTED)

    def test_every_tool_is_callable(self):
        for name, fn in tools.TOOLS.items():
            self.assertTrue(callable(fn), f"{name} cagirilabilir olmali")

    def test_schema_count_and_names_match_registry(self):
        names = [s["function"]["name"] for s in tools.TOOL_SCHEMAS]
        self.assertEqual(len(names), 4)
        self.assertEqual(set(names), EXPECTED)
        self.assertEqual(set(names), set(tools.TOOLS))

    def test_schema_structure(self):
        for schema in tools.TOOL_SCHEMAS:
            self.assertEqual(schema.get("type"), "function")
            fn = schema.get("function")
            self.assertIsInstance(fn, dict)
            self.assertIn("name", fn)
            self.assertIn("description", fn)
            self.assertIsInstance(fn["description"], str)
            self.assertTrue(fn["description"].strip())
            params = fn.get("parameters")
            self.assertIsInstance(params, dict)
            self.assertEqual(params.get("type"), "object")
            self.assertIsInstance(params.get("properties"), dict)
            self.assertIsInstance(params.get("required"), list)
            # her required alan properties icinde tanimli olmali
            for req in params["required"]:
                self.assertIn(req, params["properties"])

    def test_schemas_are_json_serializable(self):
        # Ollama'ya JSON olarak gonderildigi icin serilesebilir olmali.
        dumped = json.dumps(tools.TOOL_SCHEMAS)
        self.assertEqual(json.loads(dumped), tools.TOOL_SCHEMAS)


if __name__ == "__main__":
    unittest.main()
