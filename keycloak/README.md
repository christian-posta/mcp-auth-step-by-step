You can set this up with:

Get into the .venv:

```bash
ROOT_PRO$ source .venv/bin/activate
```

Go to keycloak dir and run the script

```bash
cd keycloak
python setup_keycloak.py --config config.json --url http://localhost:8080
```