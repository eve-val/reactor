
Initial setup:

```
sqlite3 ./data/db.sqlite "VACUUM;"
curl https://www.fuzzwork.co.uk/dump/sqlite-latest.sqlite.bz2 | bunzip2 -c > ./data/reference.sqlite
poetry install
poetry run init_db
poetry run reactor
```