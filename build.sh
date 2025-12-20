docker compose -f /home/msh/docker/compose/docker-compose.yml down karatube2
docker rmi mservatius/karatube2:latest
docker build -t karatube2:latest .
docker tag karatube2:latest mservatius/karatube2:latest
docker push mservatius/karatube2:latest
docker rmi karatube2:latest
docker rmi mservatius/karatube2:latest
docker compose -f /home/msh/docker/compose/docker-compose.yml up karatube2:latest -d