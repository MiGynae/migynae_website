#!/usr/bin/env python3
"""
Migration Script: Migrate 15 top-level guide pages into /blog/<slug>
Steps:
1. Fix internal links in blogs.json (4 posts with old-path hrefs)
2. Update build_blog.py:
   - Guide pages use original page body (custom styles, schemas, full HTML) but new canonical/breadcrumbs/nav/footer
   - Split sitemaps: sitemap-pages.xml (8 URLs only) + sitemap-blog.xml (categories + posts)
   - sitemap.xml becomes sitemap index
   - guides.html links updated to /blog/<slug>
3. Create 301 redirect stubs for the 15 root HTML files
4. Run build_blog.py
"""

import os
import json
import re
import sys

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_URL = "https://migynaeapp.com"

def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

redirects = load_json(os.path.join(WORKSPACE_DIR, "redirects.json"))
OLD_TO_NEW = {old: new for old, new in redirects.items()}  # {"/old-slug": "/blog/old-slug"}

# =========================================================================
# STEP 1: Fix internal links in blogs.json content
# =========================================================================
print("\n=== STEP 1: Fix internal links in blogs.json ===")

posts = load_json(os.path.join(WORKSPACE_DIR, "blogs.json"))
fixes = 0
for p in posts:
    content = p.get("content", "")
    new_content = content
    for old_path, new_path in OLD_TO_NEW.items():
        # Replace href="/old-slug" and href='/old-slug'
        new_content = new_content.replace(f'href="{old_path}"', f'href="{new_path}"')
        new_content = new_content.replace(f"href='{old_path}'", f"href='{new_path}'")
        # Replace href="/old-slug.html"
        slug = old_path.lstrip("/")
        new_content = new_content.replace(f'href="/{slug}.html"', f'href="{new_path}"')
        new_content = new_content.replace(f"href='/{slug}.html'", f"href='{new_path}'")
    if new_content != content:
        p["content"] = new_content
        fixes += 1
        print(f"  Fixed links in: {p['id']}")

save_json(os.path.join(WORKSPACE_DIR, "blogs.json"), posts)
print(f"  Total posts fixed: {fixes}")

# =========================================================================
# STEP 2: Update guides.html — change all 15 tile links to /blog/<slug>
# =========================================================================
print("\n=== STEP 2: Update guides.html links ===")

guides_path = os.path.join(WORKSPACE_DIR, "guides.html")
with open(guides_path, "r", encoding="utf-8") as f:
    guides_html = f.read()

guides_fixes = 0
for old_path, new_path in OLD_TO_NEW.items():
    old_href = f'href="{old_path}"'
    new_href = f'href="{new_path}"'
    if old_href in guides_html:
        guides_html = guides_html.replace(old_href, new_href)
        guides_fixes += 1
        print(f"  Updated: {old_path} -> {new_path}")

with open(guides_path, "w", encoding="utf-8") as f:
    f.write(guides_html)
print(f"  Total guides.html links fixed: {guides_fixes}")

# =========================================================================
# STEP 3: Create 301 redirect stubs for the 15 root HTML files
# =========================================================================
print("\n=== STEP 3: Create 301 redirect stubs ===")

REDIRECT_STUB_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Redirecting...</title>
    <link rel="canonical" href="{new_url}">
    <meta http-equiv="refresh" content="0; url={new_path}">
    <meta name="robots" content="noindex">
    <script>
        (function() {{
            window.location.replace("{new_path}" + (window.location.search || "") + (window.location.hash || ""));
        }})();
    </script>
</head>
<body>
    <p>This page has moved. <a href="{new_path}">Click here</a> if not redirected automatically.</p>
</body>
</html>"""

for old_path, new_path in OLD_TO_NEW.items():
    slug = old_path.lstrip("/")
    stub_path = os.path.join(WORKSPACE_DIR, f"{slug}.html")
    new_url = f"{SITE_URL}{new_path}"
    stub_content = REDIRECT_STUB_TEMPLATE.format(
        new_path=new_path,
        new_url=new_url
    )
    with open(stub_path, "w", encoding="utf-8") as f:
        f.write(stub_content)
    print(f"  Stub created: {slug}.html -> {new_path}")

print("  All 15 redirect stubs created.")

# =========================================================================
# STEP 4: Extract guide-specific metadata from original HTML files for
#         use by build_blog.py's render_guide_page function.
#         Save to guides_metadata.json
# =========================================================================
print("\n=== STEP 4: Extract guide metadata from original HTML ===")

GUIDE_SLUGS = [old_path.lstrip("/") for old_path in OLD_TO_NEW.keys()]

guides_metadata = {}
for slug in GUIDE_SLUGS:
    orig_path = os.path.join(WORKSPACE_DIR, f"{slug}.html")
    if not os.path.exists(orig_path):
        print(f"  WARNING: {slug}.html not found — using blogs.json content only")
        continue

    with open(orig_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Extract inline styles
    styles = re.findall(r"<style>(.*?)</style>", html, re.DOTALL)
    custom_styles = "\n".join(s.strip() for s in styles if s.strip())

    # Extract schemas (application/ld+json)
    schemas_raw = re.findall(r'<script type=["\x27]application/ld\+json["\x27]>(.*?)</script>', html, re.DOTALL)
    custom_schemas = []
    for s in schemas_raw:
        s_updated = s
        # Update canonical URLs in schema text
        for old_p, new_p in OLD_TO_NEW.items():
            s_updated = s_updated.replace(
                f"{SITE_URL}{old_p}",
                f"{SITE_URL}{new_p}"
            )
            s_updated = s_updated.replace(f'"{old_p}"', f'"{new_p}"')
        try:
            parsed = json.loads(s_updated.strip())
            if isinstance(parsed, list):
                custom_schemas.extend(parsed)
            else:
                custom_schemas.append(parsed)
        except Exception as e:
            print(f"  WARNING: schema parse error for {slug}: {e}")

    guides_metadata[slug] = {
        "custom_styles": custom_styles,
        "custom_schemas": custom_schemas
    }
    print(f"  Extracted metadata for: {slug}")

meta_path = os.path.join(WORKSPACE_DIR, "guides_metadata.json")
save_json(meta_path, guides_metadata)
print(f"  Saved to guides_metadata.json ({len(guides_metadata)} guides)")

print("\n=== All pre-migration steps complete! ===")
print("Next: update build_blog.py to generate guide pages with custom HTML, then run it.")
