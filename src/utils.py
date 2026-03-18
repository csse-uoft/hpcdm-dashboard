"""Utility functions for processing and aggregating urban data.

This module acts as the processing layer between the raw SPARQL client and 
the UI components. It handles iterative querying (e.g., looping through 
service classes), data cleaning, and the transformation of geographic 
results into structured lists for map rendering.

Functions in this module typically return both a pandas DataFrame for 
table display and a list of dictionaries for Plotly map features.
"""
from src.sparql_client import *
import gradio as gr
import numpy as np
def process_service_data(endpoint,prefixes,pid,progress=gr.Progress()):
    """Iteratively retrieves and aggregates service data for a parcel.

    This function first identifies all available service types in the graph, 
    then performs individual queries for each type to gather specific details 
    like site locations and capacities.
     Stage 1: Get classes. Stage 2: Loop through classes for details.

    Args:
        endpoint (str): The SPARQL endpoint URL.
        prefixes (str): SPARQL namespace declarations.
        pid (str): The persistent identifier (IRI) of the target parcel.
        progress (gr.Progress): Gradio progress tracker for UI feedback.

    Returns:
        tuple[pd.DataFrame, list[dict]]: A tuple containing:
            - final_df: Combined DataFrame of all found services.
            - map_features: List of dicts containing 'wkt', 'label', and 'servicename'.
    
    Todo:
        * Test and assess whether to include catchment areas for services (when available) in addition to service sites.
    """
    # --- STAGE 1: Get List of Service leaf classes defined in the graph ---
    progress(0, desc="Identifying Service Types...")
    class_names = fetch_service_classes(endpoint,prefixes)
    all_dfs = [] # List to hold individual service DataFrames
    all_avg_dfs = [] #service averages
    map_features = [] 

    for i, row in class_names.iterrows():
        try:
            servicetype = row['servicetype'] # Get the actual URI string
            #debug
            #print(servicetype)
            # Run a second query using both the parcel URI and the specific class name
            progress((i + 1) / len(class_names), desc=f"Querying Service: {servicetype}")
            service_df = fetch_service_data(endpoint,prefixes,pid,servicetype)
            service_avg_df = fetch_service_avg(endpoint,prefixes,pid,servicetype)
  
            new_features = []
            if not service_df.empty:
                # Extract map features before we modify the DF
                # Filter the DataFrame to only include rows with valid WKTs
                valid_wkts = service_df[service_df['swkt'].notna() & (service_df['swkt'] != '-')]
                
                # Use a list comprehension to build map_features 
                #include the service name for use as a hover label
                new_features = [
                    {"wkt": row['swkt'], "label": row['servicelabel'], "servicename": row['servicename']} 
                    for _, row in valid_wkts.iterrows()
                ]

                all_dfs.append(service_df)
                # Append the new batch to the master list
                map_features.extend(new_features)
            if not service_avg_df.empty:
                all_avg_dfs.append(service_avg_df)
                
        except Exception as e:
            print(f"Loop Error for {servicetype}: {e}")
            continue
    #initialize dataframe
    final_df = pd.DataFrame()
    final_avg_df = pd.DataFrame()

    # Final Aggregation
    if all_dfs:
        # Combine all service DataFrames into one
        final_df = pd.concat(all_dfs, ignore_index=True)
        final_avg_df = pd.concat(all_avg_dfs,ignore_index=True)
        # Convert numeric column
        final_df['cap_avail'] = pd.to_numeric(final_df['cap_avail'], errors='coerce')
        return final_df, final_avg_df, map_features
    else:
        return pd.DataFrame(),pd.DataFrame(), []
    
def process_neighbourhood_demographics(endpoint,prefixes,pid,census_characteristics):
    """Processes demographic query results and extracts (unique) census tracts in the neighbourhood for display.

    Args:
        endpoint (str): The SPARQL endpoint URL.
        prefixes (str): SPARQL namespace declarations.
        pid (str): The parcel IRI used to anchor the neighborhood search.
        census_characteristics (list[str]): List of census characteristic URIs.

    Returns:
        tuple[pd.DataFrame, list[dict]]: A tuple containing:
            - demo_df: Raw demographic results.
            - map_features: List of unique census tract WKTs and labels.
    """
    #initialize list of map features
    map_features=[]
    #query results dataframe
    demo_df = fetch_neighbourhood_demographics(endpoint,prefixes,pid,census_characteristics)
    #process location data
    if not demo_df.empty:
        # Extract map features before we modify the DF
        # Filter the DataFrame to only include rows with valid WKTs (cwkt column), drop any duplicates (no need to display the same census tract twice)
        valid_wkts = demo_df[demo_df['cwkt'].notna() & (demo_df['cwkt'] != '-')].drop_duplicates(subset=['cwkt', 'ct'])
        
        # Use a list comprehension to build map_features instantly
        map_features = [
            {"wkt": row['cwkt'], "label": row['ct']} 
            for _, row in valid_wkts.iterrows()
        ]
    return demo_df,map_features

def process_compliance_properties(endpoint,prefixes):
    """Formats constrained (by zoning bylaws) properties into a list compatible with Gradio dropdowns.

    Args:
        endpoint (str): The SPARQL endpoint URL.
        prefixes (str): SPARQL namespace declarations.

    Returns:
        list[tuple[str, str]]: A list of (label, uri) tuples.
    """
    df = fetch_compliance_properties(endpoint,prefixes)
    property_list = list(zip(df['cp_label'], df['cp']))
    return property_list

def process_zoning_compliance(endpoint,prefixes,pid,property):
    """Processes zoning compliance for nearby parcels and extracts spatial status.

    Extracts a short-form Parcel ID for display and categorizes map features 
    by their compliance status (e.g., 'compliant', 'noncompliant').

    Args:
        endpoint (str): The SPARQL endpoint URL.
        prefixes (str): SPARQL namespace declarations.
        pid (str): The source parcel IRI.
        property (str): The specific property IRI to evaluate compliance for.

    Returns:
        tuple[pd.DataFrame, list[dict]]: A tuple containing:
            - df: Detailed compliance DataFrame.
            - map_features: List of nearby parcel geometries with status labels.
    Todo:
        * move the distance limit for 'nearby' to a parameter of this function
    """

    #initialize list of map features
    map_features=[]
    #query results dataframe
    df = fetch_zoning_compliance(endpoint,prefixes,pid,property)
    #add nearby parcels to list
    #label parcels as "Noncompliant" or "Compliant" depending on the value of the attribute "isviolated"
    #add a secondary label for the parcel ID (namespace stripped)
    nearbypcol = df['nearbyp'].str.extract(r'([^/#]+)$', expand=False) # This regex looks for the last / or # and takes everything following it
    df.insert(0,'nearbyp_short',nearbypcol)
    if not df.empty:
        # This prevents NumPy arrays from "sneaking" into the dictionary
        df['nearbypwkt'] = df['nearbypwkt'].astype(str)
        # Extract map features 
        # Filter the DataFrame to only include rows with valid WKTs (no NAs)
        valid_wkts = df.dropna(subset=['nearbypwkt']).copy()

        # Use a list comprehension to build map_features
        map_features = [
            {"wkt": str(row['nearbypwkt']).strip(), "label": row['compliancestatus'], "att_label": "Parcel ID", "att_value": row['nearbyp_short']} 
            for _, row in valid_wkts.iterrows()
        ]
        
        

    return df, map_features

def process_df_col_to_markdown_chips(df, column_name):
    """Converts a DataFrame column into a stylized Markdown string of HTML 'chips'.

    This helper is designed for the 'Land Use' section of the UI. It takes unique 
    values from the query results and wraps them in CSS-styled spans to create 
    a 'tag' or 'chip' look, making categories easily distinguishable.

    Args:
        df (pd.DataFrame): The source DataFrame from fetch_allowed_use or fetch_current_use.
        column_name (str): The name of the column to extract (e.g., 'Allowed Use').

    Returns:
        str: A Markdown string containing HTML-styled tags.
    """
    # 1. Handle Empty or 'Unknown' states gracefully
    if df.empty or (len(df) == 1 and str(df.iloc[0, 0]).lower() == "unknown"):
        return f"### {column_name}\n*No data available for this parcel.*"

    # 2. Extract unique, non-null values
    values = df[column_name].dropna().unique()
    
    # 3. Determine color scheme based on the category
    # Blue theme for 'Allowed' (Permissive), Grey theme for 'Current' (Fact)
    if "Allowed" in column_name:
        bg, text, border = "#e3f2fd", "#1565c0", "#90caf9"
    else:
        bg, text, border = "#f5f5f5", "#424242", "#e0e0e0"

    # 4. Generate the HTML Chips
    chips = []
    for val in values:
        chip_html = (
            f'<span style="background-color: {bg}; color: {text}; '
            f'padding: 4px 12px; margin: 4px 2px; border-radius: 16px; '
            f'border: 1px solid {border}; font-size: 0.85em; font-weight: 500; '
            f'display: inline-block; font-family: sans-serif;">'
            f'{val}</span>'
        )
        chips.append(chip_html)

    # 5. Return as a clean Markdown block
    return f"### {column_name}\n{' '.join(chips)}"