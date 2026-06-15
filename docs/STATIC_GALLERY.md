# Static Gallery

The static gallery lives in `examples/generated_reports/`.

To host it, publish `examples/generated_reports/index.html` with the sibling files and
subdirectories in `examples/generated_reports/`; no backend service, API key, or video is required.

Local rebuild:

```bash
python scripts/build_demo.py
```

Integrity check:

```bash
python scripts/verify_demo.py --check
```

In the public mirror, enable GitHub Pages with Source = GitHub Actions. The workflow in
`.github/workflows/pages.yml` deploys `examples/generated_reports/`.

Final public gallery URL:

```text
https://pickbranchz.github.io/DGPForge-STAI-X-Award-C/
```

## Troubleshooting

- In repo Settings -> Pages, set Source to GitHub Actions.
- If the Pages workflow reports that deployment was skipped, enable Pages in the public mirror and rerun the workflow.
- Check the Actions tab for the Pages workflow.
- Wait a few minutes after successful deployment.
- If the repository is private, Pages availability depends on the GitHub plan; the Pages site may still be publicly accessible depending on plan/settings.
- Do not publish sensitive data in the static gallery.
