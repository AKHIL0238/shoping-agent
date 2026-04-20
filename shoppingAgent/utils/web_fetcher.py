"""
Web Fetcher — gives the agent real web browsing capability.

  search_web()   — searches the general web via SerpAPI google engine
                   (finds reviews, comparisons, specs, YouTube, tech blogs)
  fetch_url()    — fetches and parses any URL, returns clean readable text
"""
from __future__ import annotations
import os
import re
import requests
from typing import Dict, List


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def search_web(query: str, num_results: int = 6) -> List[Dict]:
    """
    Search the general web via SerpAPI's google engine.
    Returns a list of {title, url, snippet} dicts.
    Useful for finding product reviews, expert comparisons, spec sheets.
    """
    api_key = os.getenv("SERPAPI_API_KEY", "")
    if not api_key:
        return []
    try:
        resp = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine":  "google",
                "q":       query,
                "hl":      "en",
                "gl":      "in",
                "num":     num_results,
                "api_key": api_key,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for r in data.get("organic_results", [])[:num_results]:
            results.append({
                "title":   r.get("title", ""),
                "url":     r.get("link", ""),
                "snippet": r.get("snippet", ""),
            })
        return results
    except Exception:
        return []


def fetch_url(url: str, max_chars: int = 4000) -> str:
    """
    Fetch a web page and return its clean text content.
    Strips scripts, styles, nav elements. Falls back to regex if bs4 is absent.
    """
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=12)
        resp.raise_for_status()
        html = resp.text

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header",
                              "aside", "form", "noscript", "iframe"]):
                tag.decompose()
            text = soup.get_text(separator=" ", strip=True)
        except ImportError:
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()

        # Collapse whitespace and truncate
        text = re.sub(r"\s{3,}", "  ", text)
        return text[:max_chars]

    except requests.exceptions.Timeout:
        return "Error: request timed out."
    except requests.exceptions.HTTPError as exc:
        return f"Error: HTTP {exc.response.status_code} for {url}"
    except Exception as exc:
        return f"Error fetching page: {exc}"
