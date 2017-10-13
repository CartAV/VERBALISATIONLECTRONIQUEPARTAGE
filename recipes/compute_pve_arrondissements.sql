SELECT *, ign_commune_france."INSEE_COM" as code_arrondissement
  FROM "2010_2015_pve_sr_regions_postgis"
  LEFT JOIN ign_commune_france
  ON st_within(st_SetSrid(st_point(longitude, latitude), 4326), "the_geom"::geometry)
  AND "CODE_INSEE_INFRACTION" IN ('75056', '69123', '13055')
  AND "2010_2015_pve_sr_regions_postgis"."CODE_DEPT" IN ('75', '69', '13')
  AND "2010_2015_pve_sr_regions_postgis"."INSEE_COM" NOT IN ('75056', '69123', '13055')
