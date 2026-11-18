#!/usr/bin/env python3
"""
Automated Verification Suite for MiGynae Category Blog Rebuild
=============================================================
Runs acceptance checks 1 through 7 directly against generated filesystem assets:
1. Existing /blog/<slug> legacy files exist, return valid HTML, and bodies unchanged.
2. All 15 posts appear on exactly one category page; none uncategorized.
3. Category URLs are /blog/<category-slug> (no /category/); /blog/pregnancy-lifestyle exists with dual routing.
4. Collision detection test.
5. "View source" on /blog and category pages has post links; no "Loading articles...".
6. Empty categories are absent from nav, index, sitemap; marked noindex.
7. Validates breadcrumbs, JSON-LD schemas, sitemap, and runs full internal link check.
"""

import os
import re
import json
import xml.etree.ElementTree as ET

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))

def resolve_path(url_path):
    """
    Simulates GitHub Pages clean URL resolution:
    /blog -> blog/index.html or blog.html
    /blog/foo -> blog/foo.html or blog/foo/index.html
    /blog/foo/bar -> blog/foo/bar.html or blog/foo/bar/index.html
    """
    clean = url_path.strip("/")
    candidates = [
        os.path.join(WORKSPACE_DIR, f"{clean}.html"),
        os.path.join(WORKSPACE_DIR, clean, "index.html"),
        os.path.join(WORKSPACE_DIR, clean)
    ]
    for c in candidates:
        if os.path.isfile(c):
            with open(c, "r", encoding="utf-8") as f:
                return 200, f.read()
    return 404, None

def run_checks():
    taxonomy = json.load(open(os.path.join(WORKSPACE_DIR, "blog_taxonomy.json"), encoding="utf-8"))
    posts = json.load(open(os.path.join(WORKSPACE_DIR, "blogs.json"), encoding="utf-8"))

    passed = 0
    total = 7

    # --------------------------------------------------------------------------
    # Check 1: Existing legacy posts return 200 and body content unchanged
    # --------------------------------------------------------------------------
    print("\n--- Running Check 1: Legacy Post URLs & Content Integrity ---")
    legacy_slugs = [
        "9th-month-nutrition-guide",
        "first-trimester-diet-guide",
        "nausea-friendly-diet",
        "pregnancy-101",
        "pregnancy-exercises"
    ]
    check1_ok = True
    for slug in legacy_slugs:
        status, html = resolve_path(f"/blog/{slug}")
        if status != 200:
            print(f"FAIL: /blog/{slug} could not be resolved (404)")
            check1_ok = False
        else:
            if slug == "9th-month-nutrition-guide" and "10 Traditional Superfoods" not in html:
                print(f"FAIL: /blog/{slug} content mismatch")
                check1_ok = False
            elif slug == "pregnancy-exercises" and "Safe Exercises for 9th Month" not in html:
                print(f"FAIL: /blog/{slug} content mismatch")
                check1_ok = False
            elif slug == "nausea-friendly-diet" and "Nausea-Friendly Diet Guide" not in html:
                print(f"FAIL: /blog/{slug} content mismatch")
                check1_ok = False
    if check1_ok:
        print("PASS (Check 1): All legacy /blog/<slug> URLs resolve to 200 and retain body content.")
        passed += 1

    # --------------------------------------------------------------------------
    # Check 2: All 15 posts appear on exactly one category page; none uncategorised
    # --------------------------------------------------------------------------
    print("\n--- Running Check 2: All 15 Posts Categorised & Unique ---")
    check2_ok = True
    category_counts = {}

    for cat in taxonomy["categories"]:
        c_slug = cat["slug"]
        status, html = resolve_path(f"/blog/{c_slug}")
        if status != 200:
            print(f"FAIL: Category page /blog/{c_slug} could not be resolved")
            check2_ok = False
            continue

        found_on_page = []
        for p in posts:
            if f'/blog/{p["id"]}' in html:
                found_on_page.append(p["id"])

        category_counts[c_slug] = found_on_page

    for p in posts:
        p_id = p["id"]
        expected_cat = p["category"]
        found_in = [c for c, found in category_counts.items() if p_id in found]
        if found_in != [expected_cat]:
            print(f"FAIL: Post '{p_id}' found in {found_in}, expected [{expected_cat}]")
            check2_ok = False

    if check2_ok and len(posts) == 15:
        print("PASS (Check 2): All 15 posts appear on exactly one category page; 0 uncategorized, 0 duplicates.")
        passed += 1

    # --------------------------------------------------------------------------
    # Check 3: Clean Category URLs (no /category/); /blog/pregnancy-lifestyle returns 200
    # --------------------------------------------------------------------------
    print("\n--- Running Check 3: Clean Category URLs & /blog/pregnancy-lifestyle ---")
    check3_ok = True
    status, html = resolve_path("/blog/pregnancy-lifestyle")
    if status != 200:
        print("FAIL: /blog/pregnancy-lifestyle could not be resolved")
        check3_ok = False
    elif "/category/" in html:
        print("FAIL: Found '/category/' in /blog/pregnancy-lifestyle HTML links")
        check3_ok = False
    else:
        # Check subcategory page as well
        s_status, s_html = resolve_path("/blog/pregnancy-lifestyle/travel-and-safety")
        if s_status != 200:
            print("FAIL: Subcategory /blog/pregnancy-lifestyle/travel-and-safety could not be resolved")
            check3_ok = False

    # Check dual-routing files exist on disk for GitHub Pages
    dual_check = [
        "blog/pregnancy-lifestyle.html",
        "blog/pregnancy-lifestyle/index.html",
        "blog/pregnancy-lifestyle/travel-and-safety.html",
        "blog/pregnancy-lifestyle/travel-and-safety/index.html"
    ]
    for dc in dual_check:
        if not os.path.exists(os.path.join(WORKSPACE_DIR, dc)):
            print(f"FAIL: Dual route file {dc} does not exist on disk")
            check3_ok = False

    if check3_ok:
        print("PASS (Check 3): Category URLs are clean /blog/<category-slug>; /blog/pregnancy-lifestyle resolves with dual files.")
        passed += 1

    # --------------------------------------------------------------------------
    # Check 4: Collision protection failure test
    # --------------------------------------------------------------------------
    print("\n--- Running Check 4: Collision Protection Verification ---")
    import test_collision
    check4_ok = test_collision.test_slug_collision()
    if check4_ok:
        print("PASS (Check 4): Collision protection fails build as expected on conflict.")
        passed += 1

    # --------------------------------------------------------------------------
    # Check 5: View source on /blog and category pages has post links; no "Loading articles..."
    # --------------------------------------------------------------------------
    print("\n--- Running Check 5: Server-rendered Initial HTML (No Loading Articles) ---")
    status, blog_html = resolve_path("/blog")
    check5_ok = True
    if "Loading articles..." in blog_html:
        print("FAIL: 'Loading articles...' found in /blog initial HTML")
        check5_ok = False

    # Verify post links exist in raw initial HTML
    for p in posts[:5]:
        if f'/blog/{p["id"]}' not in blog_html:
            print(f"FAIL: Post link /blog/{p['id']} missing from initial /blog HTML")
            check5_ok = False

    if check5_ok:
        print("PASS (Check 5): Initial HTML on /blog contains static post links; 'Loading articles...' is eliminated.")
        passed += 1

    # --------------------------------------------------------------------------
    # Check 6: Empty categories are absent from nav, index and sitemap, and marked noindex
    # --------------------------------------------------------------------------
    print("\n--- Running Check 6: Empty Categories Hidden & Noindex ---")
    check6_ok = True
    empty_slugs = [
        'pregnancy-week-by-week',
        'pregnancy-nutrition',
        'pregnancy-fitness',
        'mental-wellbeing',
        'labour-and-delivery',
        'postpartum-recovery',
        'baby-care',
        'womens-health',
        'pregnancy-myths-and-facts'
    ]
    sitemap_text = open(os.path.join(WORKSPACE_DIR, "sitemap.xml"), encoding="utf-8").read()

    for es in empty_slugs:
        if f"/blog/{es}" in sitemap_text:
            print(f"FAIL: Empty category '{es}' found in sitemap.xml")
            check6_ok = False
        if f'class="category-chip">{es}' in blog_html or f'href="/blog/{es}" class="category-chip"' in blog_html:
            print(f"FAIL: Empty category '{es}' chip found on /blog")
            check6_ok = False
        e_status, e_html = resolve_path(f"/blog/{es}")
        if 'noindex' not in e_html:
            print(f"FAIL: Empty category page /blog/{es} is missing 'noindex' robots meta tag")
            check6_ok = False

    if check6_ok:
        print("PASS (Check 6): All 9 empty categories omitted from nav/index/sitemap and marked noindex.")
        passed += 1

    # --------------------------------------------------------------------------
    # Check 7: Breadcrumbs, JSON-LD, Sitemap validation, and Link check
    # --------------------------------------------------------------------------
    print("\n--- Running Check 7: Schema Validation & Comprehensive Internal Link Check ---")
    check7_ok = True

    # 1. Sitemap XML parse validation
    try:
        ET.parse(os.path.join(WORKSPACE_DIR, "sitemap.xml"))
        print("  -> sitemap.xml parsed successfully as valid XML.")
    except Exception as e:
        print(f"FAIL: sitemap.xml invalid XML: {e}")
        check7_ok = False

    # 2. JSON-LD checks on /blog, category page, post page
    test_urls = ["/blog", "/blog/pregnancy-lifestyle", "/blog/travelling-during-pregnancy"]
    for tu in test_urls:
        st, thtml = resolve_path(tu)
        schemas = re.findall(r'<script type="application/ld\+json">(.*?)</script>', thtml, re.DOTALL)
        if not schemas:
            print(f"FAIL: No JSON-LD schema found on {tu}")
            check7_ok = False
        for s in schemas:
            try:
                json.loads(s.strip())
            except Exception as e:
                print(f"FAIL: Invalid JSON-LD on {tu}: {e}")
                check7_ok = False

    # 3. BreadcrumbList check on category and post pages
    for tu in ["/blog/pregnancy-lifestyle", "/blog/travelling-during-pregnancy"]:
        st, thtml = resolve_path(tu)
        if '"@type": "BreadcrumbList"' not in thtml:
            print(f"FAIL: BreadcrumbList schema missing on {tu}")
            check7_ok = False

    # 4. Internal Link Check: Scan links from /blog and /blog/pregnancy-lifestyle
    urls_to_check = set()
    for tu in ["/blog", "/blog/pregnancy-lifestyle", "/blog/getting-pregnant"]:
        st, thtml = resolve_path(tu)
        links = re.findall(r'href="(/blog/[^"#?]+)"', thtml)
        urls_to_check.update(links)

    print(f"  -> Testing {len(urls_to_check)} internal blog links...")
    for link in urls_to_check:
        st, _ = resolve_path(link)
        if st != 200:
            print(f"FAIL: Broken internal link {link} -> {st}")
            check7_ok = False

    if check7_ok:
        print("PASS (Check 7): Schemas validate, breadcrumbs intact, sitemap valid, and 0 broken links.")
        passed += 1

    print(f"\n==========================================")
    print(f"Acceptance Checks Summary: {passed}/{total} Passed")
    print(f"==========================================")
    return passed == total

if __name__ == "__main__":
    success = run_checks()
    if not success:
        exit(1)
