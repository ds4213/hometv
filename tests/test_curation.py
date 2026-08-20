import unittest
import json
import tempfile
from pathlib import Path

from hometv.curation import (
    CurationError,
    CuratedSource,
    load_curated_source,
    merge_curated_sites,
    parse_spider_reference,
    select_curated_sites,
)


class CurationTests(unittest.TestCase):
    def test_real_policy_contains_exact_approved_keys(self):
        policy = load_curated_source(Path("sources/wanger-curated.json"))
        self.assertEqual(policy.source_id, "wangerxiao")
        self.assertEqual(policy.name_prefix, "🐮")
        self.assertEqual(policy.keys, (
            "二小", "玩偶", "AiNewGuanYing", "AiQwMkv", "NewZhiZhen", "AiNewLibvio",
            "WexHanXiaoQuan", "WexAiGuaZi", "WexAiDuBoKu", "WexAiYueYue", "WexAiWenCai",
            "WexAiV6DaShiXiong", "WexAiV6TeGou", "賤賤", "WexAiYiYs", "WexAiReBo",
            "WexAiBoBo", "WexAiIkanBot", "DuanJuAiHaoKan", "DuanJuAiQiMiao", "DuanJuAiXingYa",
            "AnimeXiFan", "AnimeCiYuanCheng", "AnimeAiMiaoWu", "ChildrenAiBaoBao", "ChildrenAiBeiWa",
            "少儿教育", "小学课堂", "MusicAiLiYuan", "MusicAiIKtv", "MusicAiKuWo",
            "SportAiFeiQiu", "SportAiGuaZi", "SportAiKanQiuTong", "SportAiKanqiu"
        ))

    def test_policy_schema_must_be_exact_integer_one(self):
        source = {"schema": True, "source_id": "x", "name_prefix": "🐮", "keys": ["a"]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaises(CurationError):
                load_curated_source(path)
            source["schema"] = 1.0
            path.write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaises(CurationError):
                load_curated_source(path)

    def test_spider_reference_requires_valid_http_url(self):
        self.assertEqual(
            parse_spider_reference("https://repo.example/spider.jpg;md5;" + "a" * 32),
            ("https://repo.example/spider.jpg", "md5", "a" * 32),
        )
        for reference in (
            "https://repo.example/ bad.jpg;md5;" + "a" * 32,
            "https://user:pass@repo.example/spider.jpg;md5;" + "a" * 32,
            "https:///spider.jpg;md5;" + "a" * 32,
        ):
            with self.assertRaises(CurationError):
                parse_spider_reference(reference)

    def test_selection_preserves_upstream_order_and_fields(self):
        policy = CuratedSource("wangerxiao", "🐮", ("b", "a"))
        upstream = {"sites": [
            {"key": "a", "name": "A", "type": 3, "api": "csp_A", "ext": {"x": 1}},
            {"key": "ignored", "name": "I", "type": 3, "api": "csp_I"},
            {"key": "b", "name": "B", "type": 3, "api": "csp_B", "timeout": 120},
        ]}
        selected = select_curated_sites(upstream, policy, "https://repo/spider.jpg;md5;abc")
        self.assertEqual([site["key"] for site in selected], ["a", "b"])
        self.assertEqual(selected[0]["ext"], {"x": 1})
        self.assertEqual(selected[1]["timeout"], 120)
        self.assertTrue(all(site["name"].startswith("🐮") for site in selected))
        self.assertTrue(all(site["jar"].endswith(";md5;abc") for site in selected))

    def test_missing_duplicate_or_base_collision_is_rejected(self):
        policy = CuratedSource("wangerxiao", "🐮", ("a", "b"))
        with self.assertRaisesRegex(CurationError, "missing curated keys: b"):
            select_curated_sites({"sites": [{"key": "a", "name": "A", "type": 3}]}, policy, "jar")
        with self.assertRaisesRegex(CurationError, "duplicate upstream key: a"):
            select_curated_sites({"sites": [
                {"key": "a", "name": "A", "type": 3},
                {"key": "a", "name": "A2", "type": 3},
                {"key": "b", "name": "B", "type": 3},
            ]}, policy, "jar")
        with self.assertRaisesRegex(CurationError, "site key collision: a"):
            merge_curated_sites({"spider": "nitan", "sites": [{"key": "a"}]}, [{"key": "a"}])


if __name__ == "__main__":
    unittest.main()
