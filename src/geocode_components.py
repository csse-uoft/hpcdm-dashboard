"""Geocoding and Spatial Discovery for Parcel Retrieval.

This module provides logic to convert human-readable addresses into geographic 
coordinates (geocoding) and perform spatial intersections against an RDF 
graph database to identify specific land parcels.

It utilizes a tiered geocoding approach (ArcGIS with a Nominatim fallback) 
and generates Plotly maps to visualize the search results and 
intersected parcel boundaries.

Dependencies:
    - ArcGIS for primary geocoding within the Toronto extent.
    - Nominatim for open-source fallback.
    - Plotly for map visualization.
    - GeoSPARQL for spatial graph queries.

To do:
    * refactor to move the SPARQL logic into sparql_client, map processing into ui_components
"""
from geopy.geocoders import Nominatim
from arcgis.gis import GIS
from arcgis.geocoding import geocode
import plotly.graph_objects as go
import plotly.express as px
from shapely.geometry import Point
from shapely import wkt
from SPARQLWrapper import SPARQLWrapper, JSON
import socket
from urllib.error import URLError 
from src.ui_components import *
def geocode_logic(address):
    """Translates a string address into geographic coordinates.

    Attempts to locate the address using the ArcGIS World Geocoding Service, 
    restricted to the Toronto extent. If no results are found or an error 
    occurs, it falls back to the Nominatim (OpenStreetMap) geocoder.

    Args:
        address (str): The physical address to geocode (e.g., "100 Queen St W").

    Returns:
        tuple[float | None, float | None, str | None]: A tuple containing 
            (latitude, longitude, formatted_address). Returns (None, None, None) 
            if the address cannot be resolved in either service.
    Notes:
        ArcGIS geocoding service is free within a limited volume
    """
    # 1. Initialize ArcGIS (No key required for basic public geosearch)
    public_gis = GIS() 

    # 2. Initialize Nominatim fallback
    nominatim_geolocator = Nominatim(user_agent="megan.katsumi@utoronto.ca")

    # Toronto Bounding Box for ArcGIS: [min_lon, min_lat, max_lon, max_lat]
    TORONTO_EXTENT = "-79.6393,43.5810,-79.1159,43.8554"
    # Try Official ArcGIS Library
    try:
        results = geocode(
            address=address, 
            search_extent=TORONTO_EXTENT, 
            max_locations=1,
            location_type="rooftop"
        )
        if results:
            loc = results[0]['location']
            return loc['y'], loc['x'], results[0]['address']
    except Exception as e:
        print(f"ArcGIS Error: {e}")

    # Fallback to Nominatim Toronto Restriction
    try:
        location = nominatim_geolocator.geocode({"street": address, "city": "Toronto", "country": "Canada"})
        if location:
            return location.latitude, location.longitude, location.address
    except Exception as e:
        print(f"Nominatim Error: {e}")

    return None, None, None

def process_address(endpoint,address):
    """Processes a user address to find the corresponding parcel and generate a map.

    This function coordinates the full workflow: geocoding the address, 
    constructing a GeoSPARQL 'sfIntersects' query, executing it against the 
    GraphDB endpoint, and rendering the result on an interactive map.

    Args:
        endpoint (str): The SPARQL endpoint URL.
        address (str): The raw address input from the user.

    Returns:
        tuple: A 5-element tuple containing:
            - parcel_uri (str): The IRI of the found parcel or error message.
            - full_address (str): A human-readable formatted address (or error message).
            - query_text (str): The SPARQL query string used for the lookup.
            - map_fig (go.Figure): The interactive Plotly map figure.
            - map_fig_alt (go.Figure): A duplicate of the map figure for UI sync (to maintain a base map state).
    """
    """Returns a parcel ID, referenced address, SPARQL lookup query, and map given user address input"""
    if not address:
        return None, "Please enter an address.", "", go.Figure()

    lat, lon, full_address = geocode_logic(address)

    if lat is None:
        return None, "Address not found in Toronto.", "", go.Figure()

    # 1. Generate WKT and Query
    wkt_point = Point(lon, lat).wkt
    query_text = f"""PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX geof: <http://www.opengis.net/def/function/geosparql/>
PREFIX hp: <http://ontology.eil.utoronto.ca/HPCDM/>      
   PREFIX loc: <https://standards.iso.org/iso-iec/5087/-1/ed-1/en/ontology/SpatialLoc/>
    PREFIX genprop: <https://standards.iso.org/iso-iec/5087/-1/ed-1/en/ontology/GenericProperties/>

SELECT ?p ?wkt WHERE {{
  ?p a hp:Parcel ;
     loc:hasLocation ?loc .
    ?loc geo:asWKT ?wkt.
    BIND("{wkt_point}"^^geo:wktLiteral AS ?pwkt)
   ?loc geo:sfIntersects ?pwkt 
}} LIMIT 1"""

    # 2. SPARQL Execution
    sparql = SPARQLWrapper(endpoint)
    sparql.setQuery(query_text)
    sparql.setReturnFormat(JSON)
    timeout_limit = 35 
    sparql.setTimeout(timeout_limit)

    parcel_uri = "No parcels found."
    fig = go.Figure()

    # Map Search Marker
    fig.add_trace(go.Scattermap(
        lat=[lat], 
        lon=[lon],
        mode='markers', 
        marker=dict(size=15, color='#FF0000'), #red
        name="Search Location",
        hovertemplate=f"<b>Search Address</b>: {full_address}<extra></extra>"
    ))

    try:
        bindings = sparql.query().convert()["results"]["bindings"]
        if bindings:
            ids = []
            for res in bindings:
                parcel_uri = res['p']['value']
                ids.append(parcel_uri)
                parcel_uri_label = parcel_uri.split('#')[-1].split('/')[-1] #parcel URI with namespace stripped for legibility
                # Use the new helper
                add_wkt_to_fig(
                    fig, 
                    res['wkt']['value'], 
                    name=f"Parcel: {parcel_uri_label}", 
                    color='#FF0000', #red
                    opacity=0.4,
                    secondary_label = "Parcel ID",
                    secondary_value= f"{parcel_uri_label}")
    except socket.timeout:
        raise gr.Error("Query Timed Out: The SPARQL endpoint is currently busy. Please try again in a moment.")
    except URLError as e:
        # URLError often wraps a timeout, so we check the reason
        if isinstance(e.reason, socket.timeout):
            raise gr.Error("Query Timed Out: The SPARQL endpoint is currently busy. Please try again in a moment.")
        return f"Network Error: {str(e.reason)}"
    except Exception as e:
        parcel_uri = f"Query Error: {e}"

    fig.update_layout(
        map_style="streets",
        map=dict(center=dict(lat=lat, lon=lon), zoom=17),
        margin={"r":0,"t":0,"l":0,"b":0},
        legend=dict(
        orientation="h",   # Horizontal legend
        yanchor="bottom",
        y=-0.1,            # Position slightly below the map (0 is bottom edge)
        xanchor="center",
        x=0.5              # Center it horizontally
    )
    )
    return parcel_uri, f"Geocoded: {full_address}", query_text, fig, fig