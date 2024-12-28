# Instructions 

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
- 
