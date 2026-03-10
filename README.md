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
The code may be run directly but the easiest way to get started is with docker.
### docker
Environment variables (currently only the SPARQL_ENDPOINT) may be defined in a separate .env or passed through the docker build
* SPARQL_ENDPOINT=http://compass.project.urbandatacentre.ca/repositories/CDT_Rules

Building the container, run in the folder (hpcdm-dashboard):
sudo docker build --progress=plain -t dashboard_img .

Running the container:
sudo docker run -d -p 7860:7860 --name demo_container --restart unless-stopped dashboard_img

## Documentation
See [the documentation](https://github.com/csse-uoft/hpcdm-dashboard/wiki/Documentation) for more details.
