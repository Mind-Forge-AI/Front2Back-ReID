# Publish the Front2Back-ReID project page

There are two public pieces, with different jobs:

| Location | What it is for |
| --- | --- |
| **GitHub repository + GitHub Pages** | The project website and browser. It contains the benchmark files so the page can show images and the all-500-pair explorer works. |
| **Google Drive or Google Cloud Storage ZIP** | The single downloadable, versioned package researchers save locally, unzip, validate, and use in experiments. |

They intentionally contain the same public benchmark data. The ZIP is not a replacement
for the website files; it is the convenient reproducible download.

## Step 1 — Use the correct folder

Use only `export/front2back-reid-public-v1`. Do **not** use `front2back-reid-v1`:
that is your private archival export.

## Step 2 — Copy everything into the new GitHub repository

Copy **every item shown in the public-release folder** into the root of your new GitHub
repository. Yes, this includes these four folders:

- `annotations`
- `data`
- `inputs`
- `splits`

Also copy every file beside them: `index.html`, `explorer.html`, `project.css`,
`project.js`, `site-config.json`, `README.md`, `PUBLISH_GITHUB_PAGES.md`,
`evaluate.py`, `verify.py`, `checksums.sha256`, `CITATION.cff`, `LICENSE`,
`.nojekyll`, and `.gitattributes`.

Do **not** copy the public ZIP itself into the GitHub repository. It is hosted on
Google Drive or Google Cloud Storage instead.

After copying, the repository root should look like this:

```text
Front2Back-ReID/
  annotations/  data/  inputs/  splits/
  index.html    explorer.html    site-config.json
  README.md     evaluate.py      verify.py
  CITATION.cff  LICENSE          .nojekyll
```

## Step 3 — Upload the ZIP for researchers to download

Upload these two files to Google Drive or Google Cloud Storage:

- `export/front2back-reid-public-v1.zip`
- `export/front2back-reid-public-v1.zip.sha256`

**Google Cloud Storage is recommended** because it gives stable direct HTTPS links.
Make both objects publicly readable and copy their URLs.

For **Google Drive**, set both files to “Anyone with the link”, then test the link in
a private/incognito browser window. Use a direct-download URL, not a Drive preview
page URL.

## Step 4 — Connect the website button to the ZIP

In the new GitHub repository, open `site-config.json` and replace the placeholder URLs:

```json
{
  "dataset_url": "https://YOUR-HOST/front2back-reid-public-v1.zip",
  "checksum_url": "https://YOUR-HOST/front2back-reid-public-v1.zip.sha256"
}
```

Commit and push the repository. The blue **Download dataset ZIP** button will now send
researchers to your Drive/GCS archive.

## Step 5 — Turn on GitHub Pages

On GitHub, open the repository’s **Settings → Pages**. Under **Build and deployment**:

1. Select **Deploy from a branch**.
2. Select branch `main`.
3. Select folder `/(root)`.
4. Click **Save**.

GitHub will show the public project-page URL after deployment.

## Step 6 — Test it before announcing

Open the Pages URL in a private browser window. Check that:

1. The two hero images load.
2. **Open all 500 pairs** works.
3. The blue download button downloads the ZIP.
4. `README.md` explains the task after unzipping.

Finally, verify the ZIP you downloaded:

```powershell
Get-FileHash .\front2back-reid-public-v1.zip -Algorithm SHA256
```

Its value must match the text in `front2back-reid-public-v1.zip.sha256`.
