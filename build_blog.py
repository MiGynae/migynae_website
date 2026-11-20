#!/usr/bin/env python3
"""
MiGynae Blog Static Build Pipeline
=================================
Generates static, SEO-optimized, accessible HTML for the category-based MiGynae blog.
Ensures zero client-side "Loading articles..." delays, strict slug collision protection,
valid JSON-LD schemas, breadcrumbs, clean URLs (no /category/), and sitemap synchronization.

v2: Adds guide page rendering (migrated top-level articles), split sitemaps
    (sitemap-pages.xml + sitemap-blog.xml + sitemap index), and redirect stubs.
"""

import os
import sys
import json
import re
import math
from datetime import datetime

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_URL = "https://migynaeapp.com"
RESERVED_ROUTES = {"page", "search", "tag", "feed", "rss", "sitemap", "index", "category", "admin", "api"}
POSTS_PER_PAGE = 12

# Guide slugs that use the full custom-HTML rendering path
GUIDE_SLUGS = {
    "irregular-periods-pcos-india", "free-period-tracker", "safe-period-method-pregnancy",
    "free-kick-tracker", "reduced-fetal-movement-when-to-worry",
    "labour-prep-guide", "pre-labour-prep-guide", "during-labour-guide",
    "epidural-guide", "caesarean-guide",
    "postpartum-recovery-guide", "post-delivery-guide",
    "partner-support-guide", "family-support-guide", "pregnancy-beauty-salon-guide"
}

def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def escape_html(text):
    if not text:
        return ""
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#39;"))

def format_date(iso_date):
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
        return dt.strftime("%B %d, %Y")
    except Exception:
        return iso_date

def validate_and_check_collisions(taxonomy, posts):
    """
    Collision Protection:
    FAIL if any category slug equals any post slug or a reserved route.
    Print a clear error naming the conflict.
    Validate that every post has an existing category in taxonomy.
    """
    category_slugs = set()
    subcategory_slugs = {}
    categories_by_slug = {}

    for cat in taxonomy["categories"]:
        c_slug = cat["slug"]
        if c_slug in RESERVED_ROUTES:
            raise RuntimeError(f"BUILD ERROR: Collision detected! Category slug '{c_slug}' is a reserved route.")
        if c_slug in category_slugs:
            raise RuntimeError(f"BUILD ERROR: Duplicate category slug detected: '{c_slug}'.")
        category_slugs.add(c_slug)
        categories_by_slug[c_slug] = cat

        sub_slugs = set()
        for sub in cat.get("subcategories", []):
            s_slug = sub["slug"]
            if s_slug in RESERVED_ROUTES:
                raise RuntimeError(f"BUILD ERROR: Collision detected! Sub-category slug '{s_slug}' is a reserved route.")
            if s_slug in sub_slugs:
                raise RuntimeError(f"BUILD ERROR: Duplicate sub-category slug '{s_slug}' in category '{c_slug}'.")
            sub_slugs.add(s_slug)
        subcategory_slugs[c_slug] = sub_slugs

    post_slugs = set()
    for post in posts:
        p_id = post.get("id")
        if not p_id:
            raise ValueError("BUILD ERROR: Post missing 'id' (slug).")
        if p_id in RESERVED_ROUTES:
            raise RuntimeError(f"BUILD ERROR: Collision detected! Post slug '{p_id}' is a reserved route.")
        if p_id in post_slugs:
            raise RuntimeError(f"BUILD ERROR: Duplicate post slug detected: '{p_id}'.")
        if p_id in category_slugs:
            raise RuntimeError(f"BUILD ERROR: Collision detected! Post slug '{p_id}' conflicts with category slug '{p_id}'.")

        post_slugs.add(p_id)

        # Validate category
        cat_slug = post.get("category")
        if not cat_slug or cat_slug not in category_slugs:
            raise ValueError(f"BUILD ERROR: Post '{p_id}' has missing or unknown category '{cat_slug}'.")

        # Validate subcategory if present
        sub_slug = post.get("subcategory")
        if sub_slug and sub_slug not in subcategory_slugs[cat_slug]:
            raise ValueError(f"BUILD ERROR: Post '{p_id}' has unknown subcategory '{sub_slug}' under category '{cat_slug}'.")

    print(f"Validation successful: {len(category_slugs)} categories, {len(post_slugs)} posts. No collisions.")
    return categories_by_slug, subcategory_slugs

def build_mega_menu_html(taxonomy, visible_categories):
    """
    Renders accessible desktop mega-menu & mobile accordion HTML grouped by nav groups.
    Only shows visible categories.
    """
    visible_cat_map = {c["slug"]: c for c in visible_categories}
    groups = taxonomy["navGroups"]

    html = ['<div class="mega-menu" id="blogMegaMenu" role="menu" aria-label="Blog Topics">']
    html.append('  <div class="mega-menu-grid">')

    for grp in groups:
        # Collect visible categories for this group
        cats_in_grp = [
            c for c in taxonomy["categories"]
            if c["navGroup"] == grp["id"] and c["slug"] in visible_cat_map
        ]
        if not cats_in_grp:
            continue

        html.append('    <div class="mega-menu-col">')
        html.append(f'      <div class="mega-menu-col-title">{escape_html(grp["name"])}</div>')
        html.append('      <ul class="mega-menu-list">')
        for c in cats_in_grp:
            html.append(f'        <li><a href="/blog/{c["slug"]}">{escape_html(c["name"])}</a></li>')
        html.append('      </ul>')
        html.append('    </div>')

    html.append('  </div>')
    html.append('  <div class="mega-menu-footer">')
    html.append('    <span>Explore clinical guides, symptom relief &amp; trimester care</span>')
    html.append('    <a href="/blog">View All Blog Articles &rarr;</a>')
    html.append('  </div>')
    html.append('</div>')

    return "\n".join(html)

def build_footer_topics_html(visible_categories):
    html = ['<div class="footer-section">', '  <h4>Blog Topics</h4>']
    for c in visible_categories:
        html.append(f'  <a href="/blog/{c["slug"]}">{escape_html(c["name"])}</a>')
    html.append('</div>')
    return "\n".join(html)

def build_header_html(active_link, taxonomy, visible_categories, base_href="/"):
    mega_menu_html = build_mega_menu_html(taxonomy, visible_categories)
    blog_active = ' active' if active_link == 'blog' else ''
    home_active = ' class="active"' if active_link == 'home' else ''
    features_active = ' class="active"' if active_link == 'features' else ''
    hiw_active = ' class="active"' if active_link == 'how-it-works' else ''
    resources_active = ' class="active"' if active_link == 'resources' else ''
    guides_active = ' class="active"' if active_link == 'guides' else ''

    return f"""    <header>
        <nav class="container">
            <a href="/" class="logo" style="text-decoration:none;">
                <div class="logo-mark">M</div>
                <p class="logo-title" aria-label="MiGynae">MiGynae</p>
            </a>
            <ul class="nav-links">
                <li><a href="/"{home_active}>Home</a></li>
                <li><a href="/features"{features_active}>Features</a></li>
                <li><a href="/how-it-works"{hiw_active}>How It Works</a></li>
                <li><a href="/resources"{resources_active}>Resources</a></li>
                <li class="nav-item-has-menu">
                    <a href="/blog" class="mega-menu-trigger{blog_active}" aria-haspopup="true" aria-expanded="false">
                        Blog <i class="fas fa-chevron-down chevron-icon"></i>
                    </a>
                    {mega_menu_html}
                </li>
                <li><a href="/guides"{guides_active}>Guides</a></li>
            </ul>
            <div class="mobile-menu" aria-label="Toggle menu" aria-expanded="false" role="button" tabindex="0">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </nav>
    </header>"""

def build_footer_html(visible_categories):
    topics_html = build_footer_topics_html(visible_categories)
    return f"""    <footer>
        <div class="container">
            <div class="footer-content">
                <div class="footer-brand">
                    <h3>MiGynae</h3>
                    <p>Professional pregnancy care platform trusted by healthcare professionals and expecting mothers worldwide.</p>
                </div>
                <div class="footer-section">
                    <h4>Quick Links</h4>
                    <a href="/">Home</a>
                    <a href="/features">Features</a>
                    <a href="/how-it-works">How It Works</a>
                    <a href="/resources">Resources</a>
                    <a href="/guides">Guides</a>
                    <a href="/blog">Blog Index</a>
                </div>
                {topics_html}
                <div class="footer-section">
                    <h4>Download</h4>
                    <a href="https://play.google.com/store/apps/details?id=com.mimedic.migynae" target="_blank" rel="noopener">Android App</a>
                    <a href="https://apps.apple.com/in/app/migynae/id6748379521" target="_blank" rel="noopener">iOS App</a>
                </div>
                <div class="footer-section">
                    <h4>Legal</h4>
                    <a href="/privacy-policy">Privacy Policy</a>
                    <a href="/terms-of-service">Terms of Service</a>
                </div>
            </div>
            <div class="footer-bottom">
                <p>&copy; 2026 MiGynae. All rights reserved.</p>
            </div>
        </div>
    </footer>"""

def build_app_cta_html():
    return """        <div class="app-cta-banner">
            <h2>Download MiGynae – Your Pregnancy Care Companion</h2>
            <p>Track baby kicks, time contractions, access personalized Indian nutrition charts, and get OBGYN-backed answers every day.</p>
            <div class="app-cta-buttons">
                <a href="https://play.google.com/store/apps/details?id=com.mimedic.migynae" class="app-cta-btn" target="_blank" rel="noopener">
                    <img src="/images/Playstore_button.png" alt="Get it on Google Play" height="52" width="175" loading="lazy">
                </a>
                <a href="https://apps.apple.com/in/app/migynae/id6748379521" class="app-cta-btn" target="_blank" rel="noopener">
                    <img src="/images/apple_logo_button_white.svg" alt="Download on the App Store" height="52" width="156" loading="lazy">
                </a>
            </div>
        </div>"""

def build_breadcrumbs_html(crumbs):
    """
    crumbs: list of (label, url) tuples. The last tuple is the current active page (url can be None).
    """
    items = []
    schema_items = []

    for idx, (label, url) in enumerate(crumbs):
        pos = idx + 1
        if url and idx < len(crumbs) - 1:
            items.append(f'<li><a href="{url}">{escape_html(label)}</a></li>')
            schema_items.append({
                "@type": "ListItem",
                "position": pos,
                "name": label,
                "item": f"{SITE_URL}{url}" if url.startswith("/") else url
            })
        else:
            items.append(f'<li aria-current="page">{escape_html(label)}</li>')
            schema_items.append({
                "@type": "ListItem",
                "position": pos,
                "name": label
            })

    list_html = "\n        ".join(items)
    json_ld = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": schema_items
    }

    html = f"""    <nav class="blog-breadcrumbs" aria-label="Breadcrumb">
        <div class="container">
            <ol>
                {list_html}
            </ol>
        </div>
    </nav>"""
    return html, json.dumps(json_ld, indent=2)

def build_article_card_html(post, category_name):
    img_url = "/" + post["image"] if not post["image"].startswith("/") else post["image"]
    return f"""                <article class="article-card">
                    <a href="/blog/{post['id']}" class="article-card-thumb-wrap" aria-label="{escape_html(post['title'])}">
                        <img src="{img_url}" alt="{escape_html(post.get('imageAlt', post['title']))}" class="article-card-thumb" loading="lazy" width="400" height="225">
                    </a>
                    <div class="article-card-body">
                        <div class="article-card-meta">
                            <a href="/blog/{post['category']}" class="category-badge">{escape_html(category_name)}</a>
                            <span class="article-meta-date"><i class="far fa-calendar-alt"></i> {format_date(post['date'])}</span>
                        </div>
                        <h2 class="article-card-title">
                            <a href="/blog/{post['id']}">{escape_html(post['title'])}</a>
                        </h2>
                        <p class="article-card-excerpt">{escape_html(post['excerpt'])}</p>
                        <div class="article-card-footer">
                            <span><i class="far fa-clock"></i> {escape_html(post.get('readTime', '8 min read'))}</span>
                            <a href="/blog/{post['id']}" class="read-more-link">Read Article &rarr;</a>
                        </div>
                    </div>
                </article>"""

def build_pagination_html(base_url, current_page, total_pages):
    if total_pages <= 1:
        return ""

    links = []
    for p in range(1, total_pages + 1):
        url = base_url if p == 1 else f"{base_url}?page={p}"
        active = ' class="page-link active"' if p == current_page else ' class="page-link"'
        links.append(f'<a href="{url}"{active} aria-label="Page {p}">{p}</a>')

    return f"""        <nav class="pagination-nav" aria-label="Article pagination">
            {"".join(links)}
        </nav>"""

def render_blog_index(taxonomy, visible_categories, posts, current_page=1):
    total_posts = len(posts)
    total_pages = math.ceil(total_posts / POSTS_PER_PAGE) if total_posts > 0 else 1
    start_idx = (current_page - 1) * POSTS_PER_PAGE
    page_posts = posts[start_idx:start_idx + POSTS_PER_PAGE]

    cat_map = {c["slug"]: c for c in taxonomy["categories"]}

    # Category Chips
    chips_html = ['<div class="category-chips-nav" aria-label="Filter articles by category">']
    chips_html.append('  <a href="/blog" class="category-chip active">All Topics</a>')
    for c in visible_categories:
        chips_html.append(f'  <a href="/blog/{c["slug"]}" class="category-chip">{escape_html(c["name"])}</a>')
    chips_html.append('</div>')

    # BabyCenter Category Cards Grid
    cat_cards_html = []
    for c in visible_categories:
        c_posts = [p for p in posts if p["category"] == c["slug"]]
        links_html = []
        for p in c_posts[:4]:
            links_html.append(f'<li><a href="/blog/{p["id"]}">{escape_html(p["title"])}</a></li>')
        # Also add a subcategory link if any
        if c.get("subcategories"):
            sub = c["subcategories"][0]
            links_html.append(f'<li><a href="/blog/{c["slug"]}/{sub["slug"]}">{escape_html(sub["name"])} &rarr;</a></li>')

        cat_cards_html.append(f"""            <div class="category-card">
                <div class="category-card-header">
                    <div class="category-card-icon"><i class="{c.get('icon', 'fas fa-heart')}"></i></div>
                    <h2 class="category-card-title"><a href="/blog/{c['slug']}">{escape_html(c['name'])}</a></h2>
                </div>
                <p class="category-card-desc">{escape_html(c['description'])}</p>
                <ul class="category-card-links">
                    {"".join(links_html)}
                </ul>
                <div class="category-card-action">
                    <a href="/blog/{c['slug']}" class="btn-see-all">See all {len(c_posts)} articles &rarr;</a>
                </div>
            </div>""")

    # Latest Articles Grid
    articles_html = []
    for p in page_posts:
        cat_name = cat_map.get(p["category"], {}).get("name", "Pregnancy")
        articles_html.append(build_article_card_html(p, cat_name))

    pagination_html = build_pagination_html("/blog", current_page, total_pages)
    header_html = build_header_html("blog", taxonomy, visible_categories)
    footer_html = build_footer_html(visible_categories)
    app_cta_html = build_app_cta_html()

    canonical_url = f"{SITE_URL}/blog" if current_page == 1 else f"{SITE_URL}/blog?page={current_page}"

    json_ld = {
        "@context": "https://schema.org",
        "@type": "Blog",
        "name": "MiGynae Pregnancy & Women's Health Blog",
        "url": canonical_url,
        "description": "Doctor-reviewed pregnancy insights, period health, fetal development guides, and prenatal nutrition for Indian mothers.",
        "publisher": {
            "@type": "Organization",
            "name": "MiGynae",
            "url": SITE_URL,
            "logo": {
                "@type": "ImageObject",
                "url": f"{SITE_URL}/favicon-180.png"
            }
        }
    }

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <base href="/">
    <meta charset="UTF-8">
    <script>
      (function () {{
        var p = window.location.pathname;
        if (p.endsWith('.html')) {{
          var c = p.replace(/\\.html$/, '');
          if (c === '/index' || c.endsWith('/index')) c = c.slice(0, -5) || '/';
          window.location.replace(c + window.location.search + window.location.hash);
        }}
      }})();
    </script>

    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-YRTYHVLS8B"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', 'G-YRTYHVLS8B');
    </script>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" href="/favicon.ico" sizes="any">
    <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16.png">
    <link rel="apple-touch-icon" sizes="180x180" href="/favicon-180.png">
    <title>MiGynae Pregnancy Blog — Expert Tips for Every Trimester</title>
    <meta name="description" content="Expert pregnancy tips, OBGYN-backed advice, nutrition guides, and trimester-by-trimester support from the MiGynae medical team. Free to read.">
    <link rel="canonical" href="{canonical_url}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{canonical_url}">
    <meta property="og:title" content="MiGynae Pregnancy Blog — Expert Tips for Every Trimester">
    <meta property="og:description" content="Expert pregnancy tips, OBGYN-backed advice, nutrition guides, and trimester-by-trimester support from the MiGynae team. Free to read.">
    <meta property="og:image" content="{SITE_URL}/images/weekly_updates_screen.webp">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="MiGynae Pregnancy Blog — Expert Tips for Every Trimester">
    <meta name="twitter:description" content="Expert pregnancy tips, OBGYN-backed advice, nutrition guides, and trimester-by-trimester support from the MiGynae team. Free to read.">
    <script type="application/ld+json">
{json.dumps(json_ld, indent=4)}
    </script>
    <link rel="stylesheet" href="css/index.min.css">
    <link rel="stylesheet" href="css/landing.min.css">
    <link rel="stylesheet" href="css/blog-redesign.css">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body class="blog-page">
{header_html}

    <main>
        <section class="hub-header">
            <div class="container">
                <div class="hub-header-inner">
                    <span class="hub-eyebrow">Evidence-Based Pregnancy &amp; Health</span>
                    <h1 class="hub-title">Pregnancy Insights &amp; Expert Advice</h1>
                    <p class="hub-intro">Medically reviewed articles, symptom guides, and nutrition advice to support your conception, pregnancy, and postpartum journey in India.</p>
                    {"".join(chips_html)}
                </div>
            </div>
        </section>

        <section class="category-showcase-section">
            <div class="container">
                <div class="section-header">
                    <h2>Explore by Health Category</h2>
                    <p>Select a category below to explore focused topics, doctor checklists, and symptom relief guides.</p>
                </div>
                <div class="category-showcase-grid">
{"".join(cat_cards_html)}
                </div>
            </div>
        </section>

        <section class="articles-section">
            <div class="container">
                <div class="section-header">
                    <h2>Latest Medical Articles</h2>
                    <p>Reliable healthcare guidance written and reviewed by certified gynecologists.</p>
                </div>
                <div class="articles-grid">
{"".join(articles_html)}
                </div>
{pagination_html}
{app_cta_html}
            </div>
        </section>
    </main>

{footer_html}

    <script>
        (function () {{
            var toggle = document.querySelector('.mobile-menu');
            var nav = document.querySelector('.nav-links');
            var megaTrigger = document.querySelector('.mega-menu-trigger');
            var navMenuHasSub = document.querySelector('.nav-item-has-menu');

            if (toggle && nav) {{
                function setOpen(open) {{
                    nav.classList.toggle('open', open);
                    toggle.classList.toggle('open', open);
                    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
                }}

                toggle.addEventListener('click', function () {{
                    setOpen(!nav.classList.contains('open'));
                }});

                toggle.addEventListener('keydown', function (e) {{
                    if (e.key === 'Enter' || e.key === ' ') {{
                        e.preventDefault();
                        setOpen(!nav.classList.contains('open'));
                    }}
                }});
            }}

            if (megaTrigger && navMenuHasSub) {{
                // Accessibility keyboard support
                megaTrigger.addEventListener('click', function (e) {{
                    if (window.innerWidth <= 900) {{
                        e.preventDefault();
                        navMenuHasSub.classList.toggle('mobile-open');
                        var expanded = navMenuHasSub.classList.contains('mobile-open');
                        megaTrigger.setAttribute('aria-expanded', expanded ? 'true' : 'false');
                    }}
                }});

                document.addEventListener('keydown', function (e) {{
                    if (e.key === 'Escape') {{
                        navMenuHasSub.classList.remove('mobile-open');
                        var mm = document.getElementById('blogMegaMenu');
                        if (mm) mm.classList.remove('is-open');
                        megaTrigger.setAttribute('aria-expanded', 'false');
                    }}
                }});
            }}
        }})();
    </script>
</body>
</html>"""

def render_category_page(category, taxonomy, visible_categories, posts, subcategory_filter=None):
    cat_slug = category["slug"]
    sub_slug = subcategory_filter["slug"] if subcategory_filter else None

    if sub_slug:
        cat_posts = [p for p in posts if p["category"] == cat_slug and p.get("subcategory") == sub_slug]
        page_title = f"{subcategory_filter['name']} — {category['name']} | MiGynae"
        page_h1 = subcategory_filter["name"]
        intro_copy = subcategory_filter["intro"]
        meta_desc = subcategory_filter["description"]
        canonical_path = f"/blog/{cat_slug}/{sub_slug}"
        crumbs = [
            ("Home", "/"),
            ("Blog", "/blog"),
            (category["name"], f"/blog/{cat_slug}"),
            (subcategory_filter["name"], None)
        ]
    else:
        cat_posts = [p for p in posts if p["category"] == cat_slug]
        page_title = f"{category['name']} Guide — Symptoms, Care & Health | MiGynae"
        page_h1 = category["name"]
        intro_copy = category["intro"]
        meta_desc = category["description"]
        canonical_path = f"/blog/{cat_slug}"
        crumbs = [
            ("Home", "/"),
            ("Blog", "/blog"),
            (category["name"], None)
        ]

    if len(meta_desc) > 155:
        meta_desc = meta_desc[:152] + "..."

    breadcrumbs_html, breadcrumbs_json_ld = build_breadcrumbs_html(crumbs)

    # Sub-category filter chips
    subchips_html = []
    if category.get("subcategories"):
        all_active = ' active' if not sub_slug else ''
        subchips_html.append(f'<a href="/blog/{cat_slug}" class="category-chip{all_active}">All {escape_html(category["name"])}</a>')
        for s in category["subcategories"]:
            active = ' active' if sub_slug == s["slug"] else ''
            subchips_html.append(f'<a href="/blog/{cat_slug}/{s["slug"]}" class="category-chip{active}">{escape_html(s["name"])}</a>')

    # Articles
    articles_html = []
    for p in cat_posts:
        articles_html.append(build_article_card_html(p, category["name"]))

    if not articles_html:
        articles_content = f"""                <div class="no-results" style="grid-column: 1/-1; text-align: center; padding: 60px 20px;">
                    <h3>Articles Coming Soon</h3>
                    <p>Our medical team is currently reviewing new guides for this section. Check back shortly!</p>
                    {f'<p style="margin-top: 16px;"><a href="{category.get("hubLink")}" class="btn-primary" style="display:inline-block; max-width:280px; margin:0 auto;">{category.get("hubLinkLabel", "View Guide")}</a></p>' if category.get("hubLink") else ''}
                </div>"""
    else:
        articles_content = "\n".join(articles_html)

    header_html = build_header_html("blog", taxonomy, visible_categories)
    footer_html = build_footer_html(visible_categories)
    app_cta_html = build_app_cta_html()

    canonical_url = f"{SITE_URL}{canonical_path}"

    # Schema CollectionPage + ItemList
    item_list_elements = []
    for idx, p in enumerate(cat_posts):
        item_list_elements.append({
            "@type": "ListItem",
            "position": idx + 1,
            "url": f"{SITE_URL}/blog/{p['id']}",
            "name": p["title"]
        })

    collection_schema = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": page_h1,
        "url": canonical_url,
        "description": meta_desc,
        "publisher": {
            "@type": "Organization",
            "name": "MiGynae",
            "url": SITE_URL
        },
        "mainEntity": {
            "@type": "ItemList",
            "itemListElement": item_list_elements
        }
    }

    # Meta robots: if empty, noindex
    robots_meta = '<meta name="robots" content="noindex, follow">' if len(cat_posts) == 0 else '<meta name="robots" content="index, follow">'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <base href="/">
    <meta charset="UTF-8">
    <script>
      (function () {{
        var p = window.location.pathname;
        if (p.endsWith('.html')) {{
          var c = p.replace(/\\.html$/, '');
          if (c === '/index' || c.endsWith('/index')) c = c.slice(0, -5) || '/';
          window.location.replace(c + window.location.search + window.location.hash);
        }}
      }})();
    </script>

    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-YRTYHVLS8B"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', 'G-YRTYHVLS8B');
    </script>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" href="/favicon.ico" sizes="any">
    <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16.png">
    <link rel="apple-touch-icon" sizes="180x180" href="/favicon-180.png">
    <title>{escape_html(page_title)}</title>
    <meta name="description" content="{escape_html(meta_desc)}">
    {robots_meta}
    <link rel="canonical" href="{canonical_url}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{canonical_url}">
    <meta property="og:title" content="{escape_html(page_title)}">
    <meta property="og:description" content="{escape_html(meta_desc)}">
    <meta property="og:image" content="{SITE_URL}/images/weekly_updates_screen.webp">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{escape_html(page_title)}">
    <meta name="twitter:description" content="{escape_html(meta_desc)}">
    <script type="application/ld+json">
{breadcrumbs_json_ld}
    </script>
    <script type="application/ld+json">
{json.dumps(collection_schema, indent=4)}
    </script>
    <link rel="stylesheet" href="css/index.min.css">
    <link rel="stylesheet" href="css/landing.min.css">
    <link rel="stylesheet" href="css/blog-redesign.css">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body class="blog-page">
{header_html}

    <main style="padding-top: 90px;">
        {breadcrumbs_html}

        <section class="hub-header" style="padding-top: 20px;">
            <div class="container">
                <div class="hub-header-inner">
                    <span class="hub-eyebrow">Health Category</span>
                    <h1 class="hub-title">{escape_html(page_h1)}</h1>
                    <p class="hub-intro">{escape_html(intro_copy)}</p>
                    {f'<div class="category-chips-nav">{"".join(subchips_html)}</div>' if subchips_html else ''}
                </div>
            </div>
        </section>

        <section class="articles-section">
            <div class="container">
                <div class="section-header">
                    <h2>Articles in {escape_html(page_h1)}</h2>
                    <p>Evidence-based guides, symptoms checklists, and clinical advice.</p>
                </div>
                <div class="articles-grid">
{articles_content}
                </div>
{app_cta_html}
            </div>
        </section>
    </main>

{footer_html}

    <script>
        (function () {{
            var toggle = document.querySelector('.mobile-menu');
            var nav = document.querySelector('.nav-links');
            var megaTrigger = document.querySelector('.mega-menu-trigger');
            var navMenuHasSub = document.querySelector('.nav-item-has-menu');

            if (toggle && nav) {{
                function setOpen(open) {{
                    nav.classList.toggle('open', open);
                    toggle.classList.toggle('open', open);
                    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
                }}

                toggle.addEventListener('click', function () {{
                    setOpen(!nav.classList.contains('open'));
                }});

                toggle.addEventListener('keydown', function (e) {{
                    if (e.key === 'Enter' || e.key === ' ') {{
                        e.preventDefault();
                        setOpen(!nav.classList.contains('open'));
                    }}
                }});
            }}

            if (megaTrigger && navMenuHasSub) {{
                megaTrigger.addEventListener('click', function (e) {{
                    if (window.innerWidth <= 900) {{
                        e.preventDefault();
                        navMenuHasSub.classList.toggle('mobile-open');
                        var expanded = navMenuHasSub.classList.contains('mobile-open');
                        megaTrigger.setAttribute('aria-expanded', expanded ? 'true' : 'false');
                    }}
                }});

                document.addEventListener('keydown', function (e) {{
                    if (e.key === 'Escape') {{
                        navMenuHasSub.classList.remove('mobile-open');
                        var mm = document.getElementById('blogMegaMenu');
                        if (mm) mm.classList.remove('is-open');
                        megaTrigger.setAttribute('aria-expanded', 'false');
                    }}
                }});
            }}
        }})();
    </script>
</body>
</html>"""

def render_post_page(post, category, subcategory, taxonomy, visible_categories, all_posts):
    post_id = post["id"]
    cat_slug = category["slug"]
    sub_slug = subcategory["slug"] if subcategory else None

    crumbs = [
        ("Home", "/"),
        ("Blog", "/blog"),
        (category["name"], f"/blog/{cat_slug}")
    ]
    if subcategory:
        crumbs.append((subcategory["name"], f"/blog/{cat_slug}/{sub_slug}"))
    crumbs.append((post["title"], None))

    breadcrumbs_html, breadcrumbs_json_ld = build_breadcrumbs_html(crumbs)

    # More in category posts (3-4 posts, prefer same subcategory, then category, then others)
    same_sub = [p for p in all_posts if p["id"] != post_id and p["category"] == cat_slug and p.get("subcategory") == sub_slug]
    same_cat = [p for p in all_posts if p["id"] != post_id and p["category"] == cat_slug and p not in same_sub]
    others = [p for p in all_posts if p["id"] != post_id and p not in same_sub and p not in same_cat]

    related_posts = (same_sub + same_cat + others)[:3]
    related_cards = []
    for rp in related_posts:
        related_cards.append(build_article_card_html(rp, category["name"]))

    header_html = build_header_html("blog", taxonomy, visible_categories)
    footer_html = build_footer_html(visible_categories)
    app_cta_html = build_app_cta_html()

    canonical_url = f"{SITE_URL}/blog/{post_id}"
    img_url = f"{SITE_URL}/{post['image']}" if not post['image'].startswith("http") else post['image']

    meta_title = post.get("metaTitle") or f"{post['title']} | MiGynae"
    meta_desc = post.get("metaDescription") or post["excerpt"]
    if len(meta_desc) > 155:
        meta_desc = meta_desc[:152] + "..."
    image_alt = post.get("imageAlt") or post["title"]

    article_schema = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post.get("metaTitle", post["title"]),
        "description": meta_desc,
        "image": img_url,
        "datePublished": post["date"],
        "dateModified": post["date"],
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": canonical_url
        },
        "author": {
            "@type": "Physician",
            "name": post.get("medicalReviewer", "Dr. Shuchita Batra, MBBS, MD (Obstetrics & Gynaecology)")
        },
        "publisher": {
            "@type": "Organization",
            "name": "MiGynae",
            "url": SITE_URL,
            "logo": {
                "@type": "ImageObject",
                "url": f"{SITE_URL}/favicon-180.png"
            }
        }
    }

    faq_schema_script = ""
    if post.get("faqs"):
        faq_schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": q["question"],
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": q["answer"]
                    }
                }
                for q in post["faqs"]
            ]
        }
        faq_schema_script = f"""    <script type="application/ld+json">
{json.dumps(faq_schema, indent=4)}
    </script>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <base href="/">
    <meta charset="UTF-8">
    <script>
      (function () {{
        var p = window.location.pathname;
        if (p.endsWith('.html')) {{
          var c = p.replace(/\\.html$/, '');
          if (c === '/index' || c.endsWith('/index')) c = c.slice(0, -5) || '/';
          window.location.replace(c + window.location.search + window.location.hash);
        }}
      }})();
    </script>

    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-YRTYHVLS8B"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', 'G-YRTYHVLS8B');
    </script>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" href="/favicon.ico" sizes="any">
    <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16.png">
    <link rel="apple-touch-icon" sizes="180x180" href="/favicon-180.png">
    <title>{escape_html(meta_title)}</title>
    <meta name="description" content="{escape_html(meta_desc)}">
    <link rel="canonical" href="{canonical_url}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="{canonical_url}">
    <meta property="og:title" content="{escape_html(meta_title)}">
    <meta property="og:description" content="{escape_html(meta_desc)}">
    <meta property="og:image" content="{img_url}">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{escape_html(meta_title)}">
    <meta name="twitter:description" content="{escape_html(meta_desc)}">
    <script type="application/ld+json">
{breadcrumbs_json_ld}
    </script>
    <script type="application/ld+json">
{json.dumps(article_schema, indent=4)}
    </script>
{faq_schema_script}
    <link rel="stylesheet" href="css/index.min.css">
    <link rel="stylesheet" href="css/landing.min.css">
    <link rel="stylesheet" href="css/blog-redesign.css">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .post-banner {{
            width: 100%;
            max-height: 440px;
            object-fit: cover;
            border-radius: 20px;
            margin: 20px 0 30px;
            background: #f8f9fa;
        }}
        .post-content-wrap {{
            max-width: 820px;
            margin: 0 auto;
            background: #ffffff;
            padding: 30px 20px 60px;
        }}
        .post-title {{
            font-size: 2.5rem;
            font-weight: 800;
            color: #2c3e50;
            line-height: 1.25;
            margin: 16px 0 20px;
        }}
        .post-body {{
            font-size: 1.1rem;
            line-height: 1.8;
            color: #374151;
            margin-top: 30px;
        }}
        .post-body h2 {{
            font-size: 1.75rem;
            color: #1f2937;
            margin: 36px 0 16px;
        }}
        .post-body h3 {{
            font-size: 1.35rem;
            color: #374151;
            margin: 28px 0 12px;
        }}
        .post-body p {{
            margin-bottom: 20px;
        }}
        .post-body ul {{
            margin-bottom: 24px;
            padding-left: 24px;
        }}
        .post-body li {{
            margin-bottom: 10px;
        }}
    </style>
</head>
<body class="blog-page">
{header_html}

    <main style="padding-top: 90px;">
        {breadcrumbs_html}

        <article class="post-content-wrap">
            <div class="post-meta-top">
                <a href="/blog/{category['slug']}" class="category-badge">{escape_html(category['name'])}</a>
                <span style="font-size: 14px; color: #9ca3af; margin-left: 12px;">
                    <i class="far fa-calendar-alt"></i> {format_date(post['date'])} · <i class="far fa-clock"></i> {escape_html(post.get('readTime', '8 min read'))}
                </span>
            </div>

            <h1 class="post-title">{escape_html(post['title'])}</h1>

            <div class="medical-reviewer-banner">
                <i class="fas fa-user-md"></i>
                <span>Medically reviewed by {escape_html(post.get('medicalReviewer', 'Dr. Shuchita Batra, MBBS, MD (Obstetrics & Gynaecology)'))}</span>
            </div>

            <img src="{post['image']}" alt="{escape_html(image_alt)}" class="post-banner" width="820" height="440">

            <div class="post-body">
                {post['content']}
            </div>

            <section class="more-in-category-section">
                <h2 class="more-in-category-title">More in {escape_html(category['name'])}</h2>
                <div class="articles-grid">
                    {"".join(related_cards)}
                </div>
            </section>

{app_cta_html}
        </article>
    </main>

{footer_html}

    <script>
        (function () {{
            var toggle = document.querySelector('.mobile-menu');
            var nav = document.querySelector('.nav-links');
            var megaTrigger = document.querySelector('.mega-menu-trigger');
            var navMenuHasSub = document.querySelector('.nav-item-has-menu');

            if (toggle && nav) {{
                function setOpen(open) {{
                    nav.classList.toggle('open', open);
                    toggle.classList.toggle('open', open);
                    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
                }}

                toggle.addEventListener('click', function () {{
                    setOpen(!nav.classList.contains('open'));
                }});

                toggle.addEventListener('keydown', function (e) {{
                    if (e.key === 'Enter' || e.key === ' ') {{
                        e.preventDefault();
                        setOpen(!nav.classList.contains('open'));
                    }}
                }});
            }}

            if (megaTrigger && navMenuHasSub) {{
                megaTrigger.addEventListener('click', function (e) {{
                    if (window.innerWidth <= 900) {{
                        e.preventDefault();
                        navMenuHasSub.classList.toggle('mobile-open');
                        var expanded = navMenuHasSub.classList.contains('mobile-open');
                        megaTrigger.setAttribute('aria-expanded', expanded ? 'true' : 'false');
                    }}
                }});

                document.addEventListener('keydown', function (e) {{
                    if (e.key === 'Escape') {{
                        navMenuHasSub.classList.remove('mobile-open');
                        var mm = document.getElementById('blogMegaMenu');
                        if (mm) mm.classList.remove('is-open');
                        megaTrigger.setAttribute('aria-expanded', 'false');
                    }}
                }});
            }}
        }})();
    </script>
</body>
</html>"""

def render_guide_page(post, category, subcategory, taxonomy, visible_categories, all_posts, guides_meta):
    """
    Renders a migrated guide page at /blog/<slug>.
    Preserves the original page's body content (custom styles, full HTML, schemas)
    but adds the new canonical URL, og:url, breadcrumbs, category badge, and
    "More in Category" block using the shared nav/footer.
    """
    post_id = post["id"]
    cat_slug = category["slug"]
    sub_slug = subcategory["slug"] if subcategory else None

    crumbs = [
        ("Home", "/"),
        ("Blog", "/blog"),
        (category["name"], f"/blog/{cat_slug}")
    ]
    if subcategory:
        crumbs.append((subcategory["name"], f"/blog/{cat_slug}/{sub_slug}"))
    crumbs.append((post["title"], None))

    breadcrumbs_html, breadcrumbs_json_ld = build_breadcrumbs_html(crumbs)

    # Related posts
    same_sub = [p for p in all_posts if p["id"] != post_id and p["category"] == cat_slug and p.get("subcategory") == sub_slug]
    same_cat = [p for p in all_posts if p["id"] != post_id and p["category"] == cat_slug and p not in same_sub]
    others = [p for p in all_posts if p["id"] != post_id and p not in same_sub and p not in same_cat]
    related_posts = (same_sub + same_cat + others)[:3]
    related_cards = [build_article_card_html(rp, category["name"]) for rp in related_posts]

    header_html = build_header_html("blog", taxonomy, visible_categories)
    footer_html = build_footer_html(visible_categories)
    app_cta_html = build_app_cta_html()

    canonical_url = f"{SITE_URL}/blog/{post_id}"
    img_url = f"{SITE_URL}/{post['image']}" if not post["image"].startswith("http") else post["image"]

    meta_desc = post["excerpt"]
    if len(meta_desc) > 155:
        meta_desc = meta_desc[:152] + "..."

    # Guide-specific metadata (custom styles + original schemas with updated URLs)
    meta = guides_meta.get(post_id, {})
    custom_styles = meta.get("custom_styles", "")
    custom_schemas = meta.get("custom_schemas", [])

    # Build extra schema tags (original schemas, URL-updated)
    extra_schema_tags = ""
    for schema in custom_schemas:
        # Update canonical url/id fields in schema
        if isinstance(schema, dict):
            schema_str = json.dumps(schema, indent=4)
        else:
            schema_str = json.dumps(schema, indent=4)
        extra_schema_tags += f'\n    <script type="application/ld+json">\n{schema_str}\n    </script>'

    custom_style_tag = f"\n    <style>\n{custom_styles}\n    </style>" if custom_styles else ""

    # Category badge + date line
    date_str = format_date(post.get("date", ""))
    read_time = escape_html(post.get("readTime", "8 min read"))

    # More in category section
    more_section = ""
    if related_cards:
        more_section = f"""
        <section class="more-in-category-section" style="margin: 40px auto; max-width: 1120px; padding: 0 20px;">
            <h2 class="more-in-category-title">More in {escape_html(category["name"])}</h2>
            <div class="articles-grid">
                {"".join(related_cards)}
            </div>
        </section>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <base href="/">
    <meta charset="UTF-8">
    <script>
      (function () {{
        var p = window.location.pathname;
        if (p.endsWith('.html')) {{
          var c = p.replace(/\\.html$/, '');
          if (c === '/index' || c.endsWith('/index')) c = c.slice(0, -5) || '/';
          window.location.replace(c + window.location.search + window.location.hash);
        }}
      }})();
    </script>

    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-YRTYHVLS8B"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', 'G-YRTYHVLS8B');
    </script>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" href="/favicon.ico" sizes="any">
    <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16.png">
    <link rel="apple-touch-icon" sizes="180x180" href="/favicon-180.png">
    <title>{escape_html(post["title"])} | MiGynae</title>
    <meta name="description" content="{escape_html(meta_desc)}">
    <link rel="canonical" href="{canonical_url}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="{canonical_url}">
    <meta property="og:title" content="{escape_html(post["title"])} | MiGynae">
    <meta property="og:description" content="{escape_html(meta_desc)}">
    <meta property="og:image" content="{img_url}">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{escape_html(post["title"])} | MiGynae">
    <meta name="twitter:description" content="{escape_html(meta_desc)}">
    <script type="application/ld+json">
{breadcrumbs_json_ld}
    </script>{extra_schema_tags}{custom_style_tag}
    <link rel="stylesheet" href="css/index.min.css">
    <link rel="stylesheet" href="css/landing.min.css">
    <link rel="stylesheet" href="css/blog-redesign.css">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body class="blog-page">
{header_html}

    <main style="padding-top: 90px;">
        {breadcrumbs_html}

        <div class="post-content-wrap" style="max-width: 820px; margin: 0 auto; padding: 20px 20px 40px;">
            <div class="post-meta-top" style="margin-bottom: 16px;">
                <a href="/blog/{category["slug"]}" class="category-badge">{escape_html(category["name"])}</a>
                <span style="font-size: 14px; color: #9ca3af; margin-left: 12px;">
                    <i class="far fa-calendar-alt"></i> {date_str} · <i class="far fa-clock"></i> {read_time}
                </span>
            </div>
        </div>

        <div class="post-body" style="max-width: 820px; margin: 0 auto; padding: 0 20px 20px;">
            {post.get("content", "")}
        </div>

{more_section}
{app_cta_html}
    </main>

{footer_html}

    <script>
        (function () {{
            var toggle = document.querySelector('.mobile-menu');
            var nav = document.querySelector('.nav-links');
            var megaTrigger = document.querySelector('.mega-menu-trigger');
            var navMenuHasSub = document.querySelector('.nav-item-has-menu');

            if (toggle && nav) {{
                function setOpen(open) {{
                    nav.classList.toggle('open', open);
                    toggle.classList.toggle('open', open);
                    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
                }}

                toggle.addEventListener('click', function () {{
                    setOpen(!nav.classList.contains('open'));
                }});

                toggle.addEventListener('keydown', function (e) {{
                    if (e.key === 'Enter' || e.key === ' ') {{
                        e.preventDefault();
                        setOpen(!nav.classList.contains('open'));
                    }}
                }});
            }}

            if (megaTrigger && navMenuHasSub) {{
                megaTrigger.addEventListener('click', function (e) {{
                    if (window.innerWidth <= 900) {{
                        e.preventDefault();
                        navMenuHasSub.classList.toggle('mobile-open');
                        var expanded = navMenuHasSub.classList.contains('mobile-open');
                        megaTrigger.setAttribute('aria-expanded', expanded ? 'true' : 'false');
                    }}
                }});

                document.addEventListener('keydown', function (e) {{
                    if (e.key === 'Escape') {{
                        navMenuHasSub.classList.remove('mobile-open');
                        var mm = document.getElementById('blogMegaMenu');
                        if (mm) mm.classList.remove('is-open');
                        megaTrigger.setAttribute('aria-expanded', 'false');
                    }}
                }});
            }}
        }})();
    </script>
</body>
</html>"""


def update_legacy_post(file_path, taxonomy, visible_categories):
    """
    Updates legacy post file (e.g. blog/9th-month-nutrition-guide.html) with the
    new header mega-menu, footer, and blog-redesign.css WITHOUT changing its
    existing body, meta tags, or reviewer line.
    """
    if not os.path.exists(file_path):
        return

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Ensure blog-redesign.css is included
    if "css/blog-redesign.css" not in content:
        content = content.replace('</head>', '    <link rel="stylesheet" href="css/blog-redesign.css">\n</head>')

    # Replace <header>...</header> with new header
    header_html = build_header_html("blog", taxonomy, visible_categories)
    content = re.sub(r'<header>.*?</header>', header_html, content, flags=re.DOTALL)

    # Replace <footer>...</footer> with new footer
    footer_html = build_footer_html(visible_categories)
    content = re.sub(r'<footer>.*?</footer>', footer_html, content, flags=re.DOTALL)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

def update_standalone_page_nav(file_path, active_tab, taxonomy, visible_categories):
    """
    Updates header and footer on standalone root pages like index.html, features.html, etc.
    """
    if not os.path.exists(file_path):
        return

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Ensure blog-redesign.css is included
    if "css/blog-redesign.css" not in content:
        content = content.replace('</head>', '    <link rel="stylesheet" href="css/blog-redesign.css">\n</head>')

    header_html = build_header_html(active_tab, taxonomy, visible_categories)
    content = re.sub(r'<header>.*?</header>', header_html, content, flags=re.DOTALL)

    footer_html = build_footer_html(visible_categories)
    content = re.sub(r'<footer>.*?</footer>', footer_html, content, flags=re.DOTALL)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

def write_dual_file(path_single, path_index, html_content):
    """
    Writes both blog/<slug>.html and blog/<slug>/index.html for universal routing.
    """
    os.makedirs(os.path.dirname(path_single), exist_ok=True)
    with open(path_single, "w", encoding="utf-8") as f:
        f.write(html_content)

    os.makedirs(os.path.dirname(path_index), exist_ok=True)
    with open(path_index, "w", encoding="utf-8") as f:
        f.write(html_content)

def build_sitemap_xml(urls, today):
    """Build a standard urlset XML string from list of (path, freq, priority) tuples."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, freq, prio in urls:
        lines.append(
            f'  <url><loc>{SITE_URL}{path}</loc>'
            f'<lastmod>{today}</lastmod>'
            f'<changefreq>{freq}</changefreq>'
            f'<priority>{prio}</priority></url>'
        )
    lines.append('</urlset>')
    return "\n".join(lines) + "\n"


def update_sitemap(visible_categories, taxonomy, posts):
    today = datetime.now().strftime("%Y-%m-%d")

    # -----------------------------------------------------------------------
    # sitemap-pages.xml — only the 8 canonical page URLs (NO redirected URLs)
    # -----------------------------------------------------------------------
    page_urls = [
        ("/", "weekly", "1.0"),
        ("/features", "monthly", "0.8"),
        ("/how-it-works", "monthly", "0.8"),
        ("/resources", "weekly", "0.8"),
        ("/guides", "monthly", "0.8"),
        ("/blog", "weekly", "0.9"),
        ("/privacy-policy", "yearly", "0.3"),
        ("/terms-of-service", "yearly", "0.3"),
    ]
    pages_xml = build_sitemap_xml(page_urls, today)
    with open(os.path.join(WORKSPACE_DIR, "sitemap-pages.xml"), "w", encoding="utf-8") as f:
        f.write(pages_xml)
    print(f"Written sitemap-pages.xml with {len(page_urls)} URLs.")

    # -----------------------------------------------------------------------
    # sitemap-blog.xml — /blog index + visible categories + sub-categories + all posts
    # -----------------------------------------------------------------------
    blog_urls = [("/blog", "weekly", "0.9")]

    # Visible categories
    for c in visible_categories:
        blog_urls.append((f"/blog/{c['slug']}", "weekly", "0.8"))
        for s in c.get("subcategories", []):
            sub_posts = [p for p in posts if p["category"] == c["slug"] and p.get("subcategory") == s["slug"]]
            if sub_posts:
                blog_urls.append((f"/blog/{c['slug']}/{s['slug']}", "weekly", "0.7"))

    # All posts (including migrated guides — they are now at /blog/<slug>)
    for p in posts:
        blog_urls.append((f"/blog/{p['id']}", "monthly", "0.8"))

    # Legacy blog posts (old ones not in blogs.json)
    legacy_posts = [
        "9th-month-nutrition-guide",
        "first-trimester-diet-guide",
        "nausea-friendly-diet",
        "pregnancy-101",
        "pregnancy-exercises"
    ]
    post_ids = {p["id"] for p in posts}
    for lp in legacy_posts:
        if lp not in post_ids:
            blog_urls.append((f"/blog/{lp}", "monthly", "0.6"))

    blog_xml = build_sitemap_xml(blog_urls, today)
    with open(os.path.join(WORKSPACE_DIR, "sitemap-blog.xml"), "w", encoding="utf-8") as f:
        f.write(blog_xml)
    print(f"Written sitemap-blog.xml with {len(blog_urls)} URLs.")

    # -----------------------------------------------------------------------
    # sitemap.xml — sitemap index referencing both
    # -----------------------------------------------------------------------
    sitemap_index = f"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>{SITE_URL}/sitemap-pages.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>
  <sitemap>
    <loc>{SITE_URL}/sitemap-blog.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>
</sitemapindex>
"""
    with open(os.path.join(WORKSPACE_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sitemap_index)
    print("Written sitemap.xml (sitemap index referencing sitemap-pages.xml + sitemap-blog.xml).")

def main():
    print("Starting MiGynae Blog Static Build...")
    tax_path = os.path.join(WORKSPACE_DIR, "blog_taxonomy.json")
    blogs_path = os.path.join(WORKSPACE_DIR, "blogs.json")
    guides_meta_path = os.path.join(WORKSPACE_DIR, "guides_metadata.json")

    taxonomy = load_json(tax_path)
    posts = load_json(blogs_path)

    # Load guide metadata (custom styles + schemas extracted from original HTMLs)
    if os.path.exists(guides_meta_path):
        guides_meta = load_json(guides_meta_path)
        print(f"Loaded guides_metadata.json with {len(guides_meta)} guide entries.")
    else:
        guides_meta = {}
        print("WARNING: guides_metadata.json not found — guide pages will render without custom styles.")

    # Validate & Collision Protection
    categories_by_slug, subcategory_slugs = validate_and_check_collisions(taxonomy, posts)

    # Determine visible vs empty categories
    visible_categories = []
    empty_categories = []

    for c in taxonomy["categories"]:
        c_slug = c["slug"]
        c_posts = [p for p in posts if p["category"] == c_slug]
        if len(c_posts) > 0 or c.get("showWhenEmpty", False):
            visible_categories.append(c)
        else:
            empty_categories.append(c)

    print(f"Visible categories ({len(visible_categories)}): {[c['slug'] for c in visible_categories]}")
    print(f"Empty categories ({len(empty_categories)}): {[c['slug'] for c in empty_categories]}")

    # 1. Render Blog Index
    blog_index_html = render_blog_index(taxonomy, visible_categories, posts, current_page=1)
    # Write to blog.html and blog/index.html
    with open(os.path.join(WORKSPACE_DIR, "blog.html"), "w", encoding="utf-8") as f:
        f.write(blog_index_html)
    with open(os.path.join(WORKSPACE_DIR, "blog", "index.html"), "w", encoding="utf-8") as f:
        f.write(blog_index_html)
    print("Rendered Blog Index: blog.html & blog/index.html")

    # If >12 posts, render page 2
    if len(posts) > POSTS_PER_PAGE:
        blog_p2_html = render_blog_index(taxonomy, visible_categories, posts, current_page=2)
        write_dual_file(
            os.path.join(WORKSPACE_DIR, "blog", "page", "2.html"),
            os.path.join(WORKSPACE_DIR, "blog", "page", "2", "index.html"),
            blog_p2_html
        )
        print("Rendered Blog Index page 2.")

    # 2. Render Categories & Subcategories
    for c in taxonomy["categories"]:
        c_slug = c["slug"]
        # Render top-level category page
        cat_html = render_category_page(c, taxonomy, visible_categories, posts)
        write_dual_file(
            os.path.join(WORKSPACE_DIR, "blog", f"{c_slug}.html"),
            os.path.join(WORKSPACE_DIR, "blog", c_slug, "index.html"),
            cat_html
        )

        # Render sub-categories
        for sub in c.get("subcategories", []):
            s_slug = sub["slug"]
            sub_html = render_category_page(c, taxonomy, visible_categories, posts, subcategory_filter=sub)
            write_dual_file(
                os.path.join(WORKSPACE_DIR, "blog", c_slug, f"{s_slug}.html"),
                os.path.join(WORKSPACE_DIR, "blog", c_slug, s_slug, "index.html"),
                sub_html
            )

    print(f"Rendered {len(taxonomy['categories'])} category pages and all subcategory pages.")

    # 3. Render Post Pages (guides use render_guide_page, articles use render_post_page)
    sub_map = {}
    for c in taxonomy["categories"]:
        for s in c.get("subcategories", []):
            sub_map[(c["slug"], s["slug"])] = s

    guide_count = 0
    article_count = 0
    for p in posts:
        cat = categories_by_slug[p["category"]]
        sub = sub_map.get((p["category"], p.get("subcategory")))

        if p.get("format") == "guide" and p["id"] in GUIDE_SLUGS:
            # Migrated guide — use custom renderer
            post_html = render_guide_page(p, cat, sub, taxonomy, visible_categories, posts, guides_meta)
            guide_count += 1
        else:
            # Regular article
            post_html = render_post_page(p, cat, sub, taxonomy, visible_categories, posts)
            article_count += 1

        # 1. Root blog level: /blog/<id>
        write_dual_file(
            os.path.join(WORKSPACE_DIR, "blog", f"{p['id']}.html"),
            os.path.join(WORKSPACE_DIR, "blog", p["id"], "index.html"),
            post_html
        )

        # 2. Respective category slug: /blog/<category-slug>/<id>
        write_dual_file(
            os.path.join(WORKSPACE_DIR, "blog", cat["slug"], f"{p['id']}.html"),
            os.path.join(WORKSPACE_DIR, "blog", cat["slug"], p["id"], "index.html"),
            post_html
        )

        # 3. Respective subcategory slug: /blog/<category-slug>/<subcategory-slug>/<id>
        if sub:
            write_dual_file(
                os.path.join(WORKSPACE_DIR, "blog", cat["slug"], sub["slug"], f"{p['id']}.html"),
                os.path.join(WORKSPACE_DIR, "blog", cat["slug"], sub["slug"], p["id"], "index.html"),
                post_html
            )

    print(f"Rendered {guide_count} guide pages and {article_count} article pages ({guide_count + article_count} total).")

    # 4. Update Legacy Blog Post Pages (the 5 old blog posts not in taxonomy)
    legacy_files = [
        "9th-month-nutrition-guide.html",
        "first-trimester-diet-guide.html",
        "nausea-friendly-diet.html",
        "pregnancy-101.html",
        "pregnancy-exercises.html"
    ]
    for lf in legacy_files:
        lp_path = os.path.join(WORKSPACE_DIR, "blog", lf)
        update_legacy_post(lp_path, taxonomy, visible_categories)
    print("Updated legacy posts with new navigation.")

    # 5. Update Standalone Core Pages (Header & Footer)
    core_pages = [
        ("index.html", "home"),
        ("features.html", "features"),
        ("how-it-works.html", "how-it-works"),
        ("resources.html", "resources"),
        ("guides.html", "guides"),
        ("privacy-policy.html", ""),
        ("terms-of-service.html", "")
    ]
    for filename, active_tab in core_pages:
        update_standalone_page_nav(os.path.join(WORKSPACE_DIR, filename), active_tab, taxonomy, visible_categories)
    print("Updated core landing pages with new header mega-menu and footer topics.")

    # 6. Update Sitemaps (split into sitemap-pages.xml + sitemap-blog.xml + index)
    update_sitemap(visible_categories, taxonomy, posts)

    # 7. Generate Redirect Stubs from redirects.json
    redirects_path = os.path.join(WORKSPACE_DIR, "redirects.json")
    if os.path.exists(redirects_path):
        redirects = load_json(redirects_path)
        stub_template = """<!DOCTYPE html>
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
    <p>Redirecting to <a href="{new_path}">{new_path}</a>...</p>
</body>
</html>"""
        for old_path, new_path in redirects.items():
            rel_old = old_path.lstrip("/")
            if rel_old.startswith("blog/"):
                slug = rel_old[5:]
                path_single = os.path.join(WORKSPACE_DIR, "blog", f"{slug}.html")
                path_index = os.path.join(WORKSPACE_DIR, "blog", slug, "index.html")
            else:
                path_single = os.path.join(WORKSPACE_DIR, f"{rel_old}.html")
                path_index = os.path.join(WORKSPACE_DIR, rel_old, "index.html")
            stub_content = stub_template.format(new_url=f"{SITE_URL}{new_path}", new_path=new_path)
            write_dual_file(path_single, path_index, stub_content)
        print(f"Generated {len(redirects)} redirect stubs from redirects.json.")

    print("\nMiGynae Blog Static Build Complete Successfully!")
    print(f"  Posts rendered: {len(posts)} ({guide_count} guides + {article_count} articles)")
    print(f"  Categories rendered: {len(taxonomy['categories'])} ({len(visible_categories)} visible, {len(empty_categories)} empty/hidden)")
    print(f"  Sitemaps: sitemap.xml (index) -> sitemap-pages.xml ({8} URLs) + sitemap-blog.xml")

if __name__ == "__main__":
    main()
