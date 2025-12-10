# Stagewell AI - Waitlist Landing Page

This is the landing page for Stagewell AI waitlist signup.

## GitHub Pages Setup

To enable GitHub Pages for this repository:

1. Go to your repository settings on GitHub
2. Navigate to "Pages" in the left sidebar
3. Under "Source", select:
   - **Branch**: `main`
   - **Folder**: `/ (root)`
4. Click "Save"

Your site will be available at: `https://mrpolanco.github.io/stagewell-config/`

## File Structure

```
/
├── index.html          # Main landing page
├── assets/
│   └── app-screenshot.png
├── config/
│   └── flags.json
├── _config.yml         # Jekyll configuration (disables processing)
├── .nojekyll           # Tells GitHub Pages to skip Jekyll
└── README.md
```

## Local Development

Simply open `index.html` in a web browser, or use a local server:

```bash
# Python 3
python3 -m http.server 8000

# Node.js (with http-server)
npx http-server

# Then visit http://localhost:8000
```

## Troubleshooting

If the page doesn't load on GitHub Pages:

1. **Check repository visibility**: GitHub Pages works on public repositories (free accounts) or private repositories with GitHub Pro/Team
2. **Verify branch**: Ensure you're using `main` branch (or `master` if that's your default)
3. **Check file paths**: All paths are relative and should work automatically
4. **Wait a few minutes**: GitHub Pages can take a few minutes to build and deploy
5. **Check Actions tab**: Look for any build errors in the GitHub Actions tab

## Notes

- The `.nojekyll` file tells GitHub Pages to serve files as static HTML without Jekyll processing
- Image paths are relative and will work on both GitHub Pages and locally
- The page is fully responsive and works on all devices
