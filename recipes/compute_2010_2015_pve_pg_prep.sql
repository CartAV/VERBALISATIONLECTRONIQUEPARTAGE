SELECT
    pve.*,
    nearest_route."INSEE_COM",
    nearest_route.num_route_or_id,
    distance
FROM "2010_2015_pve_sr_pg" as pve

LEFT JOIN LATERAL (SELECT "INSEE_COM", num_route_or_id, st_distance(st_point(result_longitude, result_latitude), the_geom) as distance
     FROM "osm_routes_par_commune"  as routes
     where routes.the_geom && st_point(result_longitude, result_latitude)
     ORDER BY distance
    LIMIT 1) as nearest_route
ON true
