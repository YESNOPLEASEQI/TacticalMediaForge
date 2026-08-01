"""Regression checks for the public project package name."""

import importlib.util
import unittest


class ProjectNamingTests(unittest.TestCase):
    def test_correctly_spelled_package_is_importable(self):
        package = importlib.util.find_spec("military_video_gen")

        self.assertIsNotNone(package)
