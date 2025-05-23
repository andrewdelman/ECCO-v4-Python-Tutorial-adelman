# Run tutorials on an AWS EC2 instance using a SMCE Docker image

(valid as of 2024-09-04; adapted from readme at `ECCO-v4-Python-Tutorial/Docker/README.md`)


## Getting started

To set this up you need an AWS EC2 instance with a Linux OS and Docker installed. The Dockerfile can be retrieved using

```bash
wget https://raw.githubusercontent.com/ECCO-GROUP/ECCO-v4-Python-Tutorial/master/Docker/smce/Dockerfile
```

## Build the Docker image

The `ECCO-v4-Python-Tutorial/Docker/smce` directory has the files that you need to build the Docker image. Make sure you are in the same directory as the Dockerfile and use:

```bash
docker build . -t ecco_tutorials
```

The build process takes a few minutes, and the image will occupy a little over 10 GB of storage, so make sure your instance has sufficient storage.

## Run the Docker image

When the build completes, you will run the image, which will activate a container within your EC2 instance, and start running Jupyter lab in that container. This is done with the following command:

```bash
docker run -it -p 8888:8888 ecco_tutorials
```

Note the port numbers specified under the `-p` option. The port listed after the colon is the container port, which is always 8888 unless this is changed manually in the `Dockerfile` (on the `EXPOSE 8888` line) prior to building the image. The port before the colon is what the host EC2 instance uses to communicate with the container, and this can be specified differently depending on the user's port availability.

If you also want to use Pluto notebooks (running Julia code), you will need to also connect to port 1234 on the container, e.g.,

```bash
docker run -it -p 8888:8888 -p 1234:1234 ecco_tutorials
```

When one of the above commands above is run, you will first be queried for NASA Earthdata credentials if those are not already stored in a `~/.netrc` file under your user home directory. After entering the credentials, you will be queried for the container port number (8888 by default unless changed as described above), and an optional password (if no password is entered, none will be needed to log in to Jupyter lab).

As Jupyter lab is launched, you will see a lot of output tagged `ServerApp` or `LabApp`. To free up this window you can press `Ctrl-p` `Ctrl-q`, and the window will escape the container...but importantly, the container is still running. To check the status of Docker containers, run `docker ps -a`.

## Open Jupyter lab in your browser

Now you need to open a connection between your local machine and the EC2 instance with the correct port forwarding. On your local machine you can use any unused port; note that if you are already running Jupyter lab/notebooks locally that port 8888 will likely already be in use. This example uses 9889 as the local port

```bash
ssh -i ~/.ssh/aws_ec2.pem -L 9889:localhost:8888 ec2-user@100.104.70.127
```

and in a browser window on your local machine, access the port you specified before `localhost` above

```bash
http://localhost:9889
```

You will see a screen that asks for a password, but if you didn't enter any before, you can just go ahead and click `Login`. Now you have access to the tutorial repository, and the tutorials are in the directory `Tutorials_as_Jupyter_Notebooks`.

## Re-connect to Jupyter lab in Docker container

If the Docker container is stopped or exited, the Jupyter lab session will also exit. To restart a Docker container use `docker ps -a` to find the container name and ID, and then use

```bash
docker start <container-name or id>
```

to re-start the container. Then you may need to run the following on your instance to re-start Jupyter lab within the container:

```bash
docker exec -it <container-name or id> ~/jupyter_lab_start_docker.sh
```

and you should see the `ServerApp` and `LabApp` output appear indicating that the session has started. Then you can use `Ctrl-p` `Ctrl-q` to escape that window from the container.
