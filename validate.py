#!/usr/bin/env python3
"""
CupStore repo validation script.
Usage: python3 validate.py [--check-urls]
"""
import json
import sys
import re
import os
import argparse
import urllib.request

REQUIRED_MOD_FIELDS  = ["id", "name", "author", "version", "description", "download", "type"]
REQUIRED_GAME_FIELDS = ["name", "titleIds"]
VALID_TYPES          = ["mod", "modpack"]
ID_PATTERN           = re.compile(r'^[a-z0-9\-_]+$')
URL_PATTERN          = re.compile(r'^https?://.+\..+')

errors   = []
warnings = []

def err(msg):  errors.append(msg)
def warn(msg): warnings.append(msg)

def validate_url(url, field, context):
    if not URL_PATTERN.match(url):
        err(f"{context}: {field} is not a valid URL: {url!r}")
        return False
    return True

def check_url_reachable(url, context):
    try:
        req = urllib.request.Request(url, method='HEAD')
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        warn(f"{context}: URL not reachable: {url} ({e})")

def validate_mod(mod, game_name, seen_ids, check_urls):
    ctx = f"Game '{game_name}' / Mod '{mod.get('id', '?')}'"

    # Required fields
    for f in REQUIRED_MOD_FIELDS:
        if f not in mod:
            err(f"{ctx}: missing required field '{f}'")

    mod_id = mod.get("id", "")

    # ID format
    if mod_id and not ID_PATTERN.match(mod_id):
        err(f"{ctx}: id '{mod_id}' contains invalid characters (only a-z, 0-9, - _ allowed)")

    # ID uniqueness (global)
    if mod_id in seen_ids:
        err(f"{ctx}: duplicate id '{mod_id}' (also in '{seen_ids[mod_id]}')")
    else:
        seen_ids[mod_id] = game_name

    # Type
    if mod.get("type") not in VALID_TYPES:
        err(f"{ctx}: type must be one of {VALID_TYPES}, got {mod.get('type')!r}")

    # URLs
    if "download" in mod: validate_url(mod["download"], "download", ctx)
    if "thumbnail" in mod: validate_url(mod["thumbnail"], "thumbnail", ctx)
    for i, s in enumerate(mod.get("screenshots", [])):
        validate_url(s, f"screenshots[{i}]", ctx)

    if check_urls:
        if "download" in mod: check_url_reachable(mod["download"], ctx)

    # Optional field types
    if "fileSize" in mod and not isinstance(mod["fileSize"], int):
        err(f"{ctx}: fileSize must be an integer (bytes)")
    if "tags" in mod and not isinstance(mod["tags"], list):
        err(f"{ctx}: tags must be a list of strings")
    if "requirements" in mod and not isinstance(mod["requirements"], list):
        err(f"{ctx}: requirements must be a list of strings")

def validate_game(game_data, game_path, seen_ids, check_urls):
    name = game_data.get("name", game_path)

    # titleIds (support both camelCase and snake_case)
    if "titleIds" not in game_data and "title_ids" not in game_data:
        err(f"Game '{name}': missing 'titleIds'")
    else:
        tids = game_data.get("titleIds", game_data.get("title_ids", []))
        if not tids:
            err(f"Game '{name}': titleIds is empty")

    if "mods" not in game_data or not game_data["mods"]:
        warn(f"Game '{name}': no mods defined")
        return

    for mod in game_data["mods"]:
        validate_mod(mod, name, seen_ids, check_urls)

def main():
    parser = argparse.ArgumentParser(description="Validate a CupStore repo")
    parser.add_argument("--check-urls", action="store_true", help="Check if download URLs are reachable")
    parser.add_argument("--repo", default="repo.json", help="Path to repo.json")
    args = parser.parse_args()

    if not os.path.exists(args.repo):
        print(f"ERROR: {args.repo} not found")
        sys.exit(1)

    with open(args.repo) as f:
        try:
            repo = json.load(f)
        except json.JSONDecodeError as e:
            print(f"ERROR: repo.json is invalid JSON: {e}")
            sys.exit(1)

    # Repo-level fields
    for f in ["name", "formatVersion", "games"]:
        if f not in repo:
            err(f"repo.json: missing required field '{f}'")

    seen_ids = {}

    for entry in repo.get("games", []):
        if "path" not in entry:
            err(f"repo.json: game entry missing 'path'")
            continue
        game_path = entry["path"]
        if not os.path.exists(game_path):
            err(f"repo.json: game file not found: {game_path!r}")
            continue
        with open(game_path) as f:
            try:
                game_data = json.load(f)
            except json.JSONDecodeError as e:
                err(f"{game_path}: invalid JSON: {e}")
                continue
        validate_game(game_data, game_path, seen_ids, args.check_urls)

    # Report
    if warnings:
        print(f"\n⚠  {len(warnings)} warning(s):")
        for w in warnings: print(f"   {w}")

    if errors:
        print(f"\n✗  {len(errors)} error(s):")
        for e in errors: print(f"   {e}")
        sys.exit(1)
    else:
        print(f"✓  Repo is valid ({len(seen_ids)} mods across {len(repo.get('games', []))} game(s))")
        if warnings:
            sys.exit(0)

if __name__ == "__main__":
    main()
