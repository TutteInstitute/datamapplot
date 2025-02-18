import base64
from collections.abc import Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
import io
import json
import numpy as np
from pathlib import Path
import platformdirs
import re
import requests
import sys
from typing import Any, Protocol
from urllib.parse import urlparse
from zipfile import ZipFile, ZIP_DEFLATED

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
    class Reading(Protocol):
        def open(self, name) -> io.TextIOBase: ...

    class Writing(Protocol):
        def open(self, name) -> io.TextIOBase: ...

    @property
    def path(self) -> Path: ...
    def reading(self) -> AbstractContextManager["Store.Reading"]: ...
    def writing(self) -> AbstractContextManager["Store.Writing"]: ...


class Confirm(Protocol):
    def confirm(self, header: str, entries: Sequence[str]) -> set[str]: ...


@dataclass
class Cache:
    js: dict[str, dict[str, str]]
    fonts: dict[str, list[dict[str, str]]]
    confirm: Confirm
    store: Store

    @classmethod
    def from_path(cls, path: Path, confirm: Confirm) -> "Cache":
        store = make_store(path)
        data = {}
        with store.reading() as reading:
            for name in ["datamapplot_js_encoded.json", "datamapplot_fonts_encoded.json"]:
                try:
                    with reading.open(name) as file:
                        data[name] = json.load(file)
                except KeyError:
                    data[name] = {}
        return cls(
            js=data["datamapplot_js_encoded.json"],
            fonts=data["datamapplot_fonts_encoded.json"],
            confirm=confirm,
            store=store
        )

    def update(self, src_cache: "Cache") -> "Cache":
        for attr, resource in [("js", "Javascript file"), ("fonts", "font")]:
            src = getattr(src_cache, attr)
            dest = getattr(self, attr)
            entries_to_pull = []
            entries_to_confirm = []
            for key in src.keys():
                if key in dest:
                    entries_to_confirm.append(key)
                else:
                    entries_to_pull.append(key)

            if entries_to_confirm:
                msg_resource = (
                    f"These {resource}s"
                    if len(entries_to_confirm) > 1
                    else f"This {resource}"
                )
                entries_to_pull += list(
                    self.confirm.confirm(
                        (
                            f"\n{msg_resource} would be replaced in cache at "
                            f"{self.store.path}. Select to confirm:"
                        ),
                        sorted(entries_to_confirm)
                    )
                )
            dest.update({k: src[k] for k in entries_to_pull})
        return self

    def save(self) -> None:
        with self.store.writing() as writing:
            for name, obj in [
                ("datamapplot_js_encoded.json", self.js),
                ("datamapplot_fonts_encoded.json", self.fonts),
            ]:
                with writing.open(name) as file:
                    json.dump(obj, file)


@dataclass
class StoreDirectory:
    path: Path

    @dataclass
    class Reading:
        dir: Path

        def open(self, name: str) -> io.TextIOBase:
            try:
                return (self.dir / name).open(mode="r", encoding="utf-8")
            except OSError:
                raise KeyError(f"The directory has no file named {name}")

    @contextmanager
    def reading(self) -> Iterator[Store.Reading]:
        yield self.Reading(self.path)

    @dataclass
    class Writing:
        dir: Path

        def open(self, name: str) -> io.TextIOBase:
            return (self.dir / name).open(mode="w", encoding="utf-8")

    @contextmanager
    def writing(self) -> Iterator[Store.Writing]:
        yield self.Writing(self.path)


@dataclass
class StoreZipFile:
    path: Path

    @dataclass
    class Reading:
        file: ZipFile

        def open(self, name: str) -> io.TextIOBase:
            return io.TextIOWrapper(self.file.open(name, "r"), encoding="utf-8")

    @contextmanager
    def reading(self) -> Iterator[Store.Reading]:
        if not self.path.is_file():
            # Create an empty Zip file so reading does not fail.
            with ZipFile(self.path, mode="w"):
                pass
        with ZipFile(self.path, mode="r") as z:
            yield self.Reading(z)

    @dataclass
    class Writing:
        file: ZipFile

        def open(self, name: str) -> io.TextIOBase:
            return io.TextIOWrapper(self.file.open(name, "w"), encoding="utf-8")

    @contextmanager
    def writing(self) -> Iterator[Store.Writing]:
        with ZipFile(self.path, mode="w", compression=ZIP_DEFLATED) as z:
            yield self.Writing(z)


def make_store(path: Path) -> Store:
    if path.is_dir():
        return StoreDirectory(path)
    return StoreZipFile(path)


class EquivalenceClass:

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, type(self))


class ConfirmInteractiveStdio(EquivalenceClass):

    def confirm(self, header: str, entries: Sequence[str]) -> set[str]:
        w = 1 + int(np.log10(len(entries)))
        confirmed = set()
        try:
            is_finished = False
            while not is_finished:
                print(header)
                for i, entry in enumerate(entries, start=1):
                    print(f"{'*' if entry in confirmed else ' '} {i:{w}d}. {entry}")
                line = input(
                    "NUMBER single item, FIRST-LAST interval, a all, ? help, . finish> "
                ).strip()
                for match in re.finditer(
                    r"(?P<indices>a|\d+(-(?P<to>\d+))?)|(?P<cmd>[.?])",
                    line
                ):
                    if (cmd := match.group("cmd")) is not None:
                        if cmd == "?":
                            self.print_help()
                        elif cmd == ".":
                            is_finished = True
                            break
                    elif (indices := match.group("indices")) is not None:
                        if indices == "a":
                            start = 0
                            end = len(entries)
                        else:
                            s, *e_maybe = indices.split("-")
                            start = int(s)
                            end = (int(e_maybe[0]) if e_maybe else start) + 1
                        for i in range(start, end):
                            try:
                                e = entries[i - 1]
                                if e in confirmed:
                                    confirmed.remove(e)
                                else:
                                    confirmed.add(e)
                            except IndexError:
                                pass  # Ignore indices to entries that don't exist.
                    else:
                        # This condition can be ignored, but when debugging we should
                        # break on it so it gets fixed.
                        assert False, (
                             "Either one of the conditions above should be true."
                         )
        except EOFError:
            print(
                (
                    "Standard input has been exhausted. "
                    "Please type '.' at the prompt (without the quotes) "
                    "for the update process to carry on. "
                    "Cancelling this operation, lest entries to update were "
                    "misselected."
                ),
                file=sys.stderr
            )
            sys.exit(11)
        return confirmed

    def print_help(self) -> None:
        print(
            """\

Type the number of an item to select it: 2

You can select an interval of items: 2-4
selects items 2, 3 and 4.

You can toggle all items: a

Selecting again an item then deselects it, whether using single number,
interval or a.

Type . to complete the selection process and go ahead with the replacements.

Type Enter to make the command happen, forcing the selection menu to refresh.

You can type multiple commands ahead of Enter: 1 3 2-4 7 .
selects items 1, 2, 4 and 7 (3 was selected, then deselected by the interval),
then proceeds."""
        )


class ConfirmYes(EquivalenceClass):

    def confirm(self, header: str, entries: Sequence[str]) -> set[str]:
        return set(entries)


_MAP_CONFIRM = {
    True: ConfirmYes,
    False: ConfirmInteractiveStdio
}


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
        "--refresh",
        action="store_true",
        default=True,
        help=(
            "Force refresh cached files from Internet repositories. "
            "This is the default."
        )
    )
    parser.add_argument(
        "--no-refresh",
        dest="refresh",
        action="store_false",
        help="Omit refreshing cached files from Internet repositories."

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

    dir_cache_home = Path(_DATA_DIRECTORY)
    dir_cache_home.mkdir(parents=True, exist_ok=True)
    path_import = getattr(args, "import")
    if path_import is None:
        if args.refresh:
            if args.js_urls:
                all_urls = list(set(DEFAULT_URLS + args.js_urls))
                cache_js_files(urls=all_urls, file_path=args.js_cache_file)
            else:
                cache_js_files(file_path=args.js_cache_file)
            if args.font_names:
                cache_fonts(fonts=args.font_names, file_path=args.font_cache_file)
            else:
                cache_fonts(file_path=args.font_cache_file)

        if args.export is not None:
            path_export = Path(args.export)
            if not path_export.is_dir() and (
                path_export.suffix[-4:] not in {".zip", ".ZIP"}
            ):
                print(
                    (
                        "WARNING: exporting the cache to a Zip archive, but "
                        f"the path to export to, {path_export}, does not carry "
                        "the usual .zip or .ZIP extension. If you rather meant to "
                        "export the cache to a directory, create it before running "
                        "this program."
                    ),
                    file=sys.stderr
                )
            cache_home = Cache.from_path(dir_cache_home, ConfirmYes())
            cache_dest = Cache.from_path(path_export, _MAP_CONFIRM[args.yes]())
            cache_dest.update(cache_home)
            cache_dest.save()
    else:
        cache_home = Cache.from_path(dir_cache_home, _MAP_CONFIRM[args.yes]())

        cache_src = Cache.from_path(Path(path_import), ConfirmYes())
        cache_home.update(cache_src)
        cache_home.save()
