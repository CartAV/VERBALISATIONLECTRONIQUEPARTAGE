SELECT DISTINCT ON (pve."PVE_ID") 
    pve.*, b.lat as lat_pr, b.lon as lon_pr
    FROM "2010_2015_pve_prep_autoroute" pve
    LEFT JOIN "bornes_routes_2016_commune" b
    ON
        (pve."CODE_INSEE_INFRACTION" = b."INSEE_COM")
        AND (pve."LIBELLE_VOIE_RN" = b."nom_courant_route")
        AND (pve."LIBELLE_TYPE_VOIE_DEDUIT" = 'Autoroute' or pve."LIBELLE_TYPE_VOIE_DEDUIT" = 'Route Nationale')