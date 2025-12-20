docker compose -f /home/ubuntu/apps/docker/docker-compose.yml down whatsapp_auth
docker rmi mservatius/whatsapp_auth:arm
docker build -t whatsapp_auth:arm .
docker tag whatsapp_auth:arm mservatius/whatsapp_auth:arm
docker push mservatius/whatsapp_auth:arm
docker rmi whatsapp_auth:arm
docker rmi mservatius/whatsapp_auth:arm
docker compose -f /home/ubuntu/apps/docker/docker-compose.yml up whatsapp_auth -d