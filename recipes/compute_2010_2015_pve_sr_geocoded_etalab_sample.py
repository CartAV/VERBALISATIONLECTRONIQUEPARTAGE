# -*- coding: utf-8 -*-
import dataiku as d
import os.path
import codecs, io, StringIO, requests
import pandas as pd, numpy as np
import concurrent.futures
from sklearn.utils import shuffle
from dataiku import pandasutils as pdu
from collections import OrderedDict


# Recipe inputs
f = d.Dataset("2010_2015_pve_sr_sample")
i=0
liste=[]
futures=[]
split=100
verbosechunksize=2000
maxtries=1
nthreads=2
j=0

# Recipe outputs


def adresse_submit(df):
    global i
    s = StringIO.StringIO()
    i+=split
    if ((i%verbosechunksize)==0):
        print("geocoding chunk %r to %r" %(i-verbosechunksize,i))
    t=1
    while (t<=maxtries):
        df_adr=df[["PVE_ID","VOIE_INFRACTION","CODE_POSTAL_INFRACTION"]]
        df_adr.fillna("NA")
        df_adr.to_csv(s,sep=",", quotechar='"',encoding="utf8",index=False)
        requests_session = requests.Session()
        kwargs = {
            'data': OrderedDict({                     
                        'columns':'VOIE_INFRACTION', 
                        'postcode':'CODE_POSTAL_INFRACTION'
            }),
            'method': 'post',
            'files': OrderedDict([
                ('data', s.getvalue())
            ]),
            'stream': True,
            'timeout':500,
            'url': 'http://api-adresse.data.gouv.fr/search/csv/',
            'proxies': {'http': 'http://proxy-1:3128'}
        }
    
        response = requests_session.request(**kwargs)
        if (response.status_code == 200):
            print "response ok"
            print response.content.decode('latin9')
            res=pd.read_csv(StringIO.StringIO(response.content.decode('utf-8')),sep=",",quotechar=None,dtype=object)
            print "got res"
            del res['CODE_POSTAL_INFRACTION']
            del res['VOIE_INFRACTION']
            print "deleted"
            res=pd.merge(df,res,how='left',on='PVE_ID')
            print "data merged"
            res['result_chunk']=i
            res['result_success']="success"
            #print(res)
            t=maxtries+1
        elif (response.status_code == 400):
            print("chunk %r to %r generated an exception, try #%r" %(i-split,i,t))
            res=df
            res['result_score']=-1
            res['result_chunk']=i
            res['result_success']="failed err 400" 
            df_adr=shuffle(df_adr)
            t=maxtries+1
        else:
            print("chunk %r to %r generated an exception, try #%r" %(i-split,i,t))
            res=df
            res['result_score']=-0.5
            res['result_chunk']=i
            res['result_success']="failed err 400"             
            t+=1
        
        
    return res




#version monothread
#for events_subset in f.iter_dataframes(chunksize=split):
#    i+=split
#    print("Enrichissement addok/BAN: {}...".format(i))
#    liste.append(adresse_submit(events_subset))
#    # Insert here applicative logic on each partial dataframe.
#    pass    

#multithread

with concurrent.futures.ThreadPoolExecutor(max_workers=nthreads) as executor:
    enrich={executor.submit(adresse_submit,subset) for subset in f.iter_dataframes(chunksize=split,infer_with_pandas=False)}
    for s in concurrent.futures.as_completed(enrich):  
        j+=split
        try:
            #print(s.result())
            liste.append(s.result())
        except Exception as exc:
            print("chunk %r to %r generated an exception: %r\n%r" %(j-split,j,exc,s))
        else:
            if ((j%verbosechunksize)==0):
                print("geocoded chunk %r to %r" %(j-verbosechunksize,j))

print "Going to concat"
#print("len(liste) "+str(len(liste)))
#print(liste[0])
events=pd.concat(liste,ignore_index=True)
#print("len(events) "+str(len(events)))

out = d.Dataset("2010_2015_pve_sr_geocoded_etalab_sample")
out.write_with_schema(events)



