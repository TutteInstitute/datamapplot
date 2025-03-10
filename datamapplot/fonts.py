from dataclasses import dataclass
import re
import requests
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
            return FontCollection(str(api_response.content))
        return FontCollection("")
    except BaseException:
        warn(f"Failed in getting google-font {fontname}; using fallback ...")
        return FontCollection("")


@dataclass
class Font:
    url: str

    def fetch(self):
        return requests.get(self.url).content


@dataclass
class FontCollection:
    content: str

    def __iter__(self):
        if self.content:
            font_urls = re.findall(r"(https?://[^\)]+)", self.content)
            for font_url in font_urls:
                yield Font(font_url)
