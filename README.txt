per fare il dump locale 

mirko@mirko-ThinkPad-T14s-Gen-6:~/Documents/github/osm_fetch_testing$ sudo docker exec osm_fetch_testing-mongodb-1 \
  mongodump \
  --username user \
  --password pass \
  --authenticationDatabase admin \
  --db 15minute \
  --out /tmp/mongo_dump

  sudo docker cp osm_fetch_testing-mongodb-1:/tmp/mongo_dump /tmp/mongo_dump
  
  
  mirko@mirko-ThinkPad-T14s-Gen-6:~/Documents/github/osm_fetch_testing/postgres_init$ sudo docker exec osm_fetch_testing-postgres-1 \
  pg_dump \
  -U postgres \
  -d 15minute \
  --clean \
  --if-exists \
  > postgres_init/01_dump.sql

