import base64
from collections.abc import Sequence
from dataclasses import dataclass
import json
import numpy as np
from pathlib import Path
import platformdirs
import re
import requests
from typing import Protocol, Self
from urllib.parse import urlparse

from warnings import warn

DEFAULT_URLS = [
    "https://unpkg.com/deck.gl@latest/dist.min.js",
    "https://unpkg.com/apache-arrow@latest/Arrow.es2015.min.js",
    "https://unpkg.com/d3@latest/dist/d3.min.js",
    "https://unpkg.com/jquery@3.7.1/dist/jquery.min.js",
    "https://unpkg.com/d3-cloud@1.2.7/build/d3.layout.cloud.js",
]

BASE_FONTS = [
    "Roboto",
    "Open Sans",
    "Montserrat",
    "Oswald",
    "Merriweather",
    "Merriweather Sans",
    "Playfair Display",
    "Playfair Display SC",
    "Roboto Condensed",
    "Ubuntu",
    "Cinzel",
    "Cormorant",
    "Cormorant SC",
    "Marcellus",
    "Marcellus SC",
    "Anton",
    "Anton SC",
    "Arsenal",
    "Arsenal SC",
    "Baskervville",
    "Baskervville SC",
    "Lora",
    "Quicksand",
    "Bebas Neue",
]

_DATA_DIRECTORY = platformdirs.user_data_dir("datamapplot")
DEFAULT_CACHE_FILES = {
    "javascript": f"{_DATA_DIRECTORY}/datamapplot_js_encoded.json",
    "fonts": f"{_DATA_DIRECTORY}/datamapplot_fonts_encoded.json",
}


def fetch_js_content(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    else:
        raise Exception(
            f"Failed to fetch content from {url}. Status code: {response.status_code}"
        )


def encode_js_content(content):
    return base64.b64encode(content.encode("utf-8")).decode("utf-8")


def generate_script_loader(url, encoded_content):
    parsed_url = urlparse(url)
    variable_name = f"{parsed_url.netloc.replace('.', '_')}_{parsed_url.path.split('/')[-1].replace('.', '_')}"
    return f"""
    // Base64 encoded content from {url}
    const {variable_name} = "{encoded_content}";
    loadBase64Script({variable_name});
    """


def build_js_encoded_dictionary(urls):
    js_loader_dict = {}

    for url in urls:
        try:
            content = fetch_js_content(url)
            encoded_content = encode_js_content(content)
            js_loader_dict[url] = {}
            js_loader_dict[url]["encoded_content"] = encoded_content
            parsed_url = urlparse(url)
            js_loader_dict[url][
                "name"
            ] = f"{parsed_url.netloc.replace('.', '_')}_{parsed_url.path.split('/')[-1].replace('.', '_')}"
        except Exception as e:
            print(f"Error processing {url}: {str(e)}")

    return js_loader_dict


def _parse_font_face(css_block):
    result = {}

    # Extract font-style
    style_match = re.search(r"font-style: (\w+)", css_block)
    result["style"] = style_match.group(1) if style_match else "normal"

    # Extract font-weight
    weight_match = re.search(r"font-weight: (\w+)", css_block)
    result["weight"] = weight_match.group(1) if weight_match else "400"

    # Extract unicode-range
    unicode_match = re.search(r"unicode-range: ([^;]+)", css_block)
    result["unicode_range"] = unicode_match.group(1) if unicode_match else ""

    # Extract URL and format
    url_match = re.findall(r'url\(([^)]+)\)\s+format\([\'"](\w+)[\'"]\)', css_block)[0]
    url, format_type = url_match
    result["type"] = format_type

    # Get font and encode it
    font_response = requests.get(url, timeout=10)
    if font_response.ok:
        encoded_font = base64.b64encode(font_response.content).decode("utf-8")
        result["content"] = encoded_font
    else:
        warn(f"Failed to fetch font from {url}")
        return None

    return result


def download_and_encode_font(fontname):
    api_fontname = fontname.replace(" ", "+")
    api_response = requests.get(
        f"https://fonts.googleapis.com/css?family={api_fontname}:black,extrabold,bold,demibold,semibold,medium,regular,light,thin,italic",
        timeout=10,
    )
    if api_response.ok:
        encoded_fonts = [
            font
            for css_block in re.findall(r"@font-face\s*{[^}]+}", api_response.text)
            if (font := _parse_font_face(css_block))
        ]
        return encoded_fonts
    else:
        warn(f"Failed to fetch font from Google Fonts API for {fontname}")
        return []


def cache_js_files(urls=DEFAULT_URLS, file_path=None):
    js_loader_dict = build_js_encoded_dictionary(urls)
    if file_path:
        json.dump(js_loader_dict, open(file_path, "w"))
    else:
        data_directory = platformdirs.user_data_dir("datamapplot", ensure_exists=True)
        json.dump(
            js_loader_dict, open(f"{data_directory}/datamapplot_js_encoded.json", "w")
        )


def load_js_files(file_path=None):
    if file_path:
        return json.load(open(file_path, "r"))
    else:
        data_directory = platformdirs.user_data_dir("datamapplot", ensure_exists=True)
        return json.load(open(f"{data_directory}/datamapplot_js_encoded.json", "r"))


def cache_fonts(fonts=BASE_FONTS, file_path=None):
    font_dict = {}
    for font in fonts:
        font_dict[font] = download_and_encode_font(font)

    if file_path:
        json.dump(font_dict, open(file_path, "w"))
    else:
        data_directory = platformdirs.user_data_dir("datamapplot", ensure_exists=True)
        json.dump(
            font_dict, open(f"{data_directory}/datamapplot_fonts_encoded.json", "w")
        )


def load_fonts(file_path=None):
    if file_path:
        return json.load(open(file_path, "r"))
    else:
        data_directory = platformdirs.user_data_dir("datamapplot", ensure_exists=True)
        return json.load(open(f"{data_directory}/datamapplot_fonts_encoded.json", "r"))


class Store(Protocol):
    def read(self, cache: "Cache") -> None: ...
    def write(self, cache: "Cache") -> None: ...


class Confirm(Protocol):
    def confirm(self, header: str, entries: Sequence[str]) -> set[str]: ...

        
@dataclass
class Cache:
    js: dict[str, dict[str, str]]
    fonts: dict[str, list[dict[str, str]]]
    confirm: Confirm
    store: Store

    @classmethod
    def from_path(cls, path: Path) -> Self:
        raise NotImplementedError()

    def update(self, src: "Cache") -> Self:
        raise NotImplementedError()

    
@dataclass
class StoreDirectory:
    path: Path

    def read(self, cache: Cache) -> None:
        raise NotImplementedError()

    def write(self, cache: Cache) -> None:
        raise NotImplementedError()


@dataclass
class StoreZipFile:
    path: Path

    def read(self, cache: Cache) -> None:
        raise NotImplementedError()

    def write(self, cache: Cache) -> None:
        raise NotImplementedError()


class ConfirmInteractiveStdio:

    def confirm(self, header: str, entries: Sequence[str]) -> set[str]:
        entries_ = list(entries)
        w = 1 + int(np.log10(len(entries)))
        confirmed = set()
        try:
            is_finished = False
            while not is_finished:
                print(header)
                for i, entry in enumerate(entries_, start=1):
                    print(f"{'*' if entry in confirmed else ' '} {i:{w}d}. {entry}")
                line = input("Number n, interval s-e, ? help, . finish> ").strip()
                for match in re.finditer(r"(?P<from>\d+)(-(?P<to>\d+))?|(?P<cmd>[.?])", line):
                    if (cmd := match.group("cmd")) is not None:
                        if cmd == "?":
                            self.print_help()
                        elif cmd == ".":
                            is_finished = True
                            break
                    else:
                        from_ = int(match.group("from"))
                        to_ = int(match.group("to") or from_)
                        for i in range(from_, to_ + 1):
                            e = entries_[i - 1]
                            if e in confirmed:
                                confirmed.remove(e)
                            else:
                                confirmed.add(e)
        except EOFError:
            pass
        return confirmed

    def print_help(self) -> None:
        print(
            """\

- Type the number of an item to select it: 2
- You can select an interval of items:     2-4
  selects items 2, 3 and 4.
- Type an item you had selected to deselect it.
- Type . to complete the selection process.
- Type Enter to make the command happen, forcing the selection menu to refresh.
- You can type multiple commands ahead of Enter: 1 3 2-4 7 .
  selects items 1, 2, 4 (3 was selected, then deselected by the interval) and 7,
  then finishes.

            """
        )


class ConfirmYes:

    def confirm(self, header: str, entries: Sequence[str]) -> set[str]:
        return set(entries)


import argparse


def main():
    parser = argparse.ArgumentParser(
        description="Cache JS and font files for offline mode",
        epilog="""
            For the --import and --export options, by default, the cache is stored as
            a Zip file (with the Zip-standard DEFLATE compression). However, if the
            path given through --import or --export is an existing directory, the cache
            files are stored as is into this directory, without any compression.
        """
    )
    parser.add_argument(
        "--js_urls", nargs="+", help="CDN URLs to fetch and cache js from"
    )
    parser.add_argument(
        "--font_names", nargs="+", help="Names of google font fonts to cache"
    )
    parser.add_argument(
        "--refresh", action="store_true", help="Force refresh cached files"
    )
    parser.add_argument("--js_cache_file", help="Path to save JS cache file")
    parser.add_argument("--font_cache_file", help="Path to save font cache file")
    parser.add_argument(
        "--import",
        default=None,
        help="""
            Imports fonts and resources from the named directory or archive into the
            user's cache directory. This omits updating cache fonts and Javascript files
            from the Internet. If any font or Javascript entry from the given cache
            dump already exists, confirmation to replace it is requested first.
        """
    )
    parser.add_argument(
        "--export",
        help="""
            Exports the user's cache to the given directory or archive after
            updating it. If the cache archive or directory already exists, and a font
            or Javascript entry from the export would clobber it, confirmation is
            requested first (unless option --yes is also used).
        """
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        default=False,
        help="""
            Forgo confirmation of cache entry replacement; just go ahead and do it.
        """
    )

    args = parser.parse_args()

    path_import_ = getattr(args, "import")
    if path_import_ is None:
        if args.js_urls:
            all_urls = list(set(DEFAULT_URLS + args.js_urls))
            cache_js_files(urls=args.all_urls, file_path=args.js_cache_file)
        else:
            cache_js_files(file_path=args.js_cache_file)
        if args.font_names:
            cache_fonts(fonts=args.font_names, file_path=args.font_cache_file)
        else:
            cache_fonts(file_path=args.font_cache_file)
    else:
        raise NotImplementedError("Import cache")

    if args.export is not None:
        raise NotImplementedError("Export cache")
