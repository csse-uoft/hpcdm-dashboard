"""SPARQL Client for RDF Graph Database Interaction.

The sparql_client module defines the logic required to retrieve and process spatial and 
regulatory data from an RDF graph database (optimized for GraphDB 11.2). 
It includes templates for SPARQL queries related to parcel attributes, 
zoning compliance, land use, and neighborhood demographics.

The core utility, `run_sparql_to_data`, executes these queries and returns 
results as cleaned, typed pandas DataFrames.

Todo:
    * Refactor code to move the parcel-finder query from 
      process_address in geocode_components.py here.
    * Refactor fetch_zoning_data (the processing logic should be implemented in a separate function in utils)
    * Test & implement the pattern ?cp rdfs:label ?cp_label in fetch_compliance_properties as optional
    * Include support for unit mismatches in fetch_zoning_compliance
"""

from SPARQLWrapper import SPARQLWrapper, JSON
import socket
from urllib.error import URLError 
import pandas as pd
import gradio as gr
def fetch_parcel_attributes(endpoint,prefixes,pid):
    """Retrieves and formats parcel attributes via a SPARQL query.

    Constructs and executes a SPARQL query to fetch the labels, numerical values, 
    and units for attributes associated with a specific parcel IRI.

    Args:
        endpoint (str): The SPARQL endpoint URL.
        prefixes (str): SPARQL namespace declarations.
        pid (str): The persistent identifier (IRI) of the parcel.

    Returns:
        pd.DataFrame: A DataFrame with columns ['attribute', 'value', 'unit'], as defined by table_vars.
    """
    table_vars = ['attribute', 'value', 'unit']
    query =  f"""{prefixes}

SELECT ?attribute ?value ?unit WHERE {{
	<{pid}> a hp:Parcel;
		?att ?q.
    ?q i72:hasValue [i72:hasNumericalValue ?value;
								i72:hasUnit ?u].
    ?att rdfs:label ?attribute.
    ?u rdfs:label ?unit.
  # Filter out ?attribute if there exists a more specific sub-property (?sub) that defines the value for the parcel
  FILTER NOT EXISTS {{
    ?sub rdfs:subPropertyOf+ ?att .
    <{pid}> ?sub ?q .
    FILTER (?sub != ?att)
  }}
}} """

    return run_sparql_to_data(query, endpoint, table_vars)

def fetch_landuse(endpoint,prefixes,pid):
    """Retrieves allowed and current land use (if available, as captured by building use) for a specific parcel.

    Args:
        endpoint (str): The SPARQL endpoint URL.
        prefixes (str): SPARQL namespace declarations.
        pid (str): The persistent identifier (IRI) of the parcel.

    Returns:
        pd.DataFrame: A DataFrame containing 'allowed_use' and 'current_use', as defined by table_vars.
    """
    table_vars=["allowed_use","current_use"]
    query = f"""
    {prefixes}

SELECT ?allowed_use ?current_use WHERE {{
    #if we are looking for the neighbourhood of a specific parcel
    <{pid}> hp:zonedAsType ?zt.
	?zt oz:allowsUse ?u.
    ?u genprop:hasName ?allowed_use.
    OPTIONAL {{
        ?x bdg:use [code:hasCode [genprop:hasName ?current_use]].
        ?x hp:occupies ?p.
    }}
}}"""
    return run_sparql_to_data(query, endpoint, table_vars)

def fetch_neighbourhood_demographics(endpoint,prefixes,pid,census_characteristics):
    """Retrieves neighborhood demographic data based on census characteristics.

    Args:
        endpoint (str): The SPARQL endpoint URL.
        prefixes (str): SPARQL namespace declarations.
        pid (str): The parcel IRI used to identify the neighborhood.
        census_characteristics (list[str]): A list of URIs representing the 
            demographic categories to retrieve.

    Returns:
        pd.DataFrame: A DataFrame containing neighborhood name, population, 
            units, and census tract labels, as definfed by table_vars.
    """
    query_vars = ["xlabel", "neighbourhood_name", "population", "unit_label", "unit", "ct","cwkt"]

    # Stage 1: Neighbourhood Discovery
    stage_1 = f"""
    {{
        SELECT ?n ?neighbourhood_name WHERE {{  
            <{pid}> loc:hasLocation ?ploc.
            ?n a tor:Neighborhood;
               loc_old:hasLocation ?nloc;
               rdfs:comment ?neighbourhood_name.
            ?ploc geo:sfWithin ?nloc.
        }}
    }}"""

    # Stage 2: Dynamic Census Characteristic Blocks
    char_blocks = []
    for char_uri in census_characteristics:
        # Wrap in brackets if it's a full URI, otherwise assume prefixed
        formatted_uri = f"<{char_uri}>" if char_uri.startswith("http") else char_uri
        
        block = f"""    {{
        ?x a {formatted_uri};
           cacensus:hasLocation ?characteristic_area;
           i72:hasValue [i72:hasNumericalValue ?population;
                         i72:hasUnit ?unit];
            rdfs:comment ?xlabel.   #indicator label
        ?characteristic_area tor:inNeighbourhood ?n;
            loc_old:hasLocation [geo:asWKT ?cwkt];
            rdfs:label ?ct. #census tract label
        OPTIONAL {{ ?unit rdfs:label ?unit_label. }}
    }}"""
        char_blocks.append(block)

    # Join the blocks with UNION
    union_stage = "\n    UNION\n".join(char_blocks)

    # Assemble final query
    query = f"""{prefixes}

SELECT ?xlabel ?neighbourhood_name ?population ?unit_label ?unit ?ct ?cwkt WHERE {{
{stage_1}
    {{
{union_stage}
    }}
}}"""
 
    #run sparql query; convert to table
    df = run_sparql_to_data(query, endpoint,query_vars)
    #if there are no query results, return "Unknown"
    if df.empty:
        df.loc[0] = "unknown" 
    return df

def fetch_service_classes(endpoint, prefixes):
    """Retrieves leaf-level Service classes defined in the graph.

    Filters out classes that have further specific subclasses to return 
    only the most granular service types.

    Args:
        endpoint (str): The SPARQL endpoint URL.
        prefixes (str): SPARQL namespace declarations.

    Returns:
        pd.DataFrame: A DataFrame with a single column 'servicetype'.
    """
    sparql = SPARQLWrapper(endpoint)
    vars_list = ["servicetype"]
    class_query = f"""{prefixes}

SELECT distinct ?servicetype WHERE {{

        #service types (TBD: what level should we capture?)
        ?servicetype rdfs:subClassOf* hp:Service.
    #filter any classes that have subclasses
      FILTER NOT EXISTS {{
    ?sub rdfs:subClassOf* ?servicetype .
    FILTER (?sub != ?servicetype && ?sub !=owl:Nothing)
  }}
}}"""
    return run_sparql_to_data(class_query,endpoint,vars_list)

def fetch_service_data(endpoint,prefixes, pid, servicetype):
    """Retrieves services available to a parcel based on defined catchment area or service radius.

    Args:
        endpoint (str): The SPARQL endpoint URL.
        prefixes (str): SPARQL namespace declarations.
        pid (str): The parcel IRI.
        servicetype (str): The IRI of the service class to filter by.

    Returns:
        pd.DataFrame: A DataFrame containing service labels, names, capacity, 
            and spatial WKT data. Note: spatial WKT data is currently only mapped for services with site locations.
    """
    #clean pid, servicetype
  #  pid = str(pid).strip("<>")
 #   servicetype = str(servicetype).strip("<>")
#    sparql = SPARQLWrapper(endpoint)  
    query_vars = ["servicelabel", "servicename", "cap_type","cap_avail", "cap_unit", "swkt"]
    detail_query = f"""
            {prefixes}

SELECT ?servicelabel ?servicename ?cap_type ?cap_avail ?cap_unit ?swkt WHERE {{
{{
#services with suitable catchment areas
    <{pid}> hp:servicedBy ?s;
    	a hp:AdministrativeArea.
    ?s a <{servicetype}>;
    	a hp:Service.
    <{servicetype}> rdfs:label ?servicelabel.
    #service site name, if defined
    OPTIONAL {{
        ?s hp:providedFromSite ?site.		
    ?site genprop:hasName ?servicename.}}
    #TBD instead of showing site location (may not exist) return catchment area as swkt?
    #?s service:hasCatchmentArea [geo:asWKT ?swkt].
    #service capacity
    ?s res:hasAvailableCapacity ?cap.
    ?cap i72:hasValue [i72:hasNumericalValue ?cap_avail;
       									i72:hasUnit ?u];
    					rdf:type ?cap_type_class.
	?cap_type_class rdfs:label ?cap_type.
    ?u rdfs:label ?cap_unit.
    # Filter out the "Generics" (owl:Thing and owl:Nothing)
    FILTER(?cap_type_class != owl:Thing && ?cap_type_class != owl:Nothing)
    FILTER(!isBlank(?cap_type_class))

    # The Leaf Constraint: 
    # Ensure there isn't another type on this node that is a SUBCLASS of our candidate.
    FILTER NOT EXISTS {{
        ?cap rdf:type ?moreSpecific .
        ?moreSpecific rdfs:subClassOf+ ?cap_type_class .
        
        # Standard safety filters
        FILTER(?moreSpecific != ?cap_type_class)
        FILTER(?moreSpecific != owl:Nothing)
    }}
}}
UNION
{{
	#services with suitable service radius
	#parcel location
    <{pid}> loc:hasLocation [geo:asWKT ?pwkt];
    	a hp:AdministrativeArea.
    	
    #service site location(s)
    ?s a <{servicetype}>;
    	a hp:Service;
    	hp:providedFromSite ?site.		
    OPTIONAL {{?site genprop:hasName ?servicename.}}
    ?site loc:hasLocation ?sloc.
    ?sloc geo:asWKT ?swkt.
    <{servicetype}> rdfs:label ?servicelabel.
    
    #service-defined radius, in metres
    ?s hp:hasServiceRadius [i72:hasValue [i72:hasNumericalValue ?max_d;
    																i72:hasUnit i72:metre]].

	#(shortest) distance between the edge of the parcel and the service network 
	BIND(geof:distance(?pwkt, ?swkt, uom:metre) AS ?distance)
	#limit distance to within the defined service radius
	FILTER (?distance <= ?max_d)
	
    #service capacity
    ?s res:hasAvailableCapacity ?cap.
    ?cap i72:hasValue [i72:hasNumericalValue ?cap_avail;
       									i72:hasUnit ?u];
    					rdf:type ?cap_type_class.
    ?u rdfs:label ?cap_unit.
	?cap_type_class rdfs:label ?cap_type.
    # Filter out the "Generics" (owl:Thing and owl:Nothing)
    FILTER(?cap_type_class != owl:Thing && ?cap_type_class != owl:Nothing)
    FILTER(!isBlank(?cap_type_class))

    # The Leaf Constraint: 
    # Ensure there isn't another type on this node that is a SUBCLASS of our candidate.
    FILTER NOT EXISTS {{
        ?cap rdf:type ?moreSpecific .
        ?moreSpecific rdfs:subClassOf+ ?cap_type_class .
        
        # Standard safety filters
        FILTER(?moreSpecific != ?cap_type_class)
        FILTER(?moreSpecific != owl:Nothing)
    }}
}}
}}"""

            # Fetch and append results for each servce
    return run_sparql_to_data(detail_query,endpoint, query_vars)

def fetch_zoning_data(endpoint,prefixes, pid, progress=gr.Progress()):
    """Retrieves zoning regulations and their associated map geometries (i.e., area of the zone) for a parcel.

    Args:
        endpoint (str): The SPARQL endpoint URL.
        prefixes (str): SPARQL namespace declarations.
        pid (str): The parcel IRI.
        progress (gr.Progress): Gradio progress tracker.

    Returns:
        tuple[pd.DataFrame, list[dict]]: A tuple containing the results DataFrame 
            and a list of map features (WKT and labels).
    """
    table_vars=["zstring", "ctlabel","constrained_property","limit","unit","regwkt"]
    map_features = []
    query = f"""
    {prefixes}

SELECT distinct ?reg ?zstring ?ctlabel ?constrained_property ?limit ?unit ?regwkt WHERE {{

    {{	#for efficiency first, evaluate this part
SELECT ?reg ?zstring ?ctlabel ?constrained_property ?limit ?unit ?regwkt ?ploc ?loc WHERE {{
    #if we are looking for the neighbourhood of a specific parcel
    <{pid}> hp:zonedForConstraint ?c;
    	loc:hasLocation ?ploc.
    
    #regulations defined in law
    ?reg hp:definedIn ?source.
    ?source a hp:ZoningBylaw.
    #the regulation that designates the zoning type for an area
    ?reg a hp:Regulation;
    hp:appliesTo [loc:hasLocation ?loc];
    hp:specifiesConstraint ?c.
    	?c i72:hasValue ?v;
                            hp:constrains [i72:parameter_of_var [i72:hasName ?cp];
                                        i72:description_of ?p];
    						#constraint type
    						rdf:type ?constraint_type.
    #constraint value
    ?v i72:hasNumericalValue ?limit.
    OPTIONAL {{?v i72:hasUnit [rdfs:label ?unit]}}
   	OPTIONAL {{?reg genprop:hasName ?zstring. }} #zoning string label, if applicable
    #quantity constraint subtype (allowance, requirement, ...) to clarify the nature of the regulation
    ?constraint_type rdfs:subClassOf hp:QuantityConstraint;
    		rdfs:label ?ctlabel.
    FILTER (?constraint_type != hp:QuantityConstraint)
    
	#location of the regulation 
    ?loc geo:asWKT ?regwkt.
    #property label
    OPTIONAL{{?cp rdfs:label ?constrained_property}}
    }}
}}
        ?ploc geo:sfIntersects ?loc. #regulations can apply to multiple areas - we only want to display the area that the parcel is in.
}}
    """
    #empty dataframe
    df = pd.DataFrame(columns=table_vars)
    #run sparql query; convert to table and add features to map
    df = run_sparql_to_data(query, endpoint,table_vars)
    new_features=[]
    if not df.empty:
        # Extract map features -- what label do we give the regulation area?
        # Filter the DataFrame to only include rows with valid WKTs
        valid_wkts = df[df['regwkt'].notna() & (df['regwkt'] != '-')]

        # Use a list comprehension to build map_features instantly
        map_features = [
            {"wkt": row['regwkt'], "label": row['zstring']} 
            for _, row in valid_wkts.iterrows()
        ]

    return df, map_features

def fetch_compliance_properties(endpoint,prefixes):
    """Retrieves all property types currently defined in zoning regulations.

    Args:
        endpoint (str): The SPARQL endpoint URL.
        prefixes (str): SPARQL namespace declarations.

    Returns:
        pd.DataFrame: A DataFrame with 'cp' (property IRI) and 'cp_label' (the defined label for the property).
    """
    query_vars = ['cp','cp_label']
    query = f"""
    {prefixes}
    SELECT DISTINCT ?cp ?cp_label  WHERE {{
    
    #regulations defined in law
    ?reg hp:definedIn ?source.
    ?source a hp:ZoningBylaw.
    #the regulation that designates the zoning type for an area
    ?reg a hp:Regulation;
    hp:appliesTo [loc:hasLocation ?loc];
    hp:specifiesConstraint ?c.
    	?c i72:hasValue ?v;
                            hp:constrains [i72:parameter_of_var [i72:hasName ?cp];
                                        i72:description_of ?p].
    ?cp rdfs:label ?cp_label.
    
    }}
    """
    df = run_sparql_to_data(query, endpoint,query_vars)
    return df
def fetch_zoning_compliance(endpoint,prefixes,pid,property):
    """Analyzes zoning compliance for a specific property across nearby parcels.

    Args:
        endpoint (str): The SPARQL endpoint URL.
        prefixes (str): SPARQL namespace declarations.
        pid (str): The source parcel IRI to search around (200m radius).
        property (str): The property IRI (e.g., height, set-back) to check.

    Returns:
        pd.DataFrame: A DataFrame including nearby parcel IRIs, regulatory limits, 
            actual values, and a calculated 'compliancestatus'.
        Compliance status is defined as:
            * 'noncompliant' if the limit is violated (i.e., the parcel demonstrates a greater/lower value for a maximum/minimum constraint),
            * 'unknown' if the actual value is missing
            * 'incompatible units' if the units in the limit and the actual value aren't aligned
    """
    query_vars = ["nearbyp", "nearbypwkt", "zstring", "ctlabel","limit", "unit", "actualvalue", "actualunit", "compliancestatus"]
    query = f"""
    {prefixes}

    SELECT DISTINCT ?nearbyp ?nearbypwkt ?zstring ?ctlabel ?limit ?vunit ?actualvalue ?actualunit ?compliancestatus WHERE {{
    #if we are looking for the neighbourhood of a specific parcel
    <{pid}> loc:hasLocation [geo:asWKT ?pwkt].
    
    #identify nearby parcels and attribute of interest
      ?nearbyp a hp:Parcel ;
        loc:hasLocation [geo:asWKT ?nearbypwkt].
    
    FILTER(
        geof:distance(?pwkt, ?nearbypwkt, uom:metre) < 200
    )
    
    #zoning constraints that apply to nearby parcels
    ?nearbyp hp:zonedForConstraint ?c.
    #regulations defined in law
    ?reg hp:definedIn ?source.
    ?source a hp:ZoningBylaw.
    #the regulation that defines the constraint
    ?reg a hp:Regulation;
    hp:appliesTo [loc:hasLocation ?loc];
    hp:specifiesConstraint ?c.
    	?c i72:hasValue ?v;
                            hp:constrains [i72:parameter_of_var [i72:hasName <{property}>];
                                        i72:description_of ?p];
    						#constraint type
    						rdf:type ?constraint_type.
    #constraint value
    ?v i72:hasNumericalValue ?limit.
    OPTIONAL {{?v i72:hasUnit ?vunit.
        ?vunit rdfs:label ?unit.}}
   	OPTIONAL {{?reg genprop:hasName ?zstring. }} #zoning string label, if applicable
    #quantity constraint subtype (allowance, requirement, ...) to clarify the nature of the regulation
    ?constraint_type rdfs:subClassOf hp:QuantityConstraint;
    		rdfs:label ?ctlabel.
    FILTER (?constraint_type != hp:QuantityConstraint)
    
    #the actual value of the constrained attribute for the parcel, if known
    OPTIONAL {{
        ?nearbyp <{property}> [i72:hasValue [i72:hasNumericalValue ?actualvalue;
            						i72:hasUnit ?aunit]].
                ?aunit rdfs:label ?actualunit.
    }}
   #or, the actual value of the constrained attribute for the building, if known
    OPTIONAL {{
        ?b hp:occupies ?nearbyp;
        	<{property}> [i72:hasValue [i72:hasNumericalValue ?actualvalue;
            						i72:hasUnit ?aunit]].
        ?aunit rdfs:label ?actualunit.
    }}
    
    #logic to define a new column to identify whether a constraint is violated
    BIND(COALESCE(
    IF(!BOUND(?actualvalue) || !BOUND(?limit), "unknown",
        IF(BOUND(?vunit) && BOUND(?aunit) && ?vunit != ?aunit, "incompatible units",
        IF(?constraint_type = hp:QuantityAllowance,
            IF(?actualvalue > ?limit, "noncompliant", "compliant"),
            IF(?constraint_type = hp:QuantityRequirement,
            IF(?actualvalue < ?limit, "noncompliant", "compliant"),
            IF(?constraint_type = hp:QuantityEquivalence,
                IF(?actualvalue != ?limit, "noncompliant", "compliant"),
                "unknown"
            )
            )
        )
        )
    ),
    "unknown" # A safety net if the IF logic crashes
    ) AS ?compliancestatus)
}}
    """
    df = run_sparql_to_data(query, endpoint,query_vars)
    return df
def fetch_allowed_use(endpoint,prefixes, pid):
    """Retrieves allowed land uses for a parcel based on zoning bylaws.

    Args:
        endpoint (str): The SPARQL endpoint URL.
        prefixes (str): SPARQL namespace declarations.
        pid (str): The parcel IRI.

    Returns:
        pd.DataFrame: A DataFrame of allowed uses. Returns 'unknown' if empty.
    """

    query_vars = ["allowed_use"]
    query = f"""
    {prefixes}
    SELECT ?allowed_use WHERE {{
    #if we are looking for the neighbourhood of a specific parcel
    <{pid}> hp:zonedAsType ?zt.
	?zt oz:allowsUse ?u.
    ?u genprop:hasName ?allowed_use.
}}
    """
    #run sparql query; convert to table and add features to map
    df = run_sparql_to_data(query, endpoint,query_vars)
    #if there are no query results, i.e. the parcel is not in the official plan, return "Unknown"
    if df.empty:
        df.loc[0] = "unknown" 
    return df

def fetch_current_use(endpoint,prefixes,pid):
    """Retrieves the current recorded use of a parcel from building data.

    Args:
        endpoint (str): The SPARQL endpoint URL.
        prefixes (str): SPARQL namespace declarations.
        pid (str): The parcel IRI.

    Returns:
        pd.DataFrame: A DataFrame of current uses. Returns 'unknown' if empty.
    """

    query_vars = ["current_use"]
    query = f"""
    {prefixes}
SELECT DISTINCT ?current_use WHERE {{
    #if we are looking for the neighbourhood of a specific parcel
    ?x hp:occupies <{pid}>;
        bdg:use [code:hasCode [genprop:hasName ?current_use]].
    
    }}
    """
    #run sparql query; convert to table
    df = run_sparql_to_data(query, endpoint,query_vars)
    #if there are no query results, return "Unknown"
    if df.empty:
        df.loc[0] = "unknown" 
    return df

def fetch_zoning_avg(endpoint,prefixes):
    """Retrieves the average values for any attributes defined for the parcel.
    Todo: complete doc"""
    query_vars = ['att', 'avg_label', 'u', 'u_label', 'avg']
    query = f"""
    {prefixes}
    SELECT ?ctlabel ?avg_label ?u_label (AVG(?limit) AS ?avg)
        WHERE {{
            # Regulations defined in law
            ?reg hp:definedIn ?source.
            ?source a hp:ZoningBylaw.
            
            # The regulation that designates the zoning type for an area
            ?reg a hp:Regulation;
                hp:specifiesConstraint ?c.
            
            ?c i72:hasValue ?v;
            hp:constrains [ i72:parameter_of_var [i72:hasName ?cp];
                            i72:description_of ?p ];
            rdf:type ?constraint_type.
            
            # Constraint value
            ?v i72:hasNumericalValue ?limit.
            
            OPTIONAL {{ ?v i72:hasUnit [rdfs:label ?u_label] }}
            
            # Property label
            OPTIONAL {{ ?cp rdfs:label ?avg_label }}
            FILTER (?limit >=0) #ignore zoning with no limit
        }}
        GROUP BY ?ctlabel ?avg_label ?u_label
    """
    #run sparql query; convert to table
    df = run_sparql_to_data(query, endpoint,query_vars)
    #if there are no query results, return "Unknown"
    if df.empty:
        df.loc[0] = "unknown" 
    return df

def fetch_demographics_avg(endpoint,prefixes):
    """Retrieves the averagee values for the key census characteristics
    Todo: complete documentation, generalize for arbitrary list of characteristics"""
    query_vars = ['avg_label', 'avg', 'u_label']
    query= f"""
    {prefixes}
    SELECT ?avg_label (AVG(?val) AS ?avg) ?u_label
    WHERE {{
    {{
        # Population density
        ?x a cacensus:PopulationDensity2016 ;
        i72:hasValue [ i72:hasNumericalValue ?val ;
                        i72:hasUnit ?unit ] .
        cacensus:PopulationDensity2016 rdfs:label ?avg_label .
        OPTIONAL {{?unit rdfs:label ?u_label .}}
    }}
    UNION
    {{
        # Avg Income
        ?x a <http://ontology.eil.utoronto.ca/tove/cacensus#AverageAfterTaxIncome25Sample2016> ;
        i72:hasValue [ i72:hasNumericalValue ?val ;
                        i72:hasUnit ?unit ] .
        <http://ontology.eil.utoronto.ca/tove/cacensus#AverageAfterTaxIncome25Sample2016> rdfs:label ?avg_label .
        OPTIONAL {{ ?unit rdfs:label ?u_label . }}
    }}
    UNION
    {{
        # Total Private Dwellings
        ?x a <http://ontology.eil.utoronto.ca/tove/cacensus#TotalPrivateDwellings2016> ;
        i72:hasValue [ i72:hasNumericalValue ?val ;
                        i72:hasUnit ?unit ] .
        <http://ontology.eil.utoronto.ca/tove/cacensus#TotalPrivateDwellings2016> rdfs:label ?avg_label.
        OPTIONAL {{ ?unit rdfs:label ?u_label . }}
    }}
    }}
    GROUP BY ?avg_label ?u_label
    """
    #run sparql query; convert to table
    df = run_sparql_to_data(query, endpoint,query_vars)
    #if there are no query results, return "Unknown"
    if df.empty:
        df.loc[0] = "unknown" 
    return df

def fetch_service_avg(endpoint,prefixes,pid,servicetype):
    """Todo: doc"""
    query_vars = ['avg_label', 'avg', 'u_label']
    query = f"""
    {prefixes}
    SELECT ?avg_label ?u_label (AVG(xsd:decimal(?cap)) AS ?avg)
WHERE {{
    # 1. Identify Leaf Service Types
    ?s a <{servicetype}> .
    <{servicetype}> rdfs:label ?avg_label .

    # 2. Capacity Data
    ?s res:hasAvailableCapacity ?avail_cap .
    ?avail_cap rdf:type ?avail_cap_type ;
               i72:hasValue ?valNode .
    ?valNode i72:hasNumericalValue ?cap .
    
    OPTIONAL {{ 
        ?valNode i72:hasUnit ?cap_unit .
        ?cap_unit rdfs:label ?u .
    }}

    # 3. Capacity Leaf Logic
    FILTER(!isBlank(?avail_cap_type) && ?avail_cap_type != owl:Thing)
    
    FILTER NOT EXISTS {{
        ?avail_cap rdf:type ?moreSpecific .
        ?moreSpecific rdfs:subClassOf ?avail_cap_type .
        FILTER(?moreSpecific != ?avail_cap_type && ?moreSpecific != owl:Nothing)
    }}
    ?avail_cap_type rdfs:label ?cap_type_label.
    BIND(CONCAT(?cap_type_label," (",?u,")") AS ?u_label)
}}
GROUP BY ?avg_label ?u_label"""
    return run_sparql_to_data(query,endpoint,query_vars)

def run_sparql_to_data(query, endpoint, columns):
    """Executes a SPARQL query and converts the JSON results to a pandas DataFrame.

    Handles the conversion of SPARQL JSON bindings to a tabular format, 
    attempts to infer numeric types, and utilizes nullable pandas dtypes.

    Args:
        query (str): The full SPARQL query string.
        endpoint (str): The SPARQL endpoint URL.
        columns (list[str]): The variable names to extract from the SELECT clause.

    Returns:
        pd.DataFrame: The processed results. Returns an empty DataFrame on error.
    """

    #timeout
    timeout_limit = 60
    sparql = SPARQLWrapper(endpoint)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    sparql.setTimeout(timeout_limit)

    try:
        results = sparql.query().convert()
        bindings = results.get("results", {}).get("bindings", [])
		# Create list of dicts for easy DataFrame conversion
        data = []
        for row in bindings:
        	#Extract only the variables in 'columns
            data.append({col: row.get(col, {}).get('value', None) for col in columns})

        df = pd.DataFrame(data, columns=columns)

        # Attempt numeric conversion per column
        for col in df.columns:
            try:
                # Attempt to convert the column to numeric
                # errors='raise' is the default; if it fails, it hits the 'except'
                df[col] = pd.to_numeric(df[col])
            except (ValueError, TypeError):
                # If conversion fails (e.g., it's a WKT or Unit string), 
                # we just leave the column as it is.
                continue

        # Intelligent conversion to best-fit nullable types (String, Int64, etc.)
        df = df.convert_dtypes()

        return df
    except socket.timeout:
        raise gr.Error("Query Timed Out: The SPARQL endpoint is currently busy. Please try again in a moment.")
    except URLError as e:
        # URLError often wraps a timeout, so we check the reason
        if isinstance(e.reason, socket.timeout):
            raise gr.Error("Query Timed Out: The SPARQL endpoint is currently busy. Please try again in a moment.")
        return f"Network Error: {str(e.reason)}"
    except Exception as e:
        print(f"Query Error: {e}")
        return pd.DataFrame(columns=columns)
    
def construct_parcel_attributes(prefixes,pid):
    """Constructs a graph overview of the parcel attributes pattern for a given pid
    Returns string, doesn't run query (output to be used for visual graph embedding)
    Todo: complete doc"""
    query = f"""
    {prefixes}
    CONSTRUCT {{
    <{pid}> a hp:Parcel;
    	?att ?measure.
    ?measure i72:hasValue ?valnode.
    ?valnode i72:hasNumericalValue ?a;
            i72:hasUnit ?u;
		    rdfs:label ?labelValue .

}} WHERE {{
    <{pid}> a hp:Parcel;
    	?att ?measure.
    ?measure i72:hasValue ?valnode.
    ?valnode i72:hasNumericalValue ?a;
            i72:hasUnit ?u.   
    ?att rdfs:label ?attlabel.
    BIND(STR(?a) as ?labelValue)

}}"""
    return query


def construct_neighbourhood_demographics(prefixes,pid):
    """Returns a query string to construct graph summary of the neighbourhood demographics query output
    Todo: 
        generalize for arbitrary census characteristic list
        complete doc"""
    query = f"""
    {prefixes}
    CONSTRUCT {{
    <{pid}> loc:hasLocation ?ploc.
    ?n a tor:Neighborhood;
    	loc_old:hasLocation ?nloc.
    ?ploc geo:sfWithin ?nloc.
    ?x cacensus:hasLocation ?characteristic_area.
    ?characteristic_area tor:inNeighbourhood ?n.
    
    ?x i72:hasValue ?valnode.
    ?valnode i72:hasNumericalValue ?population;
    				i72:hasUnit ?unit.
}} WHERE {{
#stage 1 find tor:Neighborhood for parcel
    {{
        SELECT ?n ?neighbourhood_name ?ploc ?nloc WHERE {{  
    #if we are looking for the neighbourhood of a specific parcel
    <{pid}> loc:hasLocation ?ploc.
    ?n a tor:Neighborhood;
    	loc_old:hasLocation ?nloc;
        rdfs:comment ?neighbourhood_name.
    #find the neighbourhood the parcel is located in
    ?ploc geo:sfWithin ?nloc.
        }}
    }}
    #stage 2: union of all required census characteristics:
    {{
    {{#population density
    #characteristic values for census tracts within a neighbourhood
    ?x a cacensus:PopulationDensity2016;
    cacensus:hasLocation ?characteristic_area;
		i72:hasValue [i72:hasNumericalValue ?population;
    				i72:hasUnit ?unit];
            rdfs:comment ?xlabel.
    ?characteristic_area tor:inNeighbourhood ?n;
            loc_old:hasLocation [geo:asWKT ?cwkt].
    #unit label
    ?unit rdfs:label ?unit_label.
    }}
	UNION
    {{#avg income
    #characteristic values for census tracts within a neighbourhood
    ?x a <http://ontology.eil.utoronto.ca/tove/cacensus#AverageAfterTaxIncome25Sample2016>;
    cacensus:hasLocation ?characteristic_area;
		i72:hasValue [i72:hasNumericalValue ?population;
    				i72:hasUnit ?unit];
            rdfs:comment ?xlabel.
    ?characteristic_area tor:inNeighbourhood ?n.
    OPTIONAL {{#unit label
    ?unit rdfs:label ?unit_label.
            }}
    }}
        	UNION
    {{#total private dwellings
    #characteristic values for census tracts within a neighbourhood
    ?x a <http://ontology.eil.utoronto.ca/tove/cacensus#TotalPrivateDwellings2016>;
    cacensus:hasLocation ?characteristic_area;
		i72:hasValue [i72:hasNumericalValue ?population;
    				i72:hasUnit ?unit];
            rdfs:comment ?xlabel.
    ?characteristic_area tor:inNeighbourhood ?n.
    OPTIONAL {{#unit label
    ?unit rdfs:label ?unit_label.
            }}
    }}
}}
}}"""
    return query