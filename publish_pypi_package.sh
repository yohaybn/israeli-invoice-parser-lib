# Clear old distribution builds
rm -rf dist/ build/ *.egg-info

# Build the new wheel and source distribution
python3 -m build

# Upload to PyPI using your account token credentials
python3 -m twine upload dist/*