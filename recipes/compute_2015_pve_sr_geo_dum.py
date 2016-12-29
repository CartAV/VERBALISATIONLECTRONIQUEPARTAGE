# -*- coding: utf-8 -*-
import dataiku
import pandas as pd, numpy as np
from dataiku import pandasutils as pdu
import distance

# Recipe inputs
ds_in = dataiku.Dataset("20161122_pve_sr")
df = ds_in.get_dataframe()
print("chargement initial")    


nrows=len(df.index)
threshold=0.02*float(nrows)



liste=('REGROUPEMENT_GENRE','MOIS_INFRACTION','MNT_AF','LIBELLE_TYPE_VOIE','LIBELLE_STATUT_DOSSIER','LIBELLE_CLASSE','AGE_CONTREVENANT','SEXE_CONTREVENANT','LIBELLE_FAMILLE','LIBELLE_JOUR_INFRACTION','LIBELLE_NUIT','LIBELLE_PLAGE_HORAIRE','LIB_TRANCHE_DEPASSEMENT')
for key in liste:
    print("dummies : "+key)    
    df=pd.concat([df,pd.get_dummies(df[key],prefix="DUM_"+key,prefix_sep=" ")],axis=1)

liste=('LIBELLE_NATURE','MARQUE','NATIONALITE_PLAQUE')
for key in liste:
    print("signicative dummies : "+key)    
    values = df[key]
    counts = pd.value_counts(values)
    #filtre les valeurs présentées à moins de (threshold) %
    mask = values.isin(counts[counts > threshold].index)
    df=pd.concat([df,pd.get_dummies(values[mask],prefix="DUM_"+key,prefix_sep=" ")],axis=1)

print("écriture finale")    

# Recipe outputs
ds_out = dataiku.Dataset("20161122_pve_sr_geo_dum")
ds_out.write_with_schema(df)
