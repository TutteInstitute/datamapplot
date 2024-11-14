import base64
import requests
import json
import platformdirs
from urllib.parse import urlparse

DEFAULT_URLS = [
    "https://unpkg.com/deck.gl@latest/dist.min.js",
    "https://unpkg.com/apache-arrow@latest/Arrow.es2015.min.js",
    "https://unpkg.com/d3@latest/dist/d3.min.js",
    "https://unpkg.com/jquery@3.7.1/dist/jquery.min.js",
    "https://unpkg.com/d3-cloud@1.2.7/build/d3.layout.cloud.js",
]


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
