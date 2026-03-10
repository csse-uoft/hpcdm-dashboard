"""UI Components for the Housing Potential Dashboard.

This module provides high-level functions to handle user interactions within 
the Gradio interface. It includes logic for:
1. Dynamic map rendering (Plotly/Shapely) with WKT support.
2. Route handling for different SPARQL query categories (via dropdown interaction).
3. Color palette management and exclusion (accessibility/contrast).
4. Embedding GraphDB visual graph visualizations via iframes.

Note:
    Requires a running SPARQL endpoint and pre-configured GraphDB 
    visualizations for certain iframe features.

Todo:
    * Replace the GraphDB graph view with a custom graph to improve the visualization
"""
import gradio as gr
import urllib.parse
import json
import plotly.graph_objects as go
from shapely import wkt
import plotly.express as px
from PIL import ImageColor
from src.sparql_client import *
from src.utils import *
def add_wkt_to_fig(fig, wkt_str, name, color='blue', opacity=0.3, show_in_legend=True, group_id=None, secondary_label=None, secondary_value=None):
    """Parses WKT and adds a corresponding trace to a Plotly figure.

    Supports Point, MultiPoint, Polygon, and MultiPolygon. Other geometry types 
    are ignored. Uses Scattermap for geographic rendering.

    Args:
        fig (go.Figure): The Plotly figure object to modify.
        wkt_str (str): The Well-Known Text string representing the geometry.
        name (str): Label for the legend and hover tooltip.
        color (str): Hex or CSS color string for the trace.
        opacity (float): Fill opacity for polygons (0.0 to 1.0).
        show_in_legend (bool): Whether to display this specific trace in the legend.
        group_id (str, optional): Legend group ID to allow batch toggling. 
            Defaults to the `name`.
        secondary_label (str, optional): Label for additional hover data.
        secondary_value (any, optional): Value for additional hover data.
    """
    try:
        clean_wkt = wkt_str.split('>')[-1].strip()
        lats = []
        lons = []
        geom = wkt.loads(clean_wkt)

        # Use the label name as the group ID if no specific group_id is provided
        gid = group_id if group_id else name

        legend_args = dict(
            name=name,
            legendgroup=gid,      # All items in this group toggle together
            showlegend=show_in_legend,
            marker=dict(size=12, color=color)
        )

        # Handle Point
        if geom.geom_type == 'Point':
            # Wrap in one extra list so it's [[label, value]]
            custom_data_wrapped = [[secondary_label, secondary_value]]
            fig.add_trace(go.Scattermap(
                lat=[geom.y], lon=[geom.x],
                mode='markers',
                **legend_args, # Unpack common legend settings
                customdata=custom_data_wrapped,
                hovertemplate=f"<b>%{{customdata[0]}}</b>: %{{customdata[1]}}<extra></extra>"
            ))
        # Handle Multipoint
        if geom.geom_type == 'MultiPoint':
            lats = [p.y for p in geom.geoms]
            lons = [p.x for p in geom.geoms]
            # Wrap in one extra list so it's [[label, value]] for EVERY point in the set
            custom_data_wrapped = [[secondary_label, secondary_value]] * len(lons)
            fig.add_trace(go.Scattermap(
                lat=lats, lon=lons,
                mode='markers',
                **legend_args, # Unpack common legend settings
                customdata=custom_data_wrapped,
                hovertemplate=f"<b>%{{customdata[0]}}</b>: %{{customdata[1]}}<extra></extra>"
            ))
        # Handle Polygons
        elif geom.geom_type in ['Polygon', 'MultiPolygon']:
            geoms = geom.geoms if geom.geom_type == 'MultiPolygon' else [geom]
            for g in geoms:
                lons, lats = g.exterior.xy
                # Create a list of [label, value] for EVERY vertex in the polygon
                custom_data_wrapped = [[secondary_label, secondary_value]] * len(lons)        
                fig.add_trace(go.Scattermap(
                    mode="lines", 
                    fill="toself",
                    lon=list(lons), 
                    lat=list(lats),
                    fillcolor=hex_to_rgba(color,opacity),
                    line=dict(width=2, color=color),
                    **legend_args, # Unpack common legend settings
                    customdata=custom_data_wrapped,
                    hovertemplate=f"<b>%{{customdata[0]}}</b>: %{{customdata[1]}}<extra></extra>"
                ))
    except Exception as e:
        print(f"Error parsing WKT for {name}: {e}")

#for color palette exclusion calculations
def hex_to_rgb_array(h):
    """Converts a hex color string to a NumPy RGB array.

    Args:
        h (str): Hex color code (e.g., `#FF5733`).

    Returns:
        np.ndarray: Array of [R, G, B] values.
    """
    return np.array(ImageColor.getcolor(h, "RGB"))

def hex_to_rgba(hex_code, opacity):
    """Converts hex to a CSS-style rgba string.

    Args:
        hex_code (str): Hex color code.
        opacity (float): Alpha value (0.0 to 1.0).

    Returns:
        str: String in format 'rgba(R, G, B, A)'.
    """
    hex_code = hex_code.lstrip('#')
    rgb = tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))
    return f'rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {opacity})'

def is_near_any_banned(color_hex, banned_list, threshold=60):
    """Checks if a color is visually too close to any color in a banned list.

    Uses Euclidean distance in the RGB color space.

    Args:
        color_hex (str): The candidate color hex.
        banned_list (list[str]): List of hex colors to avoid.
        threshold (float): Distance limit for exclusion.

    Returns:
        bool: True if the color is within the threshold of a banned color.
    """
    c1 = hex_to_rgb_array(color_hex)
    for banned_hex in banned_list:
        c2 = hex_to_rgb_array(banned_hex)
        distance = np.linalg.norm(c1 - c2)
        if distance < threshold:
            return True  # Found a match, no need to keep checking
    return False

def query_router(selected_option, endpoint, prefixes, parcel_uri,current_fig,progress=gr.Progress()):
    """Primary router for executing SPARQL queries based on UI selection.
    Returns the results in a table, column listing, map, and/or visual graph (html embedding) as appropriate.

    Args:
        selected_option (str): The query category selected in the UI.
        endpoint (str): SPARQL endpoint URL.
        prefixes (str): SPARQL prefix declarations.
        parcel_uri (str): The IRI of the parcel being investigated.
        current_fig (go.Figure): The existing Plotly map figure.
        progress (gr.Progress): Gradio progress tracker.

    Returns:
        tuple: (results_table, updated_fig, col1_md, col2_md, secondary_drp, graph_html)
    """
    """ Generates the appropriate query and output based on selected_option. """
    #text columns
    col1=""
    col2=""
    #results summaries
    results_table=gr.DataFrame(value=None,visible=False)
    secondary_drp = gr.Dropdown(choices=[],visible=False)
    #GraphDB visual graph html embedding
    graph_output = ""

    #colour palettes for maps
    # 1. Define the colors you want to avoid, threshold for closeness
    threshold = 80 # Increase this to be more "aggressive" with exclusions
    banned_colors = ["#FF0000"]  # Red (this is used for the parcel)
    # 2. Grab the full palette and filter it
    full_palette = px.colors.qualitative.Plotly
    clean_hex_palette = [
        c for c in full_palette 
        if not is_near_any_banned(c, banned_colors, threshold)
    ]

    if not parcel_uri:
        headers=[""]
        data = [["No parcel found. Please search for an address first."]]
        results_table = gr.Dataframe(value=data, headers=headers, visible=True)
    if selected_option == "Select...":
        headers=[""]
        data = [["Please select a query from the list."]]
        results_table = gr.Dataframe(value=data, headers=headers, visible=True)

    try:
        # create a copy of the map to add to it
        new_fig = go.Figure(current_fig)
    except Exception as e:
        print(f"Figure Restoration Error: {e}")
        # If it fails, we start a fresh figure to avoid crashing
        new_fig = go.Figure()

    if selected_option == "Parcel Attributes":
        # Query 1: Returns Attribute, Value, Unit
        headers = ["Attribute", "Value", "Unit of Measure"]
        data = fetch_parcel_attributes(endpoint,prefixes,parcel_uri)
        data.columns=headers
        #Style values with lower precision
        displaydata = data.style.format(precision=2)
        results_table = gr.Dataframe(value=displaydata, visible=True)    
        graph_output = generate_graph_iframe(parcel_uri,"4e4261c482204a5aa7951d08f4b66589") #predefined graphDB visualization config
    elif selected_option == "Neighbourhood Demographics":
        # Query 2: Returns neighbourhood demographic data
        #list of characteristics to query
        characteristic_list = ["http://ontology.eil.utoronto.ca/tove/cacensus#AverageAfterTaxIncome25Sample2016","http://ontology.eil.utoronto.ca/tove/cacensus#PopulationDensity2016","http://ontology.eil.utoronto.ca/tove/cacensus#TotalPrivateDwellings2016"]
        headers = ["Census Characteristic", "Value", "Unit","Census Tract"]
        data,map_data = process_neighbourhood_demographics(endpoint,prefixes,parcel_uri,characteristic_list)
        data = data.drop(columns=['neighbourhood_name','unit','cwkt'])
        data.columns = headers
        results_table = gr.Dataframe(value=data, visible=True)
        #update the map
        #  Build the color map using the indices of your unique labels
        # Since 'map_data' is already unique, we can use enumerate directly on it
        color_map = {
            item['label']: clean_hex_palette[i % len(clean_hex_palette)] 
            for i, item in enumerate(map_data)
        }
        for item in map_data:
            display_name = item['label']
            # The helper handles Points and Polygons automatically
            add_wkt_to_fig(
                new_fig, 
                item['wkt'], 
                display_name, 
                color=color_map[display_name], 
                opacity=0.2,
                secondary_label="Census Tract",
                secondary_value=display_name)
        # Re-apply the layout to ensure 'map' properties are preserved
        new_fig.update_layout(
            map_style="streets",
            margin={"r":0,"t":0,"l":0,"b":0}
        )
        current_fig = new_fig
    elif selected_option == "Available Services":
        #Returns available service and capacities
        headers = ["Service", "Name (if applicable)", "Capacity Type", "Capacity", "Capacity Unit"]
        data, map_data = process_service_data(endpoint, prefixes, parcel_uri, progress=progress)
        #remove wkt from results table
        data = data.drop(columns=['swkt'])
        #Set new headers for display
        data.columns=headers
        #Style values with lower precision
        displaydata = data.style.format(precision=2)
        results_table = gr.Dataframe(value=displaydata, visible=True)     

        # For service points on the map
        # Count occurrences of each service type
        from collections import Counter
        counts = Counter([item['label'] for item in map_data])

        # 2. Map each unique service type to a color
        unique_services = list(counts.keys())
        # Use Plotly's built-in qualitative palette (e.g., Plotly, D3, or G10)
        color_map = {srv: clean_hex_palette[i % len(clean_hex_palette)] for i, srv in enumerate(unique_services)}

        #add new map points for services, don't display an additional legend element if it's already been listed
        legend_tracker = set()
        for item in map_data:
            #labels for service types
            label = item['label']
            sname = item['servicename']
            count = counts[label]
            display_name = f"{label} ({count})" # e.g., "Library (3)"

            is_first = label not in legend_tracker
            if is_first:
                legend_tracker.add(label)
            # The helper handles Points and Polygons automatically
            add_wkt_to_fig(
                new_fig, 
                item['wkt'], 
                display_name, 
                color=color_map[label], 
                show_in_legend=is_first,
                group_id=label, # Keep the internal group ID the same for toggling
                opacity=0.2,
                secondary_label=label,
                secondary_value=sname)
        # Re-apply the layout to ensure 'map' properties are preserved
        new_fig.update_layout(
            map_style="streets",
            margin={"r":0,"t":0,"l":0,"b":0}
        )
        current_fig = new_fig

    elif selected_option == "Applicable Zoning":
        #Returns available service and capacities
        headers = ["Zone Label","Constraint", "Constrained Property", "Limit", "Limit Unit"]
        data, map_data = fetch_zoning_data(endpoint, prefixes, parcel_uri, progress=progress)
        #remove wkt from results table
        data = data.drop(columns=['regwkt'])
        #Set new headers for display
        data.columns=headers
        #Style values with lower precision
        displaydata = data.style.format(precision=2)
        results_table = gr.Dataframe(value=displaydata, visible=True, label="Note: zones adjacent to the parcel (if any) are returned for context.")

        #update map
        # For regulation areas on the map
        # Count occurrences of each zone
        from collections import Counter
        counts = Counter([item['label'] for item in map_data])

        # 2. Map each unique zone to a color
        unique_zone = list(counts.keys())
        color_map = {srv: clean_hex_palette[i % len(clean_hex_palette)] for i, srv in enumerate(unique_zone)}

        #add new map areas for new zones regulations, don't display an additional element if it's already been listed
        legend_tracker = set()
        for item in map_data:
            #labels for zones, count for number of regulations
            label = item['label']
            count = counts[label]
            display_name = f"{label} ({count})" # e.g., "ra_d2_0 (3)"

            is_first = label not in legend_tracker
            if is_first:
                legend_tracker.add(label)
                # The helper handles Points and Polygons automatically
                add_wkt_to_fig(
                    new_fig, 
                    item['wkt'], 
                    display_name, 
                    color=color_map[label], 
                    show_in_legend=is_first,
                    group_id=label, # Keep the internal group ID the same for toggling
                    opacity=0.2,
                    secondary_label="Zone",
                    secondary_value=display_name
                    )
            # Re-apply the layout to ensure 'map' properties are preserved
            new_fig.update_layout(
                map_style="streets",
                margin={"r":0,"t":0,"l":0,"b":0}
            )
        current_fig = new_fig
    
    elif selected_option == "Land Use":
        data1 = fetch_allowed_use(endpoint,prefixes,parcel_uri)
        header1="Allowed Use"
        data1.columns = [header1]
        col1value = process_df_col_to_markdown(data1,header1)
        data2 = fetch_current_use(endpoint,prefixes,parcel_uri)
        header2="Current Use"
        data2.columns=[header2]
        col2value = process_df_col_to_markdown(data2,header2)
        col1 = gr.Markdown(value = col1value, visible=True)
        col2 = gr.Markdown(value = col2value, visible=True)

    elif selected_option == "Zoning Compliance":
        #get property labels and uris constrained by zoning
        choices = process_compliance_properties(endpoint,prefixes)
        manual_option = [("Select a property...", "NONE_SELECTED")]
        choices = manual_option + choices
        secondary_drp = gr.Dropdown(choices,visible=True, value="NONE_SELECTED")
        results_table = gr.Dataframe(value=None, visible=False)
    return results_table, current_fig, col1, col2, secondary_drp,graph_output

def secondary_router(first_selected_option, selected_option,endpoint, prefixes, parcel_uri,current_fig,progress=gr.Progress()):
    """Handles multi-step queries (e.g., specific property compliance).

    Used when a secondary user input (like a dropdown) is required after the 
    initial category selection.

    Args:
        first_selected_option (str): The primary category (e.g., 'Zoning Compliance').
        selected_option (str): The specific parameter (e.g., a specific property IRI).
        endpoint (str): SPARQL endpoint URL.
        prefixes (str): SPARQL prefix declarations.
        parcel_uri (str): The IRI of the parcel.
        current_fig (go.Figure): The existing Plotly map figure.

    Returns:
        tuple: (results_table, updated_fig)
    """
    results_table=gr.DataFrame()
    # Manually unpack Gradio's PlotData object (to create a copy of the map so that we can add to it)
    try:
        #create a copy to add features to
        new_fig = go.Figure(current_fig)
    except Exception as e:
        print(f"Figure Restoration Error: {e}")
        # If it fails, we start a fresh figure to avoid crashing
        new_fig = go.Figure()
    #colour palettes for maps
    # 1. Define the colors you want to avoid, threshold for closeness
    threshold = 60 # Increase this to be more "aggressive" with exclusions
    banned_colors = ["#FF0000"]  # Red (this is used for the parcel)
    # 2. Grab the full palette and filter it
    full_palette = px.colors.qualitative.Plotly
    clean_hex_palette = [
        c for c in full_palette 
        if not is_near_any_banned(c, banned_colors, threshold)
    ]
    # 3. Convert the entire palette to RGB tuples once
    rgb_palette = [clean_hex_palette(c) for c in clean_hex_palette]

    if selected_option == "NONE_SELECTED":
        headers=[""]
        data = [["Please select a query from the list."]]
        results_table = gr.Dataframe(value=data, headers=headers, visible=True)
    elif not parcel_uri:
        headers=[""]
        data = [["No parcel found. Please search for an address first."]]
        results_table = gr.Dataframe(value=data, headers=headers, visible=True)
    elif first_selected_option == "Zoning Compliance":    #the logic for zoning compliance, other multi-part queries will be different
        headers = ["Nearby Parcel", "Regulation", "Constraint Type", "Limit", "Unit", "Actual Value", "Regulation Compliant?"]
        data,map_data = process_zoning_compliance(endpoint,prefixes,parcel_uri,selected_option)
        data = data.drop(columns=['nearbyp','nearbypwkt','actualunit'])
        data.columns = headers
        results_table = gr.Dataframe(value=data, visible=True)
        #update the map
        # For parcels on the map
        # Count occurrences of each status (compliance) type
        from collections import Counter
        counts = Counter([item['label'] for item in map_data])
        # Map each unique label type to a color
        unique_status = list(counts.keys())
        color_map = {srv: rgb_palette[i % len(rgb_palette)] for i, srv in enumerate(unique_status)}

        #add new map points for parcels, don't display an additional legend element if it's already been listed
        legend_tracker = set()
        for item in map_data:
            #labels for parcels
            label = item['label']
            count = counts[label]
            display_name = f"{label} ({count})" # e.g., "noncompliant (3)"

            is_first = label not in legend_tracker
            if is_first:
                legend_tracker.add(label)
            # The helper handles Points and Polygons automatically
            add_wkt_to_fig(
                new_fig, 
                item['wkt'], 
                display_name, 
                color=color_map[label], 
                show_in_legend=is_first,
                group_id=label, # Keep the internal group ID the same for toggling
                opacity=0.2,
                #add att value
                secondary_label=item['att_label'],
                secondary_value=item['att_value']
                )
            # Re-apply the layout to ensure 'map' properties are preserved
            new_fig.update_layout(
                map_style="streets",
                margin={"r":0,"t":0,"l":0,"b":0}
            )
        current_fig = new_fig
    return results_table, current_fig

def generate_graph_iframe(pid, configid, host="compass.project.urbandatacentre.ca"):
    """Generates an HTML iframe string for GraphDB's Visual Graph.

    Requires GraphDB to be configured with the specific visualization ID (configid).

    Args:
        pid (str): The persistent identifier (IRI) to center the graph on.
        configid (str): The GraphDB visual configuration ID.
        host (str): Hostname of the GraphDB instance.

    Returns:
        str: Raw HTML string containing the iframe.

    Todo:
        * Accommodate option to generate a visualization directly from a SPARQL query
            https://graphdb.ontotext.com/documentation/11.2/visualize-and-explore.html#embed-visual-graphs
        * Investigate fixes for GraphDB bug: workspace view in embedding
    """

    # Build the GraphDB Visual Graph URL with the &embedded parameter
    # Ensure your GraphDB is in 'Free Access' mode for the best experience.
    base_url = f"https://{host}/graphs-visualizations"
    repo = "CDT_HPCDM_Demo"
    #url encode the pid
     # 1. URL-encode the SPARQL query
    pid = urllib.parse.quote(pid)
    embedded_url = f"{base_url}?config={configid}&uri={pid}&embedded&repository={repo}"
    #debug
    print(f"Embedded url: {embedded_url}")
    # 3. Return the HTML iframe component
    return f'<iframe src="{embedded_url}" width="100%" height="600px" style="border:none;"></iframe>'