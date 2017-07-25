SELECT 
    "2010_2015_pve_geocoded".*,
    st_distance("IGN_COMMUNE_FRANCE".the_geom, st_point(longitude, latitude)) as distance_commune,

    "IGN_COMMUNE_FRANCE"."CODE_COM" AS "CODE_COM"
  FROM "2010_2015_pve_geocoded"
  LEFT JOIN "ign_commune_france" "IGN_COMMUNE_FRANCE"
    ON "2010_2015_pve_geocoded"."CODE_INSEE_INFRACTION" = "IGN_COMMUNE_FRANCE"."INSEE_COM"