"""Tests for LanguageDetector."""

from pathlib import Path

from mrcis.services.indexing.language import LanguageDetector


class TestLanguageDetector:
    """Tests for LanguageDetector class."""

    def test_detect_python_file(self):
        """Detector should recognize Python files."""
        detector = LanguageDetector()
        assert detector.detect(Path("script.py")) == "python"
        assert detector.detect(Path("module.pyi")) == "python"

    def test_detect_typescript_file(self):
        """Detector should recognize TypeScript files."""
        detector = LanguageDetector()
        assert detector.detect(Path("app.ts")) == "typescript"
        assert detector.detect(Path("component.tsx")) == "typescript"

    def test_detect_javascript_file(self):
        """Detector should recognize JavaScript files."""
        detector = LanguageDetector()
        assert detector.detect(Path("app.js")) == "javascript"
        assert detector.detect(Path("component.jsx")) == "javascript"

    def test_detect_ruby_file(self):
        """Detector should recognize Ruby files."""
        detector = LanguageDetector()
        assert detector.detect(Path("script.rb")) == "ruby"
        assert detector.detect(Path("Rakefile")) == "ruby"
        assert detector.detect(Path("tasks.rake")) == "ruby"

    def test_detect_go_file(self):
        """Detector should recognize Go files."""
        detector = LanguageDetector()
        assert detector.detect(Path("main.go")) == "go"

    def test_detect_rust_file(self):
        """Detector should recognize Rust files."""
        detector = LanguageDetector()
        assert detector.detect(Path("main.rs")) == "rust"

    def test_detect_java_file(self):
        """Detector should recognize Java files."""
        detector = LanguageDetector()
        assert detector.detect(Path("Main.java")) == "java"

    def test_detect_kotlin_file(self):
        """Detector should recognize Kotlin files."""
        detector = LanguageDetector()
        assert detector.detect(Path("Main.kt")) == "kotlin"

    def test_detect_unknown_extension(self):
        """Detector should return None for unknown extensions."""
        detector = LanguageDetector()
        assert detector.detect(Path("file.txt")) is None
        assert detector.detect(Path("README.md")) is None
        assert detector.detect(Path("config.json")) is None

    def test_detect_case_insensitive(self):
        """Detector should handle uppercase extensions."""
        detector = LanguageDetector()
        assert detector.detect(Path("SCRIPT.PY")) == "python"
        assert detector.detect(Path("APP.JS")) == "javascript"
