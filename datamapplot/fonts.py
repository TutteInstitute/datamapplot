from dataclasses import dataclass
import re
import requests
from urllib.parse import urlparse
from warnings import warn


class GoogleAPIUnreachable(Warning):
    pass


def can_reach_google_fonts(timeout: float = 5.0) -> bool:
    try:
        response = requests.get(
            "https://fonts.googleapis.com/css?family=Roboto", timeout=timeout
        )
        return response.ok
    except requests.RequestException:
        return False


def get_api_fontname(fontname):
    return fontname.replace(" ", "+")


def query_google_fonts(fontname):
    try:
        api_fontname = get_api_fontname(fontname)
        api_response = requests.get(
            f"https://fonts.googleapis.com/css?family={api_fontname}:black,bold,regular,light"
        )
        if api_response.ok:
            return FontCollection(api_response.text)
        return FontCollection("")
    except BaseException:
        warn(f"Failed in getting google-font {fontname}; using fallback ...")
        return FontCollection("")


TRUSTED_DOMAINS = {"fonts.googleapis.com", "fonts.gstatic.com"}


def _is_trusted_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and parsed.netloc in TRUSTED_DOMAINS
    except Exception:
        return False


@dataclass
class Font:
    url: str

    def fetch(self):
        if not _is_trusted_url(self.url):
            raise ValueError(f"Untrusted font URL: {self.url}")
        return requests.get(self.url).content


@dataclass
class FontCollection:
    content: str

    def __iter__(self):
        if self.content:
            font_urls = re.findall(r"(https?://[^\)]+)", self.content)
            for font_url in font_urls:
                yield Font(font_url)
