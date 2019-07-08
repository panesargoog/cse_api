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

from googleapiclient.discovery import build
import googleapiclient
from multiprocessing import Pool

from keys import api_key, cse_id
import time
from itertools import repeat

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


@app.route('/api')
def query():
    q = request.args.get('q')
    search_results = parallel_search(q)
    search_results['itemIds'] = construct_item_list(search_results)

    return jsonify(search_results)


@app.route('/result', methods=['POST'])
def result_page():
    query = request.form['query']
    results = search_result_page(query, api_key, cse_id, num=10)
    """Return the formatted search result page."""
    return results


# Test code follows:

@app.route('/sr')
def search_result_page():
    search_term = request.args.get('q')
    search_results = service.cse().siterestrict().list(
        q=search_term, cx=cse_id).execute()
    return render_template('index.html', result=search_results)


@app.route('/test')
def test():
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
