SELECT *, ign_commune_france."INSEE_COM" as code_arrondissement
  FROM "2010_2015_pve_sr_regions_postgis"
  LEFT JOIN ign_commune_france
  ON st_within(st_SetSrid(st_point(longitude, latitude), 4326), "the_geom"::geometry)
  AND current_city_code IN ('75056', '69123', '13055')
  AND "CODE_DEPT" IN ('75', '69', '13')
  AND "INSEE_COM" NOT IN ('75056', '69123', '13055')
