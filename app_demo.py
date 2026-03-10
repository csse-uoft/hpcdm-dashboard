"""Toronto Housing Potential Dashboard - Main Application.

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

Attributes:
    PREFIXES (str): A global string containing all SPARQL namespace 
        declarations required for the application's semantic queries.
"""
#!/usr/bin/env python
# coding: utf-8
#!/usr/bin/env python
# coding: utf-8
# main demo file - notebook version to be used for testing and development
# export executable, remove pip install statements, update launch statement
import gradio as gr
import pandas as pd
#get_ipython().run_line_magic('pip', 'install huggingface_hub>=0.19.0')
#get_ipython().run_line_magic('pip', 'install gradio>=4.0.0')
#get_ipython().run_line_magic('pip', 'install geopy shapely SPARQLWrapper plotly arcgis')

import json
import os
#get_ipython().run_line_magic('pip', 'install python-dotenv')
from dotenv import load_dotenv
from src.geocode_components import *
from src.sparql_client import *
from src.ui_components import *

load_dotenv()  # Load the variables from .env into system environment
SPARQL_ENDPOINT = os.getenv("SPARQL_ENDPOINT")
#define prefixes to be used in the queries
PREFIXES = """
PREFIX bdg: <https://standards.iso.org/iso-iec/5087/-2/ed-1/en/ontology/Building/>
PREFIX cacensus: <http://ontology.eil.utoronto.ca/tove/cacensus#>
PREFIX code: <https://standards.iso.org/iso-iec/5087/-2/ed-1/en/ontology/Code/> 
PREFIX genprop: <https://standards.iso.org/iso-iec/5087/-1/ed-1/en/ontology/GenericProperties/>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX geoext: <http://rdf.useekm.com/ext#>
PREFIX geof: <http://www.opengis.net/def/function/geosparql/>
PREFIX hp: <http://ontology.eil.utoronto.ca/HPCDM/>
PREFIX i72: <http://ontology.eil.utoronto.ca/ISO21972/iso21972#>
PREFIX loc_old: <http://ontology.eil.utoronto.ca/5087/1/SpatialLoc/>
PREFIX loc: <https://standards.iso.org/iso-iec/5087/-1/ed-1/en/ontology/SpatialLoc/>
PREFIX opr: <http://www.theworldavatar.com/ontology/ontoplanningregulation/OntoPlanningRegulation.owl#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX oz: <http://www.theworldavatar.com/ontology/ontozoning/OntoZoning.owl#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX res: <https://standards.iso.org/iso-iec/5087/-1/ed-1/en/ontology/Resource/>
PREFIX service: <https://standards.iso.org/iso-iec/5087/-2/ed-1/en/ontology/CityService/>
PREFIX time: <http://www.w3.org/2006/time#>
PREFIX tor: <http://ontology.eil.utoronto.ca/Toronto/Toronto#>
PREFIX uom: <http://www.opengis.net/def/uom/OGC/1.0/>
"""


# --- UI Setup ---
with gr.Blocks(theme=gr.themes.Default(primary_hue="red")) as demo:
    """Defines the Gradio Blocks layout and event-driven logic.
    
    The UI is split into two main sections:
    1. Search & Map: Geocoding input for parcel search and spatial visualization (base map).
    2. Advanced Queries: Iterative data retrieval for zoning, services, 
       and demographics.
    """
    # --- Hidden State ---
    # Used to store variables for context across interactions
    selected_parcel_uri = gr.State("")  #parcel id
    endpoint_state = gr.State(value=SPARQL_ENDPOINT) #endpoint
    prefix_state = gr.State(value=PREFIXES) #query prefixes
    base_map_state = gr.State() #state to hold "base map" after central parcel is found
    gr.Markdown("# Toronto Housing Potential Dashboard")
    with gr.Row():
        with gr.Column(scale=1):
            addr_input = gr.Textbox(label="Toronto Address", placeholder="e.g. 40 St George St")
            search_btn = gr.Button("Search Parcel", variant="primary")
            selected_parcel_uri = gr.Textbox(label="Detected Parcel ID(s)", interactive=False)
            res_status = gr.Textbox(label="Verification", interactive=False)
            with gr.Accordion("View SPARQL Query", open=False):
                query_display = gr.Code(language="sql")
        with gr.Column(scale=2):
            map_plot = gr.Plot(label="Map View")
    #parcel attribute view
    gr.Markdown("---")
    gr.Markdown("### 🛠️ Advanced Queries")
    query_dropdown = gr.Dropdown(
        choices=["Select...", "Parcel Attributes", "Available Services", "Applicable Zoning","Land Use", "Neighbourhood Demographics", "Zoning Compliance"],
        label="Choose a query to run on this parcel",
        value="Select..."
    )
    #zoning compliance details dropdown
    secondary_drp = gr.Dropdown(choices=[], visible=False, label="Select Attribute to Review", interactive=True)
    # This shows the text updates from the router
    #status_update = gr.Textbox(label="Query Status", interactive=False)
    # --- Results Table ---
    results_table = gr.Dataframe(interactive=False, visible=False)
    # --- Results Listing (columns) ---
    with gr.Row():
        # Column 1: Markdown list
        col1_output = gr.Markdown(visible=False)
        # Column 2: Single value
        col2_output = gr.Markdown(visible=False)
    # --- GraphDB visual graph ---
    # This component will render the interactive graph
    graph_output = gr.HTML(label="Visual Graph")
#event logic        
    search_btn.click(fn=process_address, inputs=[endpoint_state,addr_input], outputs=[selected_parcel_uri, res_status, query_display, map_plot, base_map_state])
    # Dropdown change triggers the specific query logic
    query_dropdown.change(
        fn=query_router,
        inputs=[query_dropdown, endpoint_state, prefix_state, selected_parcel_uri, base_map_state],
        outputs=[results_table, map_plot, col1_output, col2_output,secondary_drp,graph_output]
    )
    #Secondary dropdown triggers additional logic
    secondary_drp.change(
        fn = secondary_router,
        inputs = [query_dropdown,secondary_drp,endpoint_state,prefix_state,selected_parcel_uri,base_map_state],
        outputs = [results_table,map_plot]
    )
#demo.launch(server_name="0.0.0.0", server_port=7860, share=True)
demo.launch()