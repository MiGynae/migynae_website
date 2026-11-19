#!/usr/bin/env python3
"""
Test Suite: Collision Protection and Validation Checks
=====================================================
Demonstrates that build_blog fails correctly when:
1. A category slug collides with a post slug.
2. A category slug collides with a reserved route.
3. A post has a missing or unknown category.
"""

import copy
from build_blog import validate_and_check_collisions, load_json, RESERVED_ROUTES

def test_slug_collision():
    print("--- Test 1: Category slug collides with Post slug ---")
    taxonomy = load_json("blog_taxonomy.json")
    posts = load_json("blogs.json")

    # Deliberately create a conflict: make a post slug identical to a category slug
    bad_posts = copy.deepcopy(posts)
    bad_posts[0]["id"] = "getting-pregnant"  # Conflicting with category 'getting-pregnant'

    try:
        validate_and_check_collisions(taxonomy, bad_posts)
        print("FAIL: Expected RuntimeError was not raised!")
        return False
    except RuntimeError as e:
        print(f"SUCCESS: Caught expected collision error:\n  -> {e}")

    print("\n--- Test 2: Category slug uses a reserved route ---")
    bad_taxonomy = copy.deepcopy(taxonomy)
    bad_taxonomy["categories"][0]["slug"] = "sitemap"  # 'sitemap' is reserved

    try:
        validate_and_check_collisions(bad_taxonomy, posts)
        print("FAIL: Expected RuntimeError was not raised!")
        return False
    except RuntimeError as e:
        print(f"SUCCESS: Caught expected reserved route error:\n  -> {e}")

    print("\n--- Test 3: Post with missing/unknown category ---")
    bad_posts2 = copy.deepcopy(posts)
    bad_posts2[0]["category"] = "unknown-nonexistent-category"

    try:
        validate_and_check_collisions(taxonomy, bad_posts2)
        print("FAIL: Expected ValueError was not raised!")
        return False
    except ValueError as e:
        print(f"SUCCESS: Caught expected unknown category error:\n  -> {e}")

    print("\nALL COLLISION & VALIDATION TESTS PASSED PERFECTLY!")
    return True

if __name__ == "__main__":
    success = test_slug_collision()
    if not success:
        exit(1)
