name: 每日課程自動刷新

on:
  schedule:
    - cron: '0 0 * * *'
  workflow_dispatch:

jobs:
  refresh:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install anthropic playwright
          playwright install chromium
          playwright install-deps chromium

      - name: Run refresh
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python scripts/refresh.py

      - name: Commit if changed
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/courses.json data/refresh_log.json
          git diff --cached --quiet || git commit -m "🤖 每日課程更新 $(date +'%Y-%m-%d')"
          git push
