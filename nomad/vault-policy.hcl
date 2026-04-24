# Vault policy for AchaeanFleet Nomad integration
#
# Apply with:
#   vault policy write achaean-secrets nomad/vault-policy.hcl
#
# This policy grants read access to all secrets under the KV v2 path
# secret/achaean/*, which is where the mesh stores API keys.

path "secret/data/achaean/*" {
  capabilities = ["read"]
}
