# Table of Contents

* [app\_demo](#app_demo)
* [src.utils](#src.utils)
  * [process\_service\_data](#src.utils.process_service_data)
  * [process\_neighbourhood\_demographics](#src.utils.process_neighbourhood_demographics)
  * [process\_compliance\_properties](#src.utils.process_compliance_properties)
  * [process\_zoning\_compliance](#src.utils.process_zoning_compliance)
  * [process\_df\_col\_to\_markdown](#src.utils.process_df_col_to_markdown)
* [src.sparql\_client](#src.sparql_client)
  * [fetch\_parcel\_attributes](#src.sparql_client.fetch_parcel_attributes)
  * [fetch\_landuse](#src.sparql_client.fetch_landuse)
  * [fetch\_neighbourhood\_demographics](#src.sparql_client.fetch_neighbourhood_demographics)
  * [fetch\_service\_classes](#src.sparql_client.fetch_service_classes)
  * [fetch\_service\_data](#src.sparql_client.fetch_service_data)
  * [fetch\_zoning\_data](#src.sparql_client.fetch_zoning_data)
  * [fetch\_compliance\_properties](#src.sparql_client.fetch_compliance_properties)
  * [fetch\_zoning\_compliance](#src.sparql_client.fetch_zoning_compliance)
  * [fetch\_allowed\_use](#src.sparql_client.fetch_allowed_use)
  * [fetch\_current\_use](#src.sparql_client.fetch_current_use)
  * [run\_sparql\_to\_data](#src.sparql_client.run_sparql_to_data)
* [src.ui\_components](#src.ui_components)
  * [add\_wkt\_to\_fig](#src.ui_components.add_wkt_to_fig)
  * [hex\_to\_rgb\_array](#src.ui_components.hex_to_rgb_array)
  * [hex\_to\_rgba](#src.ui_components.hex_to_rgba)
  * [is\_near\_any\_banned](#src.ui_components.is_near_any_banned)
  * [query\_router](#src.ui_components.query_router)
  * [secondary\_router](#src.ui_components.secondary_router)
  * [generate\_graph\_iframe](#src.ui_components.generate_graph_iframe)

<a id="app_demo"></a>

# app\_demo

Toronto Housing Potential Dashboard - Main Application.

This module serves as the entry point for the Toronto Housing Potential
Dashboard. It initializes the Gradio web interface, manages global
application state (SPARQL endpoints and prefixes), and orchestrates
the interaction between the geocoding logic, SPARQL client, and UI components.

The dashboard allows users to:
1. Search for Toronto addresses to identify specific land parcels.
2. Visualize parcel boundaries and surrounding urban data on an interactive map.
3. Perform advanced spatial and regulatory queries (Zoning, Services, Demographics).

Environment Variables:
SPARQL_ENDPOINT: The URL for the GraphDB/RDF triple store.
Note: These are loaded via a .env file.

**Attributes**:

- `PREFIXES` _str_ - A global string containing all SPARQL namespace
  declarations required for the application's semantic queries.

<a id="src.utils"></a>

# src.utils

Utility functions for processing and aggregating urban data.

This module acts as the processing layer between the raw SPARQL client and 
the UI components. It handles iterative querying (e.g., looping through 
service classes), data cleaning, and the transformation of geographic 
results into structured lists for map rendering.

Functions in this module typically return both a pandas DataFrame for 
table display and a list of dictionaries for Plotly map features.

<a id="src.utils.process_service_data"></a>

#### process\_service\_data

```python
def process_service_data(endpoint, prefixes, pid, progress=gr.Progress())
```

[[view_source]](https://github.com/csse-uoft/hpcdm-dashboard/blob/bcdfabd1343d4ccda646ab98102320c941add7a6/src/utils.py#L14)

Iteratively retrieves and aggregates service data for a parcel.

This function first identifies all available service types in the graph,
then performs individual queries for each type to gather specific details
like site locations and capacities.
Stage 1: Get classes. Stage 2: Loop through classes for details.

**Arguments**:

- `endpoint` _str_ - The SPARQL endpoint URL.
- `prefixes` _str_ - SPARQL namespace declarations.
- `pid` _str_ - The persistent identifier (IRI) of the target parcel.
- `progress` _gr.Progress_ - Gradio progress tracker for UI feedback.
  

**Returns**:

  tuple[pd.DataFrame, list[dict]]: A tuple containing:
  - final_df: Combined DataFrame of all found services.
  - map_features: List of dicts containing 'wkt', 'label', and 'servicename'.
  

**Todo**:

  * Test and assess whether to include catchment areas for services (when available) in addition to service sites.

<a id="src.utils.process_neighbourhood_demographics"></a>

#### process\_neighbourhood\_demographics

```python
def process_neighbourhood_demographics(endpoint, prefixes, pid,
                                       census_characteristics)
```

[[view_source]](https://github.com/csse-uoft/hpcdm-dashboard/blob/bcdfabd1343d4ccda646ab98102320c941add7a6/src/utils.py#L79)

Processes demographic query results and extracts (unique) census tracts in the neighbourhood for display.

**Arguments**:

- `endpoint` _str_ - The SPARQL endpoint URL.
- `prefixes` _str_ - SPARQL namespace declarations.
- `pid` _str_ - The parcel IRI used to anchor the neighborhood search.
- `census_characteristics` _list[str]_ - List of census characteristic URIs.
  

**Returns**:

  tuple[pd.DataFrame, list[dict]]: A tuple containing:
  - demo_df: Raw demographic results.
  - map_features: List of unique census tract WKTs and labels.

<a id="src.utils.process_compliance_properties"></a>

#### process\_compliance\_properties

```python
def process_compliance_properties(endpoint, prefixes)
```

[[view_source]](https://github.com/csse-uoft/hpcdm-dashboard/blob/bcdfabd1343d4ccda646ab98102320c941add7a6/src/utils.py#L110)

Formats constrained (by zoning bylaws) properties into a list compatible with Gradio dropdowns.

**Arguments**:

- `endpoint` _str_ - The SPARQL endpoint URL.
- `prefixes` _str_ - SPARQL namespace declarations.
  

**Returns**:

  list[tuple[str, str]]: A list of (label, uri) tuples.

<a id="src.utils.process_zoning_compliance"></a>

#### process\_zoning\_compliance

```python
def process_zoning_compliance(endpoint, prefixes, pid, property)
```

[[view_source]](https://github.com/csse-uoft/hpcdm-dashboard/blob/bcdfabd1343d4ccda646ab98102320c941add7a6/src/utils.py#L124)

Processes zoning compliance for nearby parcels and extracts spatial status.

Extracts a short-form Parcel ID for display and categorizes map features
by their compliance status (e.g., 'compliant', 'noncompliant').

**Arguments**:

- `endpoint` _str_ - The SPARQL endpoint URL.
- `prefixes` _str_ - SPARQL namespace declarations.
- `pid` _str_ - The source parcel IRI.
- `property` _str_ - The specific property IRI to evaluate compliance for.
  

**Returns**:

  tuple[pd.DataFrame, list[dict]]: A tuple containing:
  - df: Detailed compliance DataFrame.
  - map_features: List of nearby parcel geometries with status labels.

**Todo**:

  * move the distance limit for 'nearby' to a parameter of this function

<a id="src.utils.process_df_col_to_markdown"></a>

#### process\_df\_col\_to\_markdown

```python
def process_df_col_to_markdown(df, colname)
```

[[view_source]](https://github.com/csse-uoft/hpcdm-dashboard/blob/bcdfabd1343d4ccda646ab98102320c941add7a6/src/utils.py#L167)

Converts a specific DataFrame column into a formatted Markdown list.

**Arguments**:

- `df` _pd.DataFrame_ - The source DataFrame.
- `colname` _str_ - The column to transform into a list (and name to display as the list heading).
  

**Returns**:

- `str` - A Markdown string with a header and bulleted items.

<a id="src.sparql_client"></a>

# src.sparql\_client

SPARQL Client for RDF Graph Database Interaction.

The sparql_client module defines the logic required to retrieve and process spatial and
regulatory data from an RDF graph database (optimized for GraphDB 11.2).
It includes templates for SPARQL queries related to parcel attributes,
zoning compliance, land use, and neighborhood demographics.

The core utility, `run_sparql_to_data`, executes these queries and returns
results as cleaned, typed pandas DataFrames.

**Todo**:

  * Refactor code to move the parcel-finder query from
  process_address in geocode_components.py here.
  * Refactor fetch_zoning_data (the processing logic should be implemented in a separate function in utils)
  * Test & implement the pattern ?cp rdfs:label ?cp_label in fetch_compliance_properties as optional
  * Include support for unit mismatches in fetch_zoning_compliance

<a id="src.sparql_client.fetch_parcel_attributes"></a>

#### fetch\_parcel\_attributes

```python
def fetch_parcel_attributes(endpoint, prefixes, pid)
```

[[view_source]](https://github.com/csse-uoft/hpcdm-dashboard/blob/bcdfabd1343d4ccda646ab98102320c941add7a6/src/sparql_client.py#L22)

Retrieves and formats parcel attributes via a SPARQL query.

Constructs and executes a SPARQL query to fetch the labels, numerical values,
and units for attributes associated with a specific parcel IRI.

**Arguments**:

- `endpoint` _str_ - The SPARQL endpoint URL.
- `prefixes` _str_ - SPARQL namespace declarations.
- `pid` _str_ - The persistent identifier (IRI) of the parcel.
  

**Returns**:

- `pd.DataFrame` - A DataFrame with columns ['attribute', 'value', 'unit'], as defined by table_vars.

<a id="src.sparql_client.fetch_landuse"></a>

#### fetch\_landuse

```python
def fetch_landuse(endpoint, prefixes, pid)
```

[[view_source]](https://github.com/csse-uoft/hpcdm-dashboard/blob/bcdfabd1343d4ccda646ab98102320c941add7a6/src/sparql_client.py#L56)

Retrieves allowed and current land use (if available, as captured by building use) for a specific parcel.

**Arguments**:

- `endpoint` _str_ - The SPARQL endpoint URL.
- `prefixes` _str_ - SPARQL namespace declarations.
- `pid` _str_ - The persistent identifier (IRI) of the parcel.
  

**Returns**:

- `pd.DataFrame` - A DataFrame containing 'allowed_use' and 'current_use', as defined by table_vars.

<a id="src.sparql_client.fetch_neighbourhood_demographics"></a>

#### fetch\_neighbourhood\_demographics

```python
def fetch_neighbourhood_demographics(endpoint, prefixes, pid,
                                     census_characteristics)
```

[[view_source]](https://github.com/csse-uoft/hpcdm-dashboard/blob/bcdfabd1343d4ccda646ab98102320c941add7a6/src/sparql_client.py#L83)

Retrieves neighborhood demographic data based on census characteristics.

**Arguments**:

- `endpoint` _str_ - The SPARQL endpoint URL.
- `prefixes` _str_ - SPARQL namespace declarations.
- `pid` _str_ - The parcel IRI used to identify the neighborhood.
- `census_characteristics` _list[str]_ - A list of URIs representing the
  demographic categories to retrieve.
  

**Returns**:

- `pd.DataFrame` - A DataFrame containing neighborhood name, population,
  units, and census tract labels, as definfed by table_vars.

<a id="src.sparql_client.fetch_service_classes"></a>

#### fetch\_service\_classes

```python
def fetch_service_classes(endpoint, prefixes)
```

[[view_source]](https://github.com/csse-uoft/hpcdm-dashboard/blob/bcdfabd1343d4ccda646ab98102320c941add7a6/src/sparql_client.py#L145)

Retrieves leaf-level Service classes defined in the graph.

Filters out classes that have further specific subclasses to return
only the most granular service types.

**Arguments**:

- `endpoint` _str_ - The SPARQL endpoint URL.
- `prefixes` _str_ - SPARQL namespace declarations.
  

**Returns**:

- `pd.DataFrame` - A DataFrame with a single column 'servicetype'.

<a id="src.sparql_client.fetch_service_data"></a>

#### fetch\_service\_data

```python
def fetch_service_data(endpoint, prefixes, pid, servicetype)
```

[[view_source]](https://github.com/csse-uoft/hpcdm-dashboard/blob/bcdfabd1343d4ccda646ab98102320c941add7a6/src/sparql_client.py#L174)

Retrieves services available to a parcel based on defined catchment area or service radius.

**Arguments**:

- `endpoint` _str_ - The SPARQL endpoint URL.
- `prefixes` _str_ - SPARQL namespace declarations.
- `pid` _str_ - The parcel IRI.
- `servicetype` _str_ - The IRI of the service class to filter by.
  

**Returns**:

- `pd.DataFrame` - A DataFrame containing service labels, names, capacity,
  and spatial WKT data. Note: spatial WKT data is currently only mapped for services with site locations.

<a id="src.sparql_client.fetch_zoning_data"></a>

#### fetch\_zoning\_data

```python
def fetch_zoning_data(endpoint, prefixes, pid, progress=gr.Progress())
```

[[view_source]](https://github.com/csse-uoft/hpcdm-dashboard/blob/bcdfabd1343d4ccda646ab98102320c941add7a6/src/sparql_client.py#L284)

Retrieves zoning regulations and their associated map geometries (i.e., area of the zone) for a parcel.

**Arguments**:

- `endpoint` _str_ - The SPARQL endpoint URL.
- `prefixes` _str_ - SPARQL namespace declarations.
- `pid` _str_ - The parcel IRI.
- `progress` _gr.Progress_ - Gradio progress tracker.
  

**Returns**:

  tuple[pd.DataFrame, list[dict]]: A tuple containing the results DataFrame
  and a list of map features (WKT and labels).

<a id="src.sparql_client.fetch_compliance_properties"></a>

#### fetch\_compliance\_properties

```python
def fetch_compliance_properties(endpoint, prefixes)
```

[[view_source]](https://github.com/csse-uoft/hpcdm-dashboard/blob/bcdfabd1343d4ccda646ab98102320c941add7a6/src/sparql_client.py#L358)

Retrieves all property types currently defined in zoning regulations.

**Arguments**:

- `endpoint` _str_ - The SPARQL endpoint URL.
- `prefixes` _str_ - SPARQL namespace declarations.
  

**Returns**:

- `pd.DataFrame` - A DataFrame with 'cp' (property IRI) and 'cp_label' (the defined label for the property).

<a id="src.sparql_client.fetch_zoning_compliance"></a>

#### fetch\_zoning\_compliance

```python
def fetch_zoning_compliance(endpoint, prefixes, pid, property)
```

[[view_source]](https://github.com/csse-uoft/hpcdm-dashboard/blob/bcdfabd1343d4ccda646ab98102320c941add7a6/src/sparql_client.py#L389)

Analyzes zoning compliance for a specific property across nearby parcels.

**Arguments**:

- `endpoint` _str_ - The SPARQL endpoint URL.
- `prefixes` _str_ - SPARQL namespace declarations.
- `pid` _str_ - The source parcel IRI to search around (200m radius).
- `property` _str_ - The property IRI (e.g., height, set-back) to check.
  

**Returns**:

- `pd.DataFrame` - A DataFrame including nearby parcel IRIs, regulatory limits,
  actual values, and a calculated 'compliancestatus'.
  Compliance status is defined as:
  * 'noncompliant' if the limit is violated (i.e., the parcel demonstrates a greater/lower value for a maximum/minimum constraint),
  * 'unknown' if the actual value is missing
  * 'incompatible units' if the units in the limit and the actual value aren't aligned

<a id="src.sparql_client.fetch_allowed_use"></a>

#### fetch\_allowed\_use

```python
def fetch_allowed_use(endpoint, prefixes, pid)
```

[[view_source]](https://github.com/csse-uoft/hpcdm-dashboard/blob/bcdfabd1343d4ccda646ab98102320c941add7a6/src/sparql_client.py#L482)

Retrieves allowed land uses for a parcel based on zoning bylaws.

**Arguments**:

- `endpoint` _str_ - The SPARQL endpoint URL.
- `prefixes` _str_ - SPARQL namespace declarations.
- `pid` _str_ - The parcel IRI.
  

**Returns**:

- `pd.DataFrame` - A DataFrame of allowed uses. Returns 'unknown' if empty.

<a id="src.sparql_client.fetch_current_use"></a>

#### fetch\_current\_use

```python
def fetch_current_use(endpoint, prefixes, pid)
```

[[view_source]](https://github.com/csse-uoft/hpcdm-dashboard/blob/bcdfabd1343d4ccda646ab98102320c941add7a6/src/sparql_client.py#L511)

Retrieves the current recorded use of a parcel from building data.

**Arguments**:

- `endpoint` _str_ - The SPARQL endpoint URL.
- `prefixes` _str_ - SPARQL namespace declarations.
- `pid` _str_ - The parcel IRI.
  

**Returns**:

- `pd.DataFrame` - A DataFrame of current uses. Returns 'unknown' if empty.

<a id="src.sparql_client.run_sparql_to_data"></a>

#### run\_sparql\_to\_data

```python
def run_sparql_to_data(query, endpoint, columns)
```

[[view_source]](https://github.com/csse-uoft/hpcdm-dashboard/blob/bcdfabd1343d4ccda646ab98102320c941add7a6/src/sparql_client.py#L541)

Executes a SPARQL query and converts the JSON results to a pandas DataFrame.

Handles the conversion of SPARQL JSON bindings to a tabular format,
attempts to infer numeric types, and utilizes nullable pandas dtypes.

**Arguments**:

- `query` _str_ - The full SPARQL query string.
- `endpoint` _str_ - The SPARQL endpoint URL.
- `columns` _list[str]_ - The variable names to extract from the SELECT clause.
  

**Returns**:

- `pd.DataFrame` - The processed results. Returns an empty DataFrame on error.

<a id="src.ui_components"></a>

# src.ui\_components

UI Components for the Housing Potential Dashboard.

This module provides high-level functions to handle user interactions within
the Gradio interface. It includes logic for:
1. Dynamic map rendering (Plotly/Shapely) with WKT support.
2. Route handling for different SPARQL query categories (via dropdown interaction).
3. Color palette management and exclusion (accessibility/contrast).
4. Embedding GraphDB visual graph visualizations via iframes.

**Notes**:

  Requires a running SPARQL endpoint and pre-configured GraphDB
  visualizations for certain iframe features.
  

**Todo**:

  * Replace the GraphDB graph view with a custom graph to improve the visualization

<a id="src.ui_components.add_wkt_to_fig"></a>

#### add\_wkt\_to\_fig

```python
def add_wkt_to_fig(fig,
                   wkt_str,
                   name,
                   color='blue',
                   opacity=0.3,
                   show_in_legend=True,
                   group_id=None,
                   secondary_label=None,
                   secondary_value=None)
```

[[view_source]](https://github.com/csse-uoft/hpcdm-dashboard/blob/bcdfabd1343d4ccda646ab98102320c941add7a6/src/ui_components.py#L26)

Parses WKT and adds a corresponding trace to a Plotly figure.

Supports Point, MultiPoint, Polygon, and MultiPolygon. Other geometry types
are ignored. Uses Scattermap for geographic rendering.

**Arguments**:

- `fig` _go.Figure_ - The Plotly figure object to modify.
- `wkt_str` _str_ - The Well-Known Text string representing the geometry.
- `name` _str_ - Label for the legend and hover tooltip.
- `color` _str_ - Hex or CSS color string for the trace.
- `opacity` _float_ - Fill opacity for polygons (0.0 to 1.0).
- `show_in_legend` _bool_ - Whether to display this specific trace in the legend.
- `group_id` _str, optional_ - Legend group ID to allow batch toggling.
  Defaults to the `name`.
- `secondary_label` _str, optional_ - Label for additional hover data.
- `secondary_value` _any, optional_ - Value for additional hover data.

<a id="src.ui_components.hex_to_rgb_array"></a>

#### hex\_to\_rgb\_array

```python
def hex_to_rgb_array(h)
```

[[view_source]](https://github.com/csse-uoft/hpcdm-dashboard/blob/bcdfabd1343d4ccda646ab98102320c941add7a6/src/ui_components.py#L106)

Converts a hex color string to a NumPy RGB array.

**Arguments**:

- `h` _str_ - Hex color code (e.g., ``FF5733``).
  

**Returns**:

- `np.ndarray` - Array of [R, G, B] values.

<a id="src.ui_components.hex_to_rgba"></a>

#### hex\_to\_rgba

```python
def hex_to_rgba(hex_code, opacity)
```

[[view_source]](https://github.com/csse-uoft/hpcdm-dashboard/blob/bcdfabd1343d4ccda646ab98102320c941add7a6/src/ui_components.py#L117)

Converts hex to a CSS-style rgba string.

**Arguments**:

- `hex_code` _str_ - Hex color code.
- `opacity` _float_ - Alpha value (0.0 to 1.0).
  

**Returns**:

- `str` - String in format 'rgba(R, G, B, A)'.

<a id="src.ui_components.is_near_any_banned"></a>

#### is\_near\_any\_banned

```python
def is_near_any_banned(color_hex, banned_list, threshold=60)
```

[[view_source]](https://github.com/csse-uoft/hpcdm-dashboard/blob/bcdfabd1343d4ccda646ab98102320c941add7a6/src/ui_components.py#L131)

Checks if a color is visually too close to any color in a banned list.

Uses Euclidean distance in the RGB color space.

**Arguments**:

- `color_hex` _str_ - The candidate color hex.
- `banned_list` _list[str]_ - List of hex colors to avoid.
- `threshold` _float_ - Distance limit for exclusion.
  

**Returns**:

- `bool` - True if the color is within the threshold of a banned color.

<a id="src.ui_components.query_router"></a>

#### query\_router

```python
def query_router(selected_option,
                 endpoint,
                 prefixes,
                 parcel_uri,
                 current_fig,
                 progress=gr.Progress())
```

[[view_source]](https://github.com/csse-uoft/hpcdm-dashboard/blob/bcdfabd1343d4ccda646ab98102320c941add7a6/src/ui_components.py#L152)

Primary router for executing SPARQL queries based on UI selection.
Returns the results in a table, column listing, map, and/or visual graph (html embedding) as appropriate.

**Arguments**:

- `selected_option` _str_ - The query category selected in the UI.
- `endpoint` _str_ - SPARQL endpoint URL.
- `prefixes` _str_ - SPARQL prefix declarations.
- `parcel_uri` _str_ - The IRI of the parcel being investigated.
- `current_fig` _go.Figure_ - The existing Plotly map figure.
- `progress` _gr.Progress_ - Gradio progress tracker.
  

**Returns**:

- `tuple` - (results_table, updated_fig, col1_md, col2_md, secondary_drp, graph_html)

<a id="src.ui_components.secondary_router"></a>

#### secondary\_router

```python
def secondary_router(first_selected_option,
                     selected_option,
                     endpoint,
                     prefixes,
                     parcel_uri,
                     current_fig,
                     progress=gr.Progress())
```

[[view_source]](https://github.com/csse-uoft/hpcdm-dashboard/blob/bcdfabd1343d4ccda646ab98102320c941add7a6/src/ui_components.py#L372)

Handles multi-step queries (e.g., specific property compliance).

Used when a secondary user input (like a dropdown) is required after the
initial category selection.

**Arguments**:

- `first_selected_option` _str_ - The primary category (e.g., 'Zoning Compliance').
- `selected_option` _str_ - The specific parameter (e.g., a specific property IRI).
- `endpoint` _str_ - SPARQL endpoint URL.
- `prefixes` _str_ - SPARQL prefix declarations.
- `parcel_uri` _str_ - The IRI of the parcel.
- `current_fig` _go.Figure_ - The existing Plotly map figure.
  

**Returns**:

- `tuple` - (results_table, updated_fig)

<a id="src.ui_components.generate_graph_iframe"></a>

#### generate\_graph\_iframe

```python
def generate_graph_iframe(pid,
                          configid,
                          host="compass.project.urbandatacentre.ca")
```

[[view_source]](https://github.com/csse-uoft/hpcdm-dashboard/blob/bcdfabd1343d4ccda646ab98102320c941add7a6/src/ui_components.py#L466)

Generates an HTML iframe string for GraphDB's Visual Graph.

Requires GraphDB to be configured with the specific visualization ID (configid).

**Arguments**:

- `pid` _str_ - The persistent identifier (IRI) to center the graph on.
- `configid` _str_ - The GraphDB visual configuration ID.
- `host` _str_ - Hostname of the GraphDB instance.
  

**Returns**:

- `str` - Raw HTML string containing the iframe.
  

**Todo**:

  * Accommodate option to generate a visualization directly from a SPARQL query
  https://graphdb.ontotext.com/documentation/11.2/visualize-and-explore.html#embed-visual-graphs
  * Investigate fixes for GraphDB bug: workspace view in embedding

