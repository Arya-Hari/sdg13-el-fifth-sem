# Instructions (Command-Line Interaction)

## SearXNG Installation
- Install [Docker](https://docs.docker.com/desktop/setup/install/windows-install/)
- Clone the official repository
  
  ```
  git clone https://github.com/searxng/searxng-docker.git
  cd searxng-docker
  ```
- On the command prompt, enter ```bash```. Then, type in the following command to generate the secret key.
  
  ```sed -i "s|ultrasecretkey|$(openssl rand -hex 32)|g" searxng/settings.yml```   
- Open the ```settings.yml``` file in the ```searxng-docker/searxng``` folder. Under the ```server``` field, set ```limiter: false```. Add the following lines -

  ```
  search:
    formats:
      - html
      - json
  ```
- From the terminal, run ```docker-compose up -d```.

## Ollama Setup
- Install [Ollama](https://ollama.com/download/windows)
- Run the command
  ```ollama run llama3.2``` on the terminal to start the Llama 3.2 3B model locally on Ollama.

## Running the Script
- Create a virtual environment : ```python -m venv .venv```
- Activate the virtual environment : ```.venv\Scripts\activate```
- Install dependencies : ```pip install requirements.txt```
- Run the script : ```python ollama-searxng.py```
