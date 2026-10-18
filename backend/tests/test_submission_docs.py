"""Offline checks for the submission's shared docs and packaging contract."""

from html.parser import HTMLParser
from pathlib import Path
import re
import tomllib
import unittest
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"


class HTMLLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []

    def handle_starttag(self, tag, attrs):
        self.targets.extend(
            value for key, value in attrs
            if key in {"href", "src"} and value
        )


def heading_ids(text):
    # GitHub-style slugs for the simple ATX headings used by these guides.
    counts = {}
    result = set()
    for title in re.findall(r"^#{1,6}\s+(.+)$", text, re.MULTILINE):
        slug = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        result.add(f"{slug}-{count}" if count else slug)
    return result


class SubmissionDocumentationTests(unittest.TestCase):
    def test_one_shared_application_readme(self):
        self.assertTrue((ROOT / "README.md").is_file())
        for application in ("backend", "frontend"):
            self.assertFalse((ROOT / application / "README.md").exists())

    def test_local_document_links_and_anchors_resolve(self):
        documents = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
        self.assertGreater(len(documents), 1)
        for document in documents:
            # Code examples are not rendered links/headings.
            text = re.sub(r"```.*?```", "", document.read_text(), flags=re.DOTALL)
            html = HTMLLinks()
            html.feed(text)
            targets = re.findall(r"!?\[[^\]]*\]\(([^)\s]+)\)", text)
            for target in targets + html.targets:
                url = urlsplit(target)
                if url.scheme or url.netloc:
                    continue  # No network or hosted-service probes.
                destination = (
                    document.parent / unquote(url.path)
                    if url.path else document
                ).resolve()
                with self.subTest(document=document.name, target=target):
                    self.assertTrue(destination.is_relative_to(ROOT))
                    self.assertTrue(destination.exists(), str(destination))
                    if url.fragment and destination.suffix == ".md":
                        contents = re.sub(
                            r"```.*?```", "", destination.read_text(), flags=re.DOTALL
                        )
                        self.assertIn(unquote(url.fragment), heading_ids(contents))

    def test_backend_metadata_and_docker_do_not_require_a_second_readme(self):
        metadata = tomllib.loads((BACKEND / "pyproject.toml").read_text())
        description = metadata["project"]["readme"]
        self.assertIsInstance(description, dict)
        self.assertEqual(description["content-type"], "text/markdown")
        self.assertIn("https://github.com/Khushi-Kasturiya/hugback-ai", description["text"])
        self.assertNotIn("file", description)
        dockerfile = (BACKEND / "Dockerfile").read_text()
        self.assertIn("COPY pyproject.toml ./", dockerfile)
        self.assertNotIn("README.md", dockerfile)

    def test_backend_distribution_only_discovers_application_packages(self):
        metadata = tomllib.loads((BACKEND / "pyproject.toml").read_text())
        discovery = metadata["tool"]["setuptools"]["packages"]["find"]
        self.assertEqual(discovery["include"], ["app", "app.*"])

    def test_local_frontend_example_explicitly_disables_hosted_firebase(self):
        values = {}
        for line in (ROOT / "frontend" / ".env.example").read_text().splitlines():
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key] = value
        self.assertEqual(values["NEXT_PUBLIC_FIREBASE_API_KEY"], "")
        self.assertEqual(values["NEXT_PUBLIC_HUGBACK_API_URL"], "http://127.0.0.1:8000")
        self.assertEqual(values["NEXT_PUBLIC_HUGBACK_WS_URL"], "ws://127.0.0.1:8000/ws")


if __name__ == "__main__":
    unittest.main()
