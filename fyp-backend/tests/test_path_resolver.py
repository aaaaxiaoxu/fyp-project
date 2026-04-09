from __future__ import annotations

import unittest
from pathlib import Path

from src.settings import settings
from src.utils import path_resolver


class PathResolverTestCase(unittest.TestCase):
    def test_project_paths_follow_documented_layout(self) -> None:
        project_id = "proj_task3"
        upload_root = Path(settings.UPLOAD_FOLDER)

        self.assertEqual(path_resolver.project_dir(project_id), upload_root / "projects" / project_id)
        self.assertEqual(
            path_resolver.project_original_file_path(project_id, "source.md"),
            upload_root / "projects" / project_id / "original" / "source.md",
        )
        self.assertEqual(
            path_resolver.project_relative_path(project_id, "ontology.json"),
            f"projects/{project_id}/ontology.json",
        )

    def test_simulation_and_explorer_paths_follow_documented_layout(self) -> None:
        simulation_id = "sim_task3"
        upload_root = Path(settings.UPLOAD_FOLDER)

        self.assertEqual(
            path_resolver.simulation_reddit_profiles_path(simulation_id),
            upload_root / "simulations" / simulation_id / "profiles" / "reddit_profiles.json",
        )
        self.assertEqual(
            path_resolver.explorer_console_log_path(simulation_id, "session_task3"),
            upload_root / "explorer" / simulation_id / "console" / "session_task3.log",
        )
        self.assertEqual(
            path_resolver.simulation_relative_path(simulation_id, "simulation_config.json"),
            f"simulations/{simulation_id}/simulation_config.json",
        )

    def test_upload_relative_conversion_round_trip(self) -> None:
        project_path = path_resolver.project_extracted_text_path("proj_roundtrip")

        relative = path_resolver.as_upload_relative_path(project_path)
        resolved = path_resolver.resolve_upload_path(relative)

        self.assertEqual(relative, "projects/proj_roundtrip/extracted_text.txt")
        self.assertEqual(resolved, project_path)

    def test_invalid_segments_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            path_resolver.project_original_file_path("proj_task3", "../source.md")

        with self.assertRaises(ValueError):
            path_resolver.resolve_upload_path("../outside.txt")

        with self.assertRaises(ValueError):
            path_resolver.as_upload_relative_path("/tmp/outside.txt")


if __name__ == "__main__":
    unittest.main()
