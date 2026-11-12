# Infrastructure

Everything for the Azure deployment, in Terraform. One resource group holds it
all, so one command removes it all.

Built to cost as little as possible:

- **Database**: Postgres with pgvector, at the size the Azure free account covers for 12 months
  (B1ms, 32 GB, auto-grow off). Nobody signs in with a password: the API uses its managed identity.
- **API**: a Container App that scales to zero when nobody is visiting. Its image is on GitHub's
  free registry (ghcr.io), built by `.github/workflows/api-image.yml`, so there is no Azure registry.
- **Site**: Static Web Apps, free tier.
- **Secrets**: Key Vault holds the Anthropic key. Terraform makes the slot; the key is put in by hand,
  so it never lands in Terraform's state file.
- **Budget alert**: emails at 50%, 80% and 100% of `monthly_budget`.

## One-time setup

1. `az login`
2. Create `terraform.tfvars` (git-ignored):
   ```hcl
   subscription_id      = "<az account show --query id -o tsv>"
   alert_email          = "<where budget alerts go>"
   admin_principal_name = "<az ad signed-in-user show --query userPrincipalName -o tsv>"
   ```
3. `terraform init`

## Deploy, in two phases

The API can't be created before its image exists, so:

```bash
# Phase 1: everything except the API
terraform apply

# Copy the passages into the new database (see "Loading the data" below).

# Phase 2: the API, once the image is on ghcr.io
terraform apply -var api_image=ghcr.io/<github-user>/rag-galaxy-api:<commit>
```

Then put the Anthropic key in the Key Vault (it is read from your `.env`, and never printed):

```bash
az keyvault secret set --vault-name "$(terraform output -raw key_vault_name)" \
  --name anthropic-api-key --value "$(grep '^ANTHROPIC_API_KEY=' ../.env | cut -d= -f2-)" --output none
```

Without the key the site still works: the example questions replay, and new questions show what
was retrieved without a written answer.

## Loading the data

The live database is a copy of the local one, so the passages keep their ids and the saved example
answers (`backend/app/baked/ev.json`) still match. From the repository root, with the local database running:

```bash
docker exec rag-galaxy-db-1 pg_dump -U postgres -d rag --no-owner --no-privileges --no-comments \
  --exclude-table-data=traces > /tmp/rag.sql
```

Then open the server's firewall to your own address for a moment, restore with `psql` signing in as
yourself (`az account get-access-token --resource-type oss-rdbms`), and close the firewall again.

## Publishing the site files

```bash
cd ../frontend
VITE_API_URL="$(terraform -chdir=../infra output -raw api_url)" \
VITE_SITE_URL="$(terraform -chdir=../infra output -raw frontend_url)" \
VITE_COMMIT="$(git rev-parse HEAD)" npm run build
npx @azure/static-web-apps-cli deploy ./dist --env production \
  --deployment-token "$(terraform -chdir=../infra output -raw static_web_app_deploy_token)"
```

## Tear it all down

```bash
terraform destroy
```

That deletes the resource group and everything in it. The data is still in the local database and
in `data/seeds/`, so nothing is lost.
