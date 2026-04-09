from __future__ import annotations

import unittest
from unittest.mock import patch

from zep_cloud.core.api_error import ApiError

from src.services.graph_builder import GraphBuilderService
from src.services.ontology_generator import OntologyGenerator
from src.utils.zep_paging import _fetch_page_with_retry


class _FakeEpisode:
    def __init__(self, processed: bool = True) -> None:
        self.processed = processed


class _FakeEpisodeClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get(self, *, uuid_: str) -> _FakeEpisode:
        self.calls.append(uuid_)
        return _FakeEpisode(processed=True)


class _FakeGraphClient:
    def __init__(self) -> None:
        self.set_ontology_kwargs: dict | None = None
        self.episode = _FakeEpisodeClient()

    def set_ontology(self, **kwargs) -> None:
        self.set_ontology_kwargs = kwargs


class _FakeClient:
    def __init__(self) -> None:
        self.graph = _FakeGraphClient()


class Task6ServiceFixesTestCase(unittest.TestCase):
    def test_ontology_generator_normalizes_label_and_type_keys(self) -> None:
        result = OntologyGenerator()._validate_and_process(
            {
                "entity_types": [
                    {"label": "student_leader", "description": "学生干部"},
                    {"type": "organization", "description": "组织"},
                ],
                "edge_types": [
                    {
                        "label": "reports_on",
                        "source_targets": [{"source": "student_leader", "target": "organization"}],
                    },
                    {
                        "type": "supports",
                        "source_targets": [{"source": "organization", "target": "student_leader"}],
                    },
                ],
            }
        )

        self.assertEqual(result["entity_types"][0]["name"], "StudentLeader")
        self.assertEqual(result["entity_types"][1]["name"], "Organization")
        self.assertEqual(result["edge_types"][0]["name"], "REPORTS_ON")
        self.assertEqual(result["edge_types"][1]["name"], "SUPPORTS")
        self.assertEqual(result["edge_types"][0]["source_targets"][0]["source"], "StudentLeader")
        self.assertEqual(result["edge_types"][0]["source_targets"][0]["target"], "Organization")

    def test_graph_builder_set_ontology_accepts_string_attributes_and_label_keys(self) -> None:
        client = _FakeClient()
        service = GraphBuilderService(client=client, send_delay_s=0, poll_interval_s=0.1)

        service.set_ontology(
            "graph_task6",
            {
                "entity_types": [
                    {
                        "label": "student_leader",
                        "attributes": [
                            "id code",
                            {"name": "age_range", "description": "age range"},
                        ],
                    }
                ],
                "edge_types": [
                    {
                        "type": "reports_on",
                        "attributes": ["fact score"],
                        "source_targets": [{"source": "Student", "target": "Organization"}],
                    }
                ],
            },
        )

        assert client.graph.set_ontology_kwargs is not None
        entities = client.graph.set_ontology_kwargs["entities"]
        edges = client.graph.set_ontology_kwargs["edges"]

        self.assertIn("student_leader", entities)
        self.assertIn("reports_on", edges)
        self.assertEqual(list(entities["student_leader"].model_fields.keys()), ["id_code", "age_range"])
        self.assertEqual(list(edges["reports_on"][0].model_fields.keys()), ["fact_score"])

    def test_wait_for_episodes_polls_only_a_sample_each_cycle(self) -> None:
        client = _FakeClient()
        service = GraphBuilderService(client=client, send_delay_s=0, poll_interval_s=0.1)
        episode_ids = [f"ep_{index}" for index in range(40)]
        sample_sizes: list[int] = []

        def deterministic_sample(population, k):
            sample_sizes.append(k)
            return list(population)[:k]

        with patch("random.sample", side_effect=deterministic_sample), patch("time.sleep", return_value=None):
            service.wait_for_episodes(episode_ids, max_polls_per_cycle=7)

        self.assertTrue(sample_sizes)
        self.assertTrue(all(size <= 7 for size in sample_sizes))
        self.assertGreater(len(sample_sizes), 1)
        self.assertEqual(len(client.graph.episode.calls), len(episode_ids))

    def test_zep_paging_retries_api_429_with_retry_after(self) -> None:
        calls = {"count": 0}

        def flaky_page():
            calls["count"] += 1
            if calls["count"] == 1:
                raise ApiError(status_code=429, headers={"retry-after": "0"}, body={"error": "rate limit"})
            return ["ok"]

        with patch("time.sleep", return_value=None) as sleep_mock:
            result = _fetch_page_with_retry(flaky_page, max_retries=3, page_description="test page")

        self.assertEqual(result, ["ok"])
        self.assertEqual(calls["count"], 2)
        sleep_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
