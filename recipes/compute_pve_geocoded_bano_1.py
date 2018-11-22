# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# -*- coding: utf-8 -*-
import dataiku
import StringIO
import numpy as np
import pandas as pd
import itertools, requests, sys, time, traceback
from multiprocessing import Process, Queue

# Input/output config
IDS_NAME = "pve_sr_month"
ODS_NAME = "2010_2015_pve_sr_geocoded_ban_vertical"

# Proxy and server  config
(SERVER_OPEN_LAB, PROXY_OPEN_LAB) = ('http://datalab-ban', 'proxy-1:3128')
(SERVER_PRIVATE_LAB, PROXY_PRIVATE_LAB) = ('http://adresse.datalab.mi', 'localhost:3128')
SERVER_GOUV_FR = 'http://api-adresse.data.gouv.fr'
HTTP_PROXIES = { "http": None, "https": None }
server_address = SERVER_OPEN_LAB # or any addok server

# Input fields configuration
columns = ['VOIE_INFRACTION']
post_code = None
city_code = 'CODE_INSEE_INFRACTION'

# Ouput fields configuration
output_prefix = 'ban_'
error_prefix = 'error'
error_col = '{}{}'.format(output_prefix,error_prefix) if error_prefix else None

# Process config
lines_per_request = 50
verbosechunksize = 10000
threads = 80
timeout = 60
maxtries = 2
limit = None

def datas():
    """
        Returns the columns composing the address
    """
    result = {'columns': columns}
    cols = list(columns)
    if post_code:
        result['postcode'] = post_code
        cols.append(post_code)
    if city_code:
        result['citycode'] = city_code
        cols.append(city_code)
    return result, cols

def correct_addr(df, cols):
    df[cols] = df[cols].replace(np.nan, "xxxxx", regex = True)
    df[cols] = df[cols].replace(r'^\s*$', "xxxxx", regex = True)
    df[cols] = df[cols].replace(r'"', "", regex = True)
    df[cols] = df[cols].replace(r"'", "", regex = True)
    df[cols] = df[cols].replace(r"\.,", "", regex = True)
    df[cols] = df[cols].replace(r"_", ",", regex = True)

def process_chunk(i, df, process_queue, write_queue, schema_check=[]):
    try:
        df = adresse_submit(df, i, schema_check)
        if (((i + 1) * lines_per_request) % verbosechunksize) == 0:
            print("Chunk {}-{} ok".format(i * lines_per_request + 1, (i + 1) * lines_per_request))
    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print("Chunk {}-{} failed - {}".format(i * lines_per_request + 1, (i + 1) * lines_per_request,
                                                         traceback.print_exception(exc_type, exc_obj, exc_tb)))
    write_queue.put(df)
    process_queue.get(i)

def adresse_submit(df, i=0, schema_check=[]):
    """
        Sends the actual request to the geocoding server
    """
    global maxtries
    string_io = StringIO.StringIO()
    data, cols = datas()
    response = None
    if not isinstance(df, pd.DataFrame):
        return df
    df.reset_index(inplace = True)
    df[cols].to_csv(string_io, encoding = "utf-8", index = False)
    kwargs = {
        'data': data,
        'files': {'data': string_io.getvalue()},
        'timeout': timeout,
        'url': "{}/search/csv".format(server_address),
        'proxies': HTTP_PROXIES
    }
    tries = 1
    failed = True
    while failed & (tries <= maxtries):
        try:
            response = requests.post(**kwargs)
            status_code = response.status_code
        except requests.exceptions.ReadTimeout:
            status_code = "timeout"
        if status_code == 200:
            failed = False
        else:
            tries += 1
            if tries <= maxtries:
                time.sleep(3 ** (tries - 1))
    if not failed:
        content = StringIO.StringIO(response.content.decode('utf-8-sig'))
        result = pd.read_csv(content, dtype=object)
        if error_col:
            df[error_col] = None
        result = result.rename(columns={'longitude': 'result_longitude',
                                        'latitude': 'result_latitude'})
        if tries > 1:
            print("Chunk {}-{} needed {} tries".format(tries, i * lines_per_request + 1, (i + 1) * lines_per_request))
        diff = [x for x in result.axes[1].difference(df.axes[1]) if x.startswith('result_')]
        for result_column in diff:
            if result_column.startswith("result_"):
                new_column = result_column.replace("result_", output_prefix)
                df[new_column] = result[result_column]
    else:
        tries -= 1
        print("Chunk {}-{} failed after {} tries".format(i * lines_per_request + 1, (i + 1) * lines_per_request, tries))
        df[output_prefix + 'score'] = -1
        if error_col:
            df[error_col] = "HTTP Status: {}".format(status_code)
        if (len(schema_check) > len(df.axes[1])):
            diff = [x for x in schema_check.difference(df.axes[1])]
            for col in diff:
                df[col] = None
    return df

def grouper(iterable, n, fillvalue=None):
    """
        Collect data into fixed-length chunks or blocks
    """
    args = [iter(iterable)] * n
    return itertools.izip_longest(*args, fillvalue=fillvalue)

def geocode(ids, ods):
    """
        Geocodes each row in an input dataset, and produces a row in the output dataset with additional fields.
        ids: the input dataset
        ods: the output dataset
    """
    # First a small pass to produce the output schema
    small = ids.get_dataframe(sampling='head', limit=3, infer_with_pandas=False)
    initial_index = small.axes[1]
    geocoded = adresse_submit(small)
    output_index = geocoded.axes[1]
    if '{}longitude'.format(output_prefix) not in output_index:
        raise Exception('Geocoding failed: unable to make a sample request')
    schema = ids.read_schema()
    floats = [output_prefix + column for column in ['longitude', 'latitude', 'score']]
    for column in output_index.difference(initial_index):
        schema.append({'name': column, 'type': 'float' if column in floats else 'string'})
    ods.write_schema(schema)
    ow = ods.get_writer()
    # Then the full pass
    dataset_iter = ids.iter_dataframes(chunksize = lines_per_request, infer_with_pandas = False, limit = limit)
    process_queue = Queue(threads)
    write_queue = Queue()
    for i, chunk in enumerate(dataset_iter):
        process_queue.put(i)
        thread = Process(target = process_chunk, args = [i, chunk, process_queue, write_queue, output_index])
        thread.start()
        while write_queue.qsize() > 0:
            ow.write_dataframe(write_queue.get())

    print("Waiting  for{} chunk processes".format(process_queue.qsize()))
    while process_queue.qsize() > 0:
        time.sleep(1)
    print("Flushing {} chunks".format(write_queue.qsize()))
    while write_queue.qsize() > 0:
        ow.write_dataframe(write_queue.get())
    ow.close()

ids = dataiku.Dataset(IDS_NAME)
ods = dataiku.Dataset(ODS_NAME)
geocode(ids, ods)