- name: Run tests
  env:
    PYTHONPATH: ${{ github.workspace }}
  run: pytest -q
