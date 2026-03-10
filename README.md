# HPCDM-dashboard
Gradio implementation of a housing potential dashboard using the City Digital Twin developed at the Urban Data Research Centre.

<!---
What the project does
Why the project is useful
How users can get started with the project
Where users can get help with your project
Who maintains and contributes to the project
-->
## Getting started
### File overview
(something like this, to be udpated)
gradio-dashboard/
├── app_demo.py     Main entry point (Mounts the pages)
├── requirements.txt
├── .env  SPARQL Endpoint URL/Credentials
├── src/
│   ├── __init__.py
│   ├── sparql_client.py 	Query functions
│   └── ui_components.py Functions for UI event/output logic
└── Dockerfile




### docker
Environment variables (currently only the SPARQL_ENDPOINT) may be defined in a separate .env or passed through the docker build
* SPARQL_ENDPOINT=http://compass.project.urbandatacentre.ca/repositories/CDT_Rules

Building the container, run in the folder (hpcdm-dashboard):
sudo docker build --progress=plain -t dashboard_img .

Running the container:
sudo docker run -d -p 7860:7860 --name demo_container --restart unless-stopped dashboard_img