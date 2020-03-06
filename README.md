# portfolio

This is a cash flow analysis tool that supports discounted and undiscounted flows. In addition, the concept "digital gallons" are supported in parallel with described cash flows.

## Running a Voila Server

It is possible to create a voila server using the `Dockerfile` provided in the repository.

### Development

In order to rapidly iterate on image builds, and container starts/stops, I created the `recreate.sh` script.

```bash
chmod +x recreate.sh  # make sure file is executable by user
./recreate.sh  # execute the bash script
```

### Building the Image

If building the docker image from scratch is your cup of tea, you may do so with the following.

```bash
docker image build -t portfolio .
```

### Starting the container

The bind mount allows running servers to be reloaded and automatically reflect changes done in development. If this is not the desired behavior, the docker file can be altered so that the image copies the notebook file the voila server is created from to `/tmp` instead and the `--mount` command line argument may be removed.

```bash
docker container run \
    --name portfolio-app \  # name the container
    --rm \  # remove container when it finishes executing
    -d \  # run as daemon
    -p 8866:8866 \  # export port 8866 (host_port_to_run_on:application_port_in_docker)
    --mount type=bind,source="$(pwd)",target=/tmp \  # mounts current directory to /tmp in container
    portfolio  # name of the image
```


### Serving through a nginx reverse proxy

This assumes voila is running on port `8866`, which is its default.

```nginx
  location / {
    access_log off;
    proxy_pass http://127.0.0.1:8866;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  }

  location ~ /api/kernels/ {
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_http_version 1.1;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header Host $host;
    proxy_pass http://127.0.0.1:8866;
  }

  location ~ /terminals/ {
    proxy_pass            http://127.0.0.1:8866;
    proxy_set_header      Host $host;
    # websocket support
    proxy_http_version    1.1;
    proxy_set_header      Upgrade "websocket";
    # proxy_set_header    Connection "Upgrade";
    proxy_read_timeout    86400;
  }
```