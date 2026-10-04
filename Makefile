.PHONY: deploy deploy-bootstrap check lint test deps clean

VAULT_TPL := group_vars/timeservers/vault.yml.tpl
VAULT_YML := group_vars/timeservers/vault.yml

# Prefix for any recipe that runs with the decrypted vault on disk. Each recipe
# line is its own shell, so a separate 'rm' line never runs once the playbook
# fails. The trap removes the vault however the shell ends (success, failure
# or Ctrl-C) and leaves the playbook's exit code for make to see.
WITH_VAULT_CLEANUP := trap 'rm -f $(VAULT_YML)' EXIT INT TERM;

# Normal idempotent re-run (admin SSH key must already be deployed)
deploy: _inject
	$(WITH_VAULT_CLEANUP) ansible-playbook playbook.yml

# First-run: Pi Imager creates admin user with password auth
deploy-bootstrap: _inject
	$(WITH_VAULT_CLEANUP) ansible-playbook playbook.yml -u admin --ask-pass -e ssh_enforce_hardening=false --ssh-extra-args="-o IdentitiesOnly=yes"

# Dry-run with diff (does not make changes)
check: _inject
	$(WITH_VAULT_CLEANUP) ansible-playbook playbook.yml --check --diff

# Always re-inject from 1Password — never reuse a stale vault.yml
_inject:
	op inject -f -i $(VAULT_TPL) -o $(VAULT_YML)

deps:
	ansible-galaxy collection install -r requirements.yml

lint:
	ansible-lint playbook.yml

# Unit tests for the on-device Python tools (no hardware needed)
test:
	python3 -m unittest discover -s roles/gnsstool/tests

clean:
	rm -f $(VAULT_YML)
	rm -rf .ansible_cache
