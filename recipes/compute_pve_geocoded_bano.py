# -*- coding: utf-8 -*-
from multiprocessing import Process, Queue
import dataiku
from dataiku.customrecipe import get_input_names_for_role
from dataiku.customrecipe import get_output_names_for_role
from dataiku.customrecipe import get_recipe_config
import itertools
import logging
import pandas as pd
import requests
import StringIO

# Proxy and server  config

PROXY_OPEN_LAB = 'proxy-1:3128'
PROXY_PRIVATE_LAB = 'localhost:3128'

SERVER_OPEN_LAB = 'http://datalab-bano'
SERVER_PRIVATE_LAB = 'http://adresse.datalab.mi'
SERVER_GOUV_FR = 'http://api-adresse.data.gouv.fr'

OPEN_LAB = True

http_proxy = PROXY_OPEN_LAB if OPEN_LAB else PROXY_PRIVATE_LAB
server_address = SERVER_OPEN_LAB if OPEN_LAB else SERVER_PRIVATE_LAB

# Input fields configuration
columns = ['ADRE_L_NUM', 'ADRE_L_NOM_VOIE', 'ADRE_cmne_l_nom']
post_code = 'ADRE_l_cmne_copo'
city_code = 'ADRE_cmne_c_insee' # None
# Ouput fields configuration
output_prefix = 'ban_'
error_prefix = 'err_'


# Process config
lines_per_request = 500
verbosechunksize = 2000
threads = 1
timeout = 1000

i = 0

def datas():
    """Returns the columns composing the address"""
    result = {'columns': columns}
    cols = list(columns)
    if post_code:
        result['postcode'] = post_code
        cols.append(post_code)
    if city_code:
        result['citycode'] = city_code
        cols.append(city_code)
    return (result, cols)

def adresse_submit(df, writer):
    """Does the actual request to the geocoding server"""
    global i
    verbosechunksize = 2000
    string_io = StringIO.StringIO()
    i += lines_per_request
    data, cols = datas()
    if not isinstance(df,pd.DataFrame): 
        return df
    df[cols].to_csv(string_io, encoding="utf-8", index=False)
    kwargs = {
        'data': data,
        'files': {'data': string_io.getvalue()},
        'timeout': timeout,
        'url': "{}/search/csv".format(server_address)
    }
    if http_proxy:
        kwargs['proxies'] = {'http': http_proxy}
    response = requests.post(**kwargs)
    error_col = 'result_{}'.format(error_prefix) if error_prefix else None
    if response.status_code == 200:
        content = StringIO.StringIO(response.content.decode('utf-8-sig'))
        result = pd.read_csv(content, dtype=object)
        if error_col:
            result[error_col] = None
        result = result.rename(columns={'longitude': 'result_longitude',
                                        'latitude': 'result_latitude'})
        diff = result.axes[1].difference(df.axes[1])
        for new_column in diff:
            if new_column.startswith("result_"):
                df[new_column.replace("result_", output_prefix)] = result[new_column]
    else:
        logging.warning("Chunk %r to %r: no valid response",
                        i-lines_per_request, i)
        df['result_score'] = -1
        if error_col:
            df["{}{}".format(output_prefix, error_prefix)] = "HTTP Status: {}".format(response.status_code)
    writer.write_dataframe(df)        
    return df

def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    args = [iter(iterable)] * n
    return itertools.izip_longest(*args, fillvalue=fillvalue)

def geocode(ids, ods):
    '''
        Geocodes each row in an input dataset, and produces a row in the output dataset with additional fields.

        ids: the input dataset
        ods: the output dataset
    '''
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
    ods.write_schema_from_dataframe(geocoded)
    ow = ods.get_writer()
    # Then the full pass
    dataset_iter = ids.iter_dataframes(chunksize=lines_per_request, infer_with_pandas=False)
    j = 0
    process_queue = Queue(threads)
    for chunk in dataset_iter:
        process_queue.put(chunk)
        thread = multiprocessing(target=adresse_submit, args=(process_queue.get(),ow))
        thread.start()
        j += lines_per_request
    ow.close()

ids = dataiku.Dataset("pve_sr_month")
ods = dataiku.Dataset("pve_geocoded_bano")
geocode(ids, ods)    
