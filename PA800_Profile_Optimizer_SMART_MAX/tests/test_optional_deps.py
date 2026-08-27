import unittest
from unittest.mock import patch

from pa800_optimizer import optional_deps


class OptionalDependencyTests(unittest.TestCase):
    def test_capability_probe_never_required_for_core(self):
        caps = optional_deps.capabilities()
        self.assertEqual(caps["core"], all(x.available for x in optional_deps.probe_required().values()))

    def test_missing_required_dependency_disables_core(self):
        missing={"mido":optional_deps.DependencyState("mido","core",False,"")}
        with patch.object(optional_deps,"probe_required",return_value=missing):
            self.assertFalse(optional_deps.capabilities()["core"])

    def test_missing_optional_import_does_not_break_probe(self):
        real_import = optional_deps.importlib.import_module

        def guarded(name):
            if name == "numpy":
                raise ImportError("simulated missing optional dependency")
            return real_import(name)

        with patch.object(optional_deps.importlib, "import_module", side_effect=guarded):
            states = optional_deps.probe()
        self.assertFalse(states["numpy"].available)


if __name__ == "__main__":
    unittest.main()