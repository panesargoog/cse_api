# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START gae_python37_app]
from flask import jsonify, Flask, render_template, request
import googleapiclient
from googleapiclient.discovery import build
from itertools import repeat
from keys import api_key, cse_id
from multiprocessing import Pool
import time

app = Flask(__name__)
service = build("customsearch", "v1", developerKey=api_key)


@app.route('/')
def form():
    return render_template('form.html')


def single_search(q, start):
    t1 = time.time()
    try:
        sr = service.cse().siterestrict().list(q=q, cx=cse_id, num=10, start=start).execute()
    except googleapiclient.errors.HttpError as err:
        print("Error:", start, err)
        return err

    t2 = time.time()
    print(q, start, t2 - t1)
    return sr


def parallel_search(q):
    t1 = time.time()
    p = Pool(3)

    start = [1, 11, 21]
    results = p.starmap(single_search, zip(repeat(q), start))
    i = 0
    all_results = {}
    try:
        for r in results:
            if r:
                if i == 0:
                    all_results = r
                else:
                    all_results['items'] = all_results['items'] + r['items']
            i += 1
    except IndexError as err:
        print("Error: ", err)
        return err

    t2 = time.time()
    print(t2 - t1)
    return all_results


def construct_item_list(search_results):
    """From CSE response, return an item list."""
    items = []
    for i in search_results["items"]:
        link = i["link"]
        if "https://www.homedepot.com/p/" in link:
            try:
                pid = link.rsplit('/', 1)[1]
            except IndexError:
                continue
            # TODO: Lookup storeId from inventory.
            item = {
                'productId': pid,
                'itemId': pid,
                'metadata': {
                    'storeId': 32
                }

            }
            items.append(item)
    return items


def add_dimension(label, refinements):
    # Dimension consists of a label, and refinements
    return {
        "label": label,
        "refinements": refinements,

    }


def construct_dimension(search_results, dim):
    # group the search results by dim, and count the number of records/dim
    # e.g. dim = 'brand'
    dimension = {}
    for i in search_results["items"]:
        try:
            products = i["pagemap"]["product"]
            for product in products:
                brand_name = product[dim]
                try:
                    dimension[brand_name]["record_count"] += 1
                except KeyError:
                    # TODO: Add filterParam, and refinmentKey
                    new_brand_refinement = {
                        "label": brand_name,
                        "recordCount": 1
                    }
                    dimension[brand_name] = new_brand_refinement
        except KeyError:
            print(i)

    return add_dimension(dim, dimension)


def construct_dimensions(search_results):
    dim = ['brand', 'color']
    # TODO: category
    # TODO: price, review_rating (histogram dimensions)
    dim_list = []
    for d in dim:
        dim_list.append(construct_dimension(search_results, d))
    return dim_list


def transform(search_results):
    """Transform CSE response to something similar to THD search response."""
    # Add itemIds and dimensions
    search_results['itemIds'] = construct_item_list(search_results)
    search_results['dimensions'] = construct_dimensions(search_results)
    # TODO: Add breadCrumbs, metadata, and searchReport sections.
    return search_results


@app.route('/api')
def query():
    """Make parallel requests to CSE API, and return a response similar to THD Search response."""
    q = request.args.get('q')
    search_results = parallel_search(q)
    search_results = transform(search_results)

    return jsonify(search_results)


@app.route('/result', methods=['POST'])
def result_page():
    """Return the formatted search result page."""
    query = request.form['query']
    results = search_result_page(query, api_key, cse_id, num=10)
    return results


# Test code follows:

@app.route('/sr')
def search_result_page():
    """HTML version of a single CSE search result."""
    search_term = request.args.get('q')
    search_results = service.cse().siterestrict().list(
        q=search_term, cx=cse_id).execute()
    return render_template('index.html', result=search_results)


@app.route('/test')
def test():
    """Return the JSON version of a CSE search result."""
    q = request.args.get('q')
    try:
        sr = service.cse().siterestrict().list(q=q, cx=cse_id, num=10, start=1).execute()
    except googleapiclient.errors.HttpError as err:
        print("Error: ", err)
        return "Error"
    return jsonify(sr)


if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
# [END gae_python37_app]
