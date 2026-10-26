import ast
from pathlib import Path
import unittest


def load_get_url():
    path = Path(__file__).resolve().parents[2] / "alembic" / "env.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    function = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "get_url"
    )
    isolated = ast.Module(body=[function], type_ignores=[])
    namespace = {}
    exec(compile(isolated, str(path), "exec"), namespace)
    return namespace["get_url"]


class AlembicDatabaseRoleTest(unittest.TestCase):
    def test_migrator_url_has_priority(self):
        get_url = load_get_url()
        env = {"ALEMBIC_DATABASE_URL": "migration-dsn", "DATABASE_URL": "write-dsn"}
        self.assertEqual(get_url(env), "migration-dsn")

    def test_database_url_is_legacy_fallback(self):
        self.assertEqual(load_get_url()({"DATABASE_URL": "write-dsn"}), "write-dsn")

    def test_missing_url_error_is_sanitized(self):
        with self.assertRaises(RuntimeError) as caught:
            load_get_url()({})
        self.assertNotIn("://", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
