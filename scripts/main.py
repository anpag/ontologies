import os
import rdflib
import owlready2
import argparse
import csv
from google.cloud import bigquery

def ingest_ontology(owl_file_path, project_id, dataset_id):
    """
    Parses an OWL ontology, applies deductive reasoning via Owlready2 (HermiT), 
    and uploads the rich dictionary and topology rules to BigQuery.
    """
    import tempfile
    
    print(f"Pre-parsing ontology file: {owl_file_path} with rdflib to normalize format...")
    # Load with rdflib to normalize any Turtle syntax into RDF/XML for Owlready2
    g_init = rdflib.Graph()
    # Try to guess format or default to turtle
    fmt = "turtle" if owl_file_path.endswith(".ttl") else "xml"
    g_init.parse(owl_file_path, format=fmt)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as temp_xml_file:
        g_init.serialize(destination=temp_xml_file.name, format="xml")
        temp_xml_path = temp_xml_file.name
        
    print(f"Loading normalized ontology file into Owlready2...")
    
    # Owlready2 needs an absolute path
    abs_path = os.path.abspath(temp_xml_path)
    onto = owlready2.get_ontology(f"file://{abs_path}").load()
    
    print("Expanding graph with HermiT reasoning (this may take a minute)...")
    with onto:
        owlready2.sync_reasoner(debug=0)
        
    temp_owl = "/tmp/reasoned_onto.xml"
    onto.save(file=temp_owl, format="rdfxml")
    
    # Clean up the intermediate xml
    os.remove(temp_xml_path)
    
    print("Parsing reasoned ontology with rdflib...")
    g = rdflib.Graph()
    # Muting warning logs from rdflib for cleaner output
    import logging
    logging.getLogger("rdflib").setLevel(logging.ERROR)
    
    g.parse(temp_owl, format="xml")
    
    # Define standard namespaces
    OWL = rdflib.Namespace("http://www.w3.org/2002/07/owl#")
    RDFS = rdflib.Namespace("http://www.w3.org/2000/01/rdf-schema#")
    SKOS = rdflib.Namespace("http://www.w3.org/2004/02/skos/core#")
    IAO = rdflib.Namespace("http://purl.obolibrary.org/obo/IAO_")

    print("Materializing domain/range from OWL restrictions...")
    for s, p, o in g.triples((None, RDFS.subClassOf, None)):
        if isinstance(o, rdflib.term.BNode) and (o, rdflib.RDF.type, OWL.Restriction) in g:
            on_prop = g.value(o, OWL.onProperty)
            target = g.value(o, OWL.someValuesFrom) or g.value(o, OWL.allValuesFrom)
            if on_prop and target and not isinstance(s, rdflib.term.BNode):
                g.add((on_prop, RDFS.domain, s))
                g.add((on_prop, RDFS.range, target))

    print(f"Graph ready. Total triples: {len(g)}")

    # 1. Extract Rich Class Dictionary
    onto_classes = []
    class_labels = {}
    for s in g.subjects(rdflib.RDF.type, OWL.Class):
        if isinstance(s, rdflib.term.BNode):
            continue
            
        label = g.value(s, RDFS.label)
        class_name = str(label) if label else str(s).split('#')[-1].split('/')[-1]
        class_labels[str(s)] = class_name
        
        # Extract rich metadata
        definition = g.value(s, SKOS.definition) or g.value(s, IAO["0000115"]) or ""
        synonyms = [str(syn) for syn in g.objects(s, SKOS.altLabel)]
        example = g.value(s, SKOS.example) or g.value(s, IAO["0000112"]) or ""
        
        onto_classes.append({
            "uri": str(s),
            "class_name": class_name,
            "definition": str(definition),
            "synonyms": ", ".join(synonyms),
            "example": str(example)
        })

    # 2. Extract Topology Rules (SHACL)
    prop_labels = {}
    for s in g.subjects(rdflib.RDF.type, OWL.ObjectProperty):
        label = g.value(s, RDFS.label)
        prop_labels[str(s)] = str(label) if label else str(s).split('#')[-1].split('/')[-1]

    onto_rules = []
    for s in g.subjects(rdflib.RDF.type, OWL.ObjectProperty):
        for d in g.objects(s, RDFS.domain):
            for r in g.objects(s, RDFS.range):
                if not isinstance(d, rdflib.term.BNode) and not isinstance(r, rdflib.term.BNode):
                    domain_label = class_labels.get(str(d))
                    range_label = class_labels.get(str(r))
                    prop_label = prop_labels.get(str(s))
                    if domain_label and range_label and prop_label:
                        onto_rules.append({
                            "domain_class": domain_label,
                            "relationship_type": prop_label,
                            "range_class": range_label
                        })

    # Remove duplicates from rules
    onto_rules = [dict(t) for t in {tuple(d.items()) for d in onto_rules}]

    # 3. Extract Data Properties (Strict Node Schemas)
    data_prop_labels = {}
    for s in g.subjects(rdflib.RDF.type, OWL.DatatypeProperty):
        label = g.value(s, RDFS.label)
        data_prop_labels[str(s)] = str(label) if label else str(s).split('#')[-1].split('/')[-1]

    onto_data_properties = []
    for s in g.subjects(rdflib.RDF.type, OWL.DatatypeProperty):
        for d in g.objects(s, RDFS.domain):
            if not isinstance(d, rdflib.term.BNode):
                domain_label = class_labels.get(str(d))
                prop_label = data_prop_labels.get(str(s))
                
                # Try to get the expected datatype (e.g., xsd:string, xsd:float)
                expected_type = "string" # Default
                range_val = g.value(s, RDFS.range)
                if range_val:
                    expected_type = str(range_val).split('#')[-1]
                
                if domain_label and prop_label:
                    onto_data_properties.append({
                        "domain_class": domain_label,
                        "property_name": prop_label,
                        "expected_type": expected_type
                    })
                    
    onto_data_properties = [dict(t) for t in {tuple(d.items()) for d in onto_data_properties}]

    # 4. Upload to BigQuery
    client = bigquery.Client(project=project_id)
    
    # Upload Classes
    print(f"Uploading {len(onto_classes)} classes to BigQuery...")
    class_table_id = f"{project_id}.{dataset_id}.onto_classes"
    client.load_table_from_json(
        onto_classes, 
        class_table_id, 
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    ).result()

    # Upload Rules
    print(f"Uploading {len(onto_rules)} topology rules to BigQuery...")
    rules_table_id = f"{project_id}.{dataset_id}.onto_rules"
    client.load_table_from_json(
        onto_rules, 
        rules_table_id, 
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    ).result()
    
    # Upload Data Properties
    print(f"Uploading {len(onto_data_properties)} data properties to BigQuery...")
    data_props_table_id = f"{project_id}.{dataset_id}.onto_data_properties"
    client.load_table_from_json(
        onto_data_properties, 
        data_props_table_id, 
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    ).result()
    
    print("Ingestion complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rich Ontology Ingestion with Reasoning.")
    parser.add_argument("--owl", required=True, help="Path to the OWL file")
    parser.add_argument("--project", required=True, help="GCP Project ID")
    parser.add_argument("--dataset", required=True, help="BQ Dataset ID")
    
    args = parser.parse_args()
    ingest_ontology(args.owl, args.project, args.dataset)
