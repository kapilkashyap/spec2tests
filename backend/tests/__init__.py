"""Test suite package for the Spec2Tests backend.

This package intentionally contains no test collection logic itself; its
presence marks ``tests`` as a regular Python package so that shared fixtures,
helpers, and test modules within it can use relative imports and be
discovered consistently by pytest (see ``backend/pytest.ini``).
"""
